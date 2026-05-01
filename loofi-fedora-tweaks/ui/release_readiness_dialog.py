"""Guided release readiness detail view."""

from __future__ import annotations

from collections import OrderedDict

from PyQt6.QtCore import QObject, Qt, QThread, pyqtSignal
from PyQt6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from core.diagnostics.release_readiness import (
    ReadinessCheck,
    ReleaseReadiness,
    ReleaseReadinessReport,
)
from core.export.support_bundle_v4 import SupportBundleV4
from utils.log import get_logger

logger = get_logger(__name__)


class ReadinessWorker(QObject):
    """Run readiness probes away from the UI thread."""

    finished = pyqtSignal(object)
    failed = pyqtSignal(str)

    def __init__(self, target_key: str):
        super().__init__()
        self.target_key = target_key

    def run(self) -> None:
        try:
            self.finished.emit(ReleaseReadiness.run(self.target_key))
        except (OSError, RuntimeError, ValueError, TypeError, AttributeError) as exc:
            logger.error("Release readiness probe failed: %s", exc, exc_info=True)
            self.failed.emit(str(exc))


class ReleaseReadinessDialog(QDialog):
    """Dashboard-launched detail view for release readiness."""

    _STATUS_COLORS = {
        "pass": "#2f855a",
        "info": "#2563eb",
        "warning": "#b45309",
        "error": "#b91c1c",
        "critical": "#991b1b",
    }

    _CATEGORY_LABELS = {
        "system": "System",
        "desktop": "Desktop",
        "package": "Packages",
        "hardware": "Hardware",
        "software": "Applications",
        "network": "Network",
    }

    def __init__(self, target_key: str = "44", parent=None, *, auto_run: bool = True):
        super().__init__(parent)
        self.target_key = target_key
        self.report: ReleaseReadinessReport | None = None
        self.advanced = False
        self._worker_thread: QThread | None = None
        self._worker: ReadinessWorker | None = None
        self.setWindowTitle(self.tr("Release Readiness"))
        self.setMinimumSize(860, 620)
        self._setup_ui()
        if auto_run:
            self.refresh()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 16)
        layout.setSpacing(12)

        header_row = QHBoxLayout()
        self.title = QLabel(self.tr("Release Readiness"))
        self.title.setStyleSheet("font-size: 18px; font-weight: bold;")
        header_row.addWidget(self.title, 1)

        self.target_selector = QComboBox()
        for target in ReleaseReadiness.list_targets():
            self.target_selector.addItem(target.label, target.key)
        self.target_selector.setCurrentIndex(max(0, self.target_selector.findData(self.target_key)))
        self.target_selector.currentIndexChanged.connect(self._on_target_changed)
        header_row.addWidget(self.target_selector)

        self.severity_filter = QComboBox()
        self.severity_filter.addItem(self.tr("All Findings"), "all")
        self.severity_filter.addItem(self.tr("Warnings and Errors"), "attention")
        self.severity_filter.addItem(self.tr("Errors Only"), "error")
        self.severity_filter.addItem(self.tr("Passed"), "pass")
        self.severity_filter.currentIndexChanged.connect(self._render)
        header_row.addWidget(self.severity_filter)

        self.advanced_toggle = QCheckBox(self.tr("Advanced"))
        self.advanced_toggle.stateChanged.connect(self._on_advanced_changed)
        header_row.addWidget(self.advanced_toggle)
        layout.addLayout(header_row)

        self.summary = QLabel("")
        self.summary.setWordWrap(True)
        layout.addWidget(self.summary)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.container = QWidget()
        self.checks_layout = QVBoxLayout(self.container)
        self.checks_layout.addStretch()
        scroll.setWidget(self.container)
        layout.addWidget(scroll, 1)

        footer = QHBoxLayout()
        self.copy_button = QPushButton(self.tr("Copy Support Summary"))
        self.copy_button.clicked.connect(self.copy_support_summary)
        footer.addWidget(self.copy_button)

        self.export_button = QPushButton(self.tr("Export Support Bundle"))
        self.export_button.clicked.connect(self.export_support_bundle)
        footer.addWidget(self.export_button)

        footer.addStretch()
        self.refresh_button = QPushButton(self.tr("Refresh"))
        self.refresh_button.clicked.connect(self.refresh)
        footer.addWidget(self.refresh_button)

        close = QPushButton(self.tr("Close"))
        close.clicked.connect(self.accept)
        footer.addWidget(close)
        layout.addLayout(footer)

    def _on_target_changed(self) -> None:
        self.target_key = self.target_selector.currentData()
        self.refresh()

    def _on_advanced_changed(self) -> None:
        self.advanced = self.advanced_toggle.isChecked()
        self._render()

    def refresh(self) -> None:
        if self._worker_thread and self._worker_thread.isRunning():
            return

        self.summary.setText(self.tr("Running read-only readiness probes..."))
        self.refresh_button.setEnabled(False)
        self.copy_button.setEnabled(False)
        self.export_button.setEnabled(False)
        self._clear_checks()

        self._worker_thread = QThread(self)
        self._worker = ReadinessWorker(self.target_key)
        self._worker.moveToThread(self._worker_thread)
        self._worker_thread.started.connect(self._worker.run)
        self._worker.finished.connect(self._on_report_ready)
        self._worker.failed.connect(self._on_report_failed)
        self._worker.finished.connect(self._worker_thread.quit)
        self._worker.failed.connect(self._worker_thread.quit)
        self._worker_thread.finished.connect(self._worker.deleteLater)
        self._worker_thread.finished.connect(self._worker_thread.deleteLater)
        self._worker_thread.finished.connect(self._on_worker_finished)
        self._worker_thread.start()

    def _on_worker_finished(self) -> None:
        self._worker_thread = None
        self._worker = None
        self.refresh_button.setEnabled(True)
        self.copy_button.setEnabled(self.report is not None)
        self.export_button.setEnabled(self.report is not None)

    def _on_report_ready(self, report: ReleaseReadinessReport) -> None:
        self.report = report
        self._render()

    def _on_report_failed(self, message: str) -> None:
        self.summary.setText(self.tr("Readiness diagnostics failed: %1").replace("%1", message))

    def _clear_checks(self) -> None:
        while self.checks_layout.count() > 1:
            item = self.checks_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

    def _filtered_checks(self) -> list[ReadinessCheck]:
        if self.report is None:
            return []
        mode = self.severity_filter.currentData()
        if mode == "attention":
            return [check for check in self.report.checks if check.severity in {"warning", "error", "critical"}]
        if mode == "error":
            return [check for check in self.report.checks if check.severity in {"error", "critical"}]
        if mode == "pass":
            return [check for check in self.report.checks if check.status == "pass"]
        return list(self.report.checks)

    def _render(self) -> None:
        self._clear_checks()
        if self.report is None:
            return

        metadata = self.report.target_metadata
        preview = self.tr(" Preview profile; no blocking repair is implied.") if metadata.preview else ""
        self.summary.setText(
            self.tr("Score: %1/100 - %2%3")
            .replace("%1", str(self.report.score))
            .replace("%2", self.report.summary)
            .replace("%3", preview)
        )
        grouped: "OrderedDict[str, list[ReadinessCheck]]" = OrderedDict()
        for check in self._filtered_checks():
            grouped.setdefault(check.category, []).append(check)

        if not grouped:
            empty = QLabel(self.tr("No findings match this filter."))
            empty.setObjectName("healthRecs")
            self.checks_layout.insertWidget(self.checks_layout.count() - 1, empty)
            return

        for category, checks in grouped.items():
            label = QLabel(self._CATEGORY_LABELS.get(category, category.title()))
            label.setStyleSheet("font-size: 14px; font-weight: bold; margin-top: 8px;")
            self.checks_layout.insertWidget(self.checks_layout.count() - 1, label)
            for check in checks:
                self.checks_layout.insertWidget(self.checks_layout.count() - 1, self._build_check_card(check))

    def _build_check_card(self, check: ReadinessCheck) -> QFrame:
        frame = QFrame()
        frame.setObjectName("dashboardCard")
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(8)

        top = QHBoxLayout()
        title = QLabel(check.title)
        title.setStyleSheet("font-weight: bold;")
        top.addWidget(title, 1)

        badge = QLabel(check.status.upper())
        color = self._STATUS_COLORS.get(check.severity, "#475569")
        badge.setStyleSheet(
            f"color: {color}; border: 1px solid {color}; border-radius: 4px; "
            "font-size: 10px; font-weight: bold; padding: 2px 5px;"
        )
        top.addWidget(badge)
        layout.addLayout(top)

        summary = QLabel(check.summary)
        summary.setWordWrap(True)
        layout.addWidget(summary)

        guidance = QLabel(check.beginner_guidance)
        guidance.setWordWrap(True)
        guidance.setStyleSheet("color: #9ca3af;")
        layout.addWidget(guidance)

        if check.recommendation:
            recommendation = QLabel(self.tr("Recommendation: %1").replace("%1", check.recommendation.title))
            recommendation.setWordWrap(True)
            recommendation.setObjectName("healthRecs")
            layout.addWidget(recommendation)

        if self.advanced:
            self._add_advanced_details(layout, check)

        return frame

    def _add_advanced_details(self, layout: QVBoxLayout, check: ReadinessCheck) -> None:
        if check.command_preview:
            cmd = QLabel("<code>" + " ".join(check.command_preview) + "</code>")
            cmd.setWordWrap(True)
            cmd.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            cmd.setStyleSheet("background: #111827; color: #f8fafc; padding: 5px; border-radius: 4px; font-family: monospace;")
            layout.addWidget(cmd)
        if check.recommendation:
            action = check.recommendation
            details = [
                self.tr("Risk: %1").replace("%1", action.risk_level),
                self.tr("Manual only: %1").replace("%1", str(action.manual_only)),
                self.tr("Reversible: %1").replace("%1", str(action.reversible)),
                action.rollback_hint,
            ]
            if action.command_preview:
                details.append(" ".join(action.command_preview))
            action_label = QLabel("\n".join(details))
            action_label.setWordWrap(True)
            action_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            action_label.setStyleSheet("font-family: monospace; font-size: 11px; color: #cbd5e1;")
            layout.addWidget(action_label)
        if check.advanced_detail:
            detail = QLabel(check.advanced_detail)
            detail.setWordWrap(True)
            detail.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            detail.setStyleSheet("font-family: monospace; font-size: 11px; color: #cbd5e1;")
            layout.addWidget(detail)

    def copy_support_summary(self) -> None:
        if self.report is None:
            return
        clipboard = QApplication.clipboard()
        clipboard.setText(self.report.support_summary())

    def export_support_bundle(self) -> None:
        path, _selected_filter = QFileDialog.getSaveFileName(
            self,
            self.tr("Export Support Bundle"),
            "loofi-support-bundle-v4.json",
            self.tr("JSON Files (*.json)"),
        )
        if not path:
            return
        try:
            SupportBundleV4.save_json(path, target=self.target_key)
        except (OSError, RuntimeError, ValueError, TypeError) as exc:
            logger.error("Failed to export support bundle: %s", exc, exc_info=True)
            QMessageBox.warning(self, self.tr("Export Failed"), str(exc))
            return
        QMessageBox.information(self, self.tr("Export Complete"), self.tr("Support bundle exported."))
