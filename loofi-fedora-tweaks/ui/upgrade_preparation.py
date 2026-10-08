"""Explicit asynchronous local preparation and manual upgrade handoff."""
from PyQt6.QtCore import Qt, QUrl, pyqtSignal
from PyQt6.QtGui import QDesktopServices
from PyQt6.QtWidgets import QCheckBox, QComboBox, QLabel, QWidget

from core.fedora_release_policy import FEDORA_RELEASE_POLICY
from services.software.upgrade_preparation import UpgradePreparationReport, UpgradePreparationService
from ui.components import Card, PrimaryButton, SecondaryButton
from ui.operation_worker import OperationControllerQtAdapter


class UpgradePreparationCard(Card):
    """Read-only observations do not authorize or run a release upgrade."""

    stopped = pyqtSignal()

    def __init__(self, *, service: UpgradePreparationService | None = None, parent: QWidget | None = None) -> None:
        super().__init__(self.tr("Prepare for a Fedora upgrade"),
                         self.tr("Review local observations and your backup before following Fedora's instructions."), parent=parent)
        self.service = service or UpgradePreparationService()
        self.report: UpgradePreparationReport | None = None
        self._accept_results = True
        self.target = QComboBox()
        self.target.setAccessibleName(self.tr("Target Fedora release"))
        for value in FEDORA_RELEASE_POLICY.action_targets:
            self.target.addItem(value, value)
        self.add_widget(self.target)
        self.check_button = PrimaryButton(self.tr("Check local preparation"))
        self.check_button.clicked.connect(self.check)
        self.add_widget(self.check_button)
        self.cancel_button = SecondaryButton(self.tr("Cancel check"))
        self.cancel_button.clicked.connect(self.request_stop)
        self.cancel_button.setEnabled(False)
        self.add_widget(self.cancel_button)
        self.details = QLabel(self.tr("Not checked. These observations do not predict the next release transaction."))
        self.details.setWordWrap(True)
        self.details.setTextFormat(Qt.TextFormat.PlainText)
        self.add_widget(self.details)
        self.backup_files = QCheckBox(self.tr("I have backed up my important files."))
        self.backup_recovery = QCheckBox(self.tr("I have checked how to recover and access my backup."))
        self.add_widget(self.backup_files)
        self.add_widget(self.backup_recovery)
        self.add_widget(QLabel(self.tr("Manual checklist only. Loofi has not verified a backup.")))
        self.docs_button = SecondaryButton(self.tr("Open official upgrade instructions"))
        self.docs_button.setEnabled(False)
        self.docs_button.clicked.connect(self.open_documentation)
        self.add_widget(self.docs_button)
        self._adapter = OperationControllerQtAdapter(parent=self)
        self._adapter.finished.connect(self._completed)
        self._adapter.failed.connect(self._failed)
        self._adapter.stopped.connect(self._stopped)

    def open_documentation(self) -> None:
        if self.report is not None:
            QDesktopServices.openUrl(QUrl(self.report.documentation))

    @property
    def busy(self) -> bool:
        return self._adapter.busy

    def check(self) -> None:
        if self.busy:
            return
        self.service.reset_cancel()
        self._accept_results = True
        target = self.target.currentData()
        self.check_button.setEnabled(False)
        self.target.setEnabled(False)
        self.cancel_button.setEnabled(True)
        self.details.setText(self.tr("Reading local package health, source configuration, free space, and reboot hints."))
        self._adapter.start(lambda: self.service.prepare(target))

    def request_stop(self) -> None:
        self._accept_results = False
        self.service.cancel()
        self._adapter.cancel()
        if self.busy:
            self.details.setText(self.tr("Check cancelled. Run a new check to collect current observations."))

    def cleanup(self, timeout_ms: int = 1000) -> bool:
        self.request_stop()
        return self._adapter.close(timeout_ms)

    def _stopped(self) -> None:
        self.check_button.setEnabled(True)
        self.target.setEnabled(True)
        self.cancel_button.setEnabled(False)
        self.stopped.emit()

    def _failed(self, _message: str) -> None:
        if self._accept_results:
            self.details.setText(self.tr("The local check failed. Preparation remains unknown."))

    def _completed(self, report: UpgradePreparationReport) -> None:
        if not self._accept_results:
            return
        self.report = report
        self.docs_button.setEnabled(True)
        target_labels = {"stable": "Stable target", "preview": "Preview target; experimental",
                         "current_release": "Already on this release", "downgrade": "Downgrade; not an upgrade path",
                         "invalid": "Invalid target", "unknown_host": "Host release support unknown"}
        reboot_labels = {"required": "Reboot recommended", "not_required": "No reboot recommended by this probe",
                         "unknown": "Reboot hint unknown"}
        database_text = (self.tr("Local dependency/conflict check passed") if report.package_database.get("healthy")
                         else self.tr("Unknown; local check unavailable or failed"))
        rows = [self.tr(target_labels[report.target_state]),
                self.tr("Host support: %1").replace("%1", str(report.platform["support_status"])),
                self.tr("Package database: %1").replace("%1", database_text),
                self.tr("Enabled sources observed: %1").replace("%1", str(report.sources.get("enabled_count", self.tr("Unknown")))),
                self.tr(reboot_labels[report.reboot["state"]])]
        if report.reboot.get("packages"):
            rows.append(self.tr("Packages updated since boot: %1").replace("%1", ", ".join(report.reboot["packages"])))
        for disk in report.disks:
            free = self.tr("Unknown") if disk["state"] == "unknown" else f'{disk["free_bytes"] / 1024**3:.1f} GiB'
            rows.append(self.tr("Free space at %1: %2").replace("%1", disk["mount"]).replace("%2", free))
        for source_id, state in report.sources.get("known_sources", {}).items():
            rows.append(self.tr("%1 configuration: %2").replace("%1", source_id).replace("%2", self.tr(state)))
        if report.platform["is_atomic"]:
            rows.append(self.tr("Atomic: package and reboot checks are unavailable here. Follow your edition's upgrade documentation."))
        rows.extend([self.tr("Checked: %1").replace("%1", report.checked_at),
                     self.tr("Source configuration and free space are observations, not a readiness guarantee."),
                     self.tr("No upgrade is downloaded or applied. Follow the official instructions when ready.")])
        self.details.setText("\n".join(rows))
