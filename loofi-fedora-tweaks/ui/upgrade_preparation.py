"""Explicit asynchronous local preparation and manual upgrade handoff."""
from dataclasses import replace
from datetime import datetime, timezone

from PyQt6.QtCore import Qt, QUrl, pyqtSignal
from PyQt6.QtGui import QDesktopServices
from PyQt6.QtWidgets import QCheckBox, QComboBox, QLabel, QWidget

from core.fedora_release_policy import FEDORA_RELEASE_POLICY
from services.software.upgrade_preparation import UpgradePreparationReport, UpgradePreparationService
from services.software.upgrade_checklist import (
    UpgradePreparationChecklist,
    UpgradePreparationChecklistStore,
    UnsupportedFutureChecklistSchema,
)
from ui.components import Card, PrimaryButton, SecondaryButton
from ui.operation_worker import OperationControllerQtAdapter


class UpgradePreparationCard(Card):
    """Read-only observations do not authorize or run a release upgrade."""

    stopped = pyqtSignal()

    def __init__(self, *, service: UpgradePreparationService | None = None,
                 checklist_store: UpgradePreparationChecklistStore | None = None,
                 parent: QWidget | None = None) -> None:
        super().__init__(self.tr("Prepare for a Fedora upgrade"),
                         self.tr("Review local observations and your backup before following Fedora's instructions."), parent=parent)
        self.service = service or UpgradePreparationService()
        self.checklist_store = checklist_store or UpgradePreparationChecklistStore()
        self.report: UpgradePreparationReport | None = None
        self._accept_results = True
        self._checklist_store_error = ""
        try:
            saved = self.checklist_store.read()
            self._checklist = saved.checklist
            if not saved.writable:
                self._checklist_store_error = "Saved checklist data uses a newer version and is read-only."
        except (OSError, RuntimeError, TypeError, ValueError):
            self._checklist = UpgradePreparationChecklist()
            self._checklist_store_error = "Saved checklist data could not be read safely."
        self.target = QComboBox()
        self.target.setAccessibleName(self.tr("Target Fedora release"))
        for value in FEDORA_RELEASE_POLICY.action_targets:
            self.target.addItem(value, value)
        target_index = self.target.findData(self._checklist.target)
        if target_index >= 0:
            self.target.setCurrentIndex(target_index)
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
        self.backup_files.setChecked(self._checklist.backup_files_confirmed)
        self.backup_files.setAccessibleName(self.tr("I have backed up my important files"))
        self.backup_recovery = QCheckBox(self.tr("I have checked how to recover and access my backup."))
        self.backup_recovery.setChecked(self._checklist.backup_recovery_confirmed)
        self.backup_recovery.setAccessibleName(self.tr("I have checked how to recover and access my backup"))
        self.add_widget(self.backup_files)
        self.add_widget(self.backup_recovery)
        self.add_widget(QLabel(self.tr("Manual checklist only. Loofi has not verified a backup.")))
        self.checklist_status = QLabel()
        self.checklist_status.setWordWrap(True)
        self.checklist_status.setTextFormat(Qt.TextFormat.PlainText)
        self.add_widget(self.checklist_status)
        self.docs_button = SecondaryButton(self.tr("Open official upgrade instructions"))
        self.docs_button.setEnabled(False)
        self.docs_button.clicked.connect(self.open_documentation)
        self.add_widget(self.docs_button)
        self._adapter = OperationControllerQtAdapter(parent=self)
        self._adapter.finished.connect(self._completed)
        self._adapter.failed.connect(self._failed)
        self._adapter.stopped.connect(self._stopped)
        self.target.currentIndexChanged.connect(self._checklist_changed)
        self.backup_files.toggled.connect(self._backup_files_changed)
        self.backup_recovery.toggled.connect(self._backup_recovery_changed)
        self._update_checklist_status()

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
        self._save_checklist(report=report)
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
        third_party = report.sources.get("third_party_source_ids", [])
        if third_party:
            rows.append(self.tr("Potential third-party source IDs observed: %1").replace("%1", ", ".join(third_party)))
        if report.platform["is_atomic"]:
            rows.append(self.tr("Atomic: package and reboot checks are unavailable here. Follow your edition's upgrade documentation."))
        rows.extend([self.tr("Checked: %1").replace("%1", report.checked_at),
                     self.tr("Source configuration and free space are observations, not a readiness guarantee."),
                     self.tr("No upgrade is downloaded or applied. Follow the official instructions when ready.")])
        self.details.setText("\n".join(rows))

    def _checklist_changed(self, *_args: object) -> None:
        self._save_checklist()

    def _backup_files_changed(self, checked: bool) -> None:
        timestamp = datetime.now(timezone.utc).isoformat() if checked else ""
        self._save_checklist(backup_files_confirmed_at=timestamp)

    def _backup_recovery_changed(self, checked: bool) -> None:
        timestamp = datetime.now(timezone.utc).isoformat() if checked else ""
        self._save_checklist(backup_recovery_confirmed_at=timestamp)

    def _save_checklist(self, *, report: UpgradePreparationReport | None = None,
                        backup_files_confirmed_at: str | None = None,
                        backup_recovery_confirmed_at: str | None = None) -> None:
        current = self._checklist
        source_ids = current.third_party_source_ids
        observation_target = current.observation_target
        observation_checked_at = current.observation_checked_at
        observation_state = current.observation_state
        if report is not None:
            observed = report.sources.get("third_party_source_ids", [])
            source_ids = tuple(item for item in observed if isinstance(item, str))[:256]
            observation_target = report.target
            observation_checked_at = report.checked_at
            observation_state = report.state if report.state in {"completed", "partial"} else "partial"
        candidate = replace(
            current,
            target=str(self.target.currentData() or current.target),
            updated_at=datetime.now(timezone.utc).isoformat(),
            observation_target=observation_target,
            observation_checked_at=observation_checked_at,
            observation_state=observation_state,
            third_party_source_ids=source_ids,
            backup_files_confirmed_at=current.backup_files_confirmed_at if backup_files_confirmed_at is None else backup_files_confirmed_at,
            backup_recovery_confirmed_at=current.backup_recovery_confirmed_at if backup_recovery_confirmed_at is None else backup_recovery_confirmed_at,
        )
        self._checklist = candidate
        try:
            self.checklist_store.save(candidate)
            self._checklist_store_error = ""
        except (OSError, RuntimeError, TypeError, ValueError, UnsupportedFutureChecklistSchema):
            self._checklist_store_error = "Saved checklist progress could not be stored."
        self._update_checklist_status()

    def _update_checklist_status(self) -> None:
        selected_target = str(self.target.currentData() or self._checklist.target)
        checklist = self._checklist
        if not checklist.observation_checked_at:
            observation = self.tr("No saved local observations yet.")
        elif checklist.observations_are_stale(selected_target=selected_target):
            observation = self.tr("Saved observations are stale for this target or are more than seven days old. Run a new check.")
        else:
            observation = self.tr("Saved observations for %1: %2 (%3).")\
                .replace("%1", checklist.observation_target)\
                .replace("%2", checklist.observation_checked_at)\
                .replace("%3", self.tr(checklist.observation_state))
        backup = self.tr("Backup confirmations are your statements, not verified by Loofi.")
        if checklist.backup_files_confirmed_at or checklist.backup_recovery_confirmed_at:
            backup += " " + self.tr("Your confirmation dates remain saved independently of observation freshness.")
        rows = [observation, backup]
        if checklist.third_party_source_ids:
            rows.append(self.tr("Potential third-party source IDs from the saved check: %1").replace("%1", ", ".join(checklist.third_party_source_ids)))
        if self._checklist_store_error:
            rows.append(self.tr(self._checklist_store_error))
        self.checklist_status.setText("\n".join(rows))
