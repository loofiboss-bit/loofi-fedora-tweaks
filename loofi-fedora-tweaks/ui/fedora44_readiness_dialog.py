"""Focused Fedora KDE 44 readiness detail view."""

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QCheckBox,
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from core.diagnostics.fedora44_readiness import Fedora44Readiness, ReadinessCheck
from utils.log import get_logger

logger = get_logger(__name__)


class Fedora44ReadinessDialog(QDialog):
    """Dashboard-launched detail view for Fedora KDE 44 readiness."""

    _STATUS_COLORS = {
        "pass": "#a6e3a1",
        "info": "#89b4fa",
        "warning": "#fab387",
        "error": "#e8556d",
    }

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(self.tr("Fedora KDE 44 Readiness"))
        self.setMinimumSize(760, 560)
        self.report = None
        self.advanced = False
        self._setup_ui()
        self._run_readiness()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 16)
        layout.setSpacing(12)

        header_row = QHBoxLayout()
        self.title = QLabel(self.tr("Fedora KDE 44 Readiness"))
        self.title.setStyleSheet("font-size: 18px; font-weight: bold;")
        header_row.addWidget(self.title)
        header_row.addStretch()
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
        footer.addStretch()
        refresh = QPushButton(self.tr("Refresh"))
        refresh.clicked.connect(self._run_readiness)
        footer.addWidget(refresh)
        close = QPushButton(self.tr("Close"))
        close.clicked.connect(self.accept)
        footer.addWidget(close)
        layout.addLayout(footer)

    def _on_advanced_changed(self) -> None:
        self.advanced = self.advanced_toggle.isChecked()
        self._render()

    def _run_readiness(self) -> None:
        try:
            self.report = Fedora44Readiness.run()
            self._render()
        except (OSError, RuntimeError, ValueError, TypeError, AttributeError) as exc:
            logger.error("Failed to run Fedora KDE 44 readiness: %s", exc, exc_info=True)
            self.summary.setText(self.tr("Readiness diagnostics failed: %1").replace("%1", str(exc)))

    def _clear_checks(self) -> None:
        while self.checks_layout.count() > 1:
            item = self.checks_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

    def _render(self) -> None:
        if self.report is None:
            return
        self.summary.setText(
            self.tr("Score: %1/100 - %2")
            .replace("%1", str(self.report.score))
            .replace("%2", self.report.summary)
        )
        self._clear_checks()
        for check in self.report.checks:
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
        color = self._STATUS_COLORS.get(check.status, "#6c7086")
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
        guidance.setStyleSheet("color: #6c7086;")
        layout.addWidget(guidance)

        if self.advanced:
            if check.command_preview:
                cmd = QLabel("<code>" + " ".join(check.command_preview) + "</code>")
                cmd.setWordWrap(True)
                cmd.setStyleSheet("background: #1c2030; padding: 5px; border-radius: 4px; font-family: monospace;")
                layout.addWidget(cmd)
            if check.advanced_detail:
                detail = QLabel(check.advanced_detail)
                detail.setWordWrap(True)
                detail.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
                detail.setStyleSheet("font-family: monospace; font-size: 11px; color: #bac2de;")
                layout.addWidget(detail)

        return frame
