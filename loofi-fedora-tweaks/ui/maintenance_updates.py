"""
Maintenance update, cleanup, overlay, and upgrade sections.
Part of v11.0 "Aurora Update".

Uses a lazy route-owned stack to preserve all features from the
original UpdatesTab, CleanupTab, and OverlaysTab.
The Overlays sub-tab is only shown on Atomic (rpm-ostree) systems.
"""

import typing

# flake8: noqa: F401

from services.system.system import cached_which

from core.plugins.metadata import PluginMetadata
from core.fedora_release_policy import FEDORA_RELEASE_POLICY
from PyQt6.QtCore import QObject, QThread, QTimer, pyqtSignal
from PyQt6.QtWidgets import (
    QFrame,
    QComboBox,
    QGroupBox,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QStackedWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)
from services.system import SystemManager
from utils.commands import PrivilegedCommand

from ui.base_tab import BaseTab
from ui.components import (
    FeedbackBanner,
    QuietButton,
    SecondaryButton,
    SectionHeader,
    TaskSummary,
)
from ui.components.layout import PageScaffold
from ui.design import semantic_qcolor
from ui.shared_states import ActionProgress, DetailsDisclosure, ResultBanner
from ui.tooltips import MAINT_CLEANUP, MAINT_JOURNAL, MAINT_ORPHANS
from ui.maintenance_action_center import _ActionCenterOperationWorker


class _UpdatesSubTab(BaseTab):
    """Run supported updates in place through the Action Center authority."""

    actionCenterRequested = pyqtSignal(str, object)

    def __init__(self: typing.Any) -> None:
        super().__init__()
        profile_reader = getattr(SystemManager, "get_platform_profile", None)
        profile_detection_failed = False
        if callable(profile_reader):
            try:
                profile = profile_reader()
            except (OSError, RuntimeError, TypeError, ValueError):
                profile = None
                profile_detection_failed = True
        else:
            profile = None
        if profile is not None:
            self.deployment_backend = str(
                getattr(getattr(profile, "deployment_backend", None), "value", "unknown")
            )
            self.package_manager = str(
                getattr(profile, "package_manager_name", "unknown")
            )
        elif profile_detection_failed:
            self.package_manager = "unknown"
            self.deployment_backend = "unknown"
        else:
            self.package_manager = SystemManager.get_package_manager()
            self.deployment_backend = {
                "dnf": "dnf5",
                "dnf5": "dnf5",
                "rpm-ostree": "rpm_ostree",
                "bootc": "bootc",
            }.get(self.package_manager, "unknown")
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        self.scaffold = PageScaffold(
            self.tr("Updates"),
            self.tr("Update system packages, Flatpaks, and firmware with clear status and automatic verification."),
        )
        root.addWidget(self.scaffold)
        layout = self.scaffold.content_layout

        from ui.update_overview import UpdateOverviewWidget

        self.overview = UpdateOverviewWidget()
        self._selected_source: str | None = None
        layout.addWidget(self.overview)
        self._add_update_overview(layout)
        self._add_source_actions(layout)
        self._add_advanced_sections(layout)
        from core.actions import DirectActionService

        self._direct_service = DirectActionService()
        self._direct_thread: QThread | None = None
        self._direct_worker: _ActionCenterOperationWorker | None = None
        self._pending_update: dict[str, str] | None = None
        self._prepared_update: typing.Any | None = None
        self.overview.snapshotChanged.connect(self._on_overview_snapshot)
        self._on_overview_snapshot(self.overview.snapshot)

        self.action_progress = ActionProgress(self.tr("Waiting for an update action."))
        self.progress_bar = self.action_progress.progress_bar
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(True)
        self.progress_bar.setFormat("%p% - %v")
        layout.addWidget(self.action_progress)
        self.action_progress.hide()

        self.output_area.setAccessibleName(self.tr("Update output"))
        self.output_area.setMaximumHeight(16777215)
        self.add_output_disclosure(layout, self.tr("Show update command output"))
        self.runner.progress_update.connect(self.update_progress)

    def _add_update_overview(self, layout: QVBoxLayout) -> None:
        """Add compact status context without making a review page mandatory."""

        update_guidance = QLabel(self._update_guidance())
        update_guidance.setWordWrap(True)
        self.plan_details = DetailsDisclosure(summary=self.tr("How update plans work"))
        self.plan_details.add_widget(update_guidance)
        layout.addWidget(self.plan_details)
        self.update_state = FeedbackBanner(
            self.tr("Ready to update"),
            self.tr("Choose an update source. Loofi checks it, runs it, and verifies the result here."),
            kind="info",
        )
        self.update_state.setObjectName("updatesState")
        self.update_state.setProperty("updateLifecycleState", "idle")
        layout.addWidget(self.update_state)
        self.update_state.hide()

        self.update_summary = TaskSummary(
            self.tr("Update details"),
            self.tr("Each update is prepared and verified by Action Center in the background."),
            status=self.tr("Ready"),
        )
        self.update_summary.add_fact(self.tr("System mode"), self.package_manager)
        self.update_summary.add_fact(self.tr("Execution"), self.tr("Action Center only"))
        self.update_summary.add_fact(self.tr("Verification"), self.tr("Required after execution"))
        self.plan_details.add_widget(self.update_summary)

        self.btn_update_all = QuietButton(
            self.tr("Why are sources separate?"),
            description=self.tr("Each source has its own preflight and verification so one failure cannot hide another."),
        )
        self.btn_update_all.setAccessibleName(self.tr("Explain independent update plans"))
        self.btn_update_all.setObjectName("maintUpdateAllBtn")
        self.btn_update_all.clicked.connect(self.run_update_all)
        self.plan_details.add_widget(self.btn_update_all)

    def _add_source_actions(self, layout: QVBoxLayout) -> None:
        """Add one direct action per update source."""
        if self.deployment_backend == "rpm_ostree":
            self.btn_dnf = SecondaryButton(self.tr("Update System (rpm-ostree)"))
        elif self.deployment_backend == "bootc":
            self.btn_dnf = SecondaryButton(self.tr("System updates require manual bootc guidance"))
        elif self.deployment_backend == "unknown":
            self.btn_dnf = SecondaryButton(self.tr("System update backend is unknown"))
        else:
            self.btn_dnf = SecondaryButton(self.tr("Update System (DNF)"))
        self.btn_dnf.setAccessibleName(self.tr("Update System"))
        self.btn_dnf.setProperty("sourceId", "system")
        self.btn_dnf.clicked.connect(lambda _checked=False: self._select_or_review_source("system"))

        self.btn_flatpak = SecondaryButton(self.tr("Update Flatpaks"))
        self.btn_flatpak.setAccessibleName(self.tr("Update Flatpaks"))
        self.btn_flatpak.setProperty("sourceId", "flatpak")
        self.btn_flatpak.clicked.connect(lambda _checked=False: self._select_or_review_source("flatpak"))

        self.btn_fw = SecondaryButton(self.tr("Update firmware"))
        self.btn_fw.setAccessibleName(self.tr("Update firmware"))
        self.btn_fw.setProperty("sourceId", "firmware")
        self.btn_fw.clicked.connect(lambda _checked=False: self._select_or_review_source("firmware"))

        for button in (self.btn_dnf, self.btn_flatpak, self.btn_fw):
            button.setEnabled(False)

        overview_layout = self.overview.layout()
        if isinstance(overview_layout, QVBoxLayout):
            for source, button in (("system", self.btn_dnf), ("flatpak", self.btn_flatpak), ("firmware", self.btn_fw)):
                overview_layout.insertWidget(overview_layout.indexOf(self.overview.rows[source][2]), button)

    def _on_overview_snapshot(self, snapshot: object) -> None:
        """Enable direct execution only after a fresh, truthful source check."""
        results = {
            str(getattr(result, "source", "")): result
            for result in getattr(snapshot, "sources", ())
        }
        backend_value = getattr(snapshot, "backend", "unknown")
        backend = str(getattr(backend_value, "value", backend_value))
        support_status = str(getattr(snapshot, "support_status", "unknown"))
        execution_policy_allowed = (
            support_status == "supported"
            and backend in {"dnf5", "rpm_ostree"}
        )
        buttons = {
            "system": self.btn_dnf,
            "flatpak": self.btn_flatpak,
            "firmware": self.btn_fw,
        }
        for source, button in buttons.items():
            result = results.get(source)
            status = str(getattr(result, "status", "unchecked"))
            fresh_result = status in {"available", "up_to_date"} and not bool(
                getattr(result, "stale", True)
            )
            ready = fresh_result and execution_policy_allowed
            button.setEnabled(ready)
            button.setProperty("sourceStatus", status)
            button.setProperty("reviewPolicyAllowed", execution_policy_allowed)
            button.setProperty("readyForReview", ready)
            button.setProperty("readyForExecution", ready)
            if source != self._selected_source:
                label = {
                    "system": self.tr("Update System"),
                    "flatpak": self.tr("Update Flatpaks"),
                    "firmware": self.tr("Update firmware"),
                }[source] if ready else {
                    "system": self.tr("Check System updates"),
                    "flatpak": self.tr("Check Flatpak updates"),
                    "firmware": self.tr("Check firmware updates"),
                }[source]
                button.setText(label)
                button.setAccessibleName(
                    label
                )

    def _select_or_review_source(self, source: str) -> None:
        """Start the selected source directly after the fresh overview check."""
        buttons = {
            "system": self.btn_dnf,
            "flatpak": self.btn_flatpak,
            "firmware": self.btn_fw,
        }
        button = buttons.get(source)
        if button is None or not button.isEnabled():
            return
        if button.property("readyForExecution") is True or button.property("readyForReview") is True:
            {
                "system": self.run_dnf_update,
                "flatpak": self.run_flatpak_update,
                "firmware": self.run_fw_update,
            }[source]()
            return

    def _add_advanced_sections(self, layout: QVBoxLayout) -> None:
        """Add the bounded kernel inspection and cleanup entry points."""
        kernel_group = QGroupBox(self.tr("Kernel Management"))
        kernel_layout = QHBoxLayout()
        kernel_group.setLayout(kernel_layout)

        btn_list_kernels = QPushButton(self.tr("List Installed Kernels"))
        btn_list_kernels.setAccessibleName(self.tr("List Installed Kernels"))
        btn_list_kernels.clicked.connect(lambda: self.run_single_command("rpm", ["-qa", "kernel"], self.tr("Listing Installed Kernels...")))
        kernel_layout.addWidget(btn_list_kernels)

        btn_remove_old = QPushButton(self.tr("Remove Old Kernels"))
        btn_remove_old.setAccessibleName(self.tr("Remove Old Kernels"))
        btn_remove_old.clicked.connect(
            lambda: self.actionCenterRequested.emit("remove-old-kernels", {})
        )
        kernel_layout.addWidget(btn_remove_old)

        layout.addWidget(kernel_group)


    def _update_guidance(self) -> str:
        if self.deployment_backend == "rpm_ostree":
            return str(self.tr(
                "System updates create a new Atomic deployment. Loofi prepares and verifies it here; "
                "restart only when Fedora reports that the new deployment is ready."
            ))
        if self.deployment_backend == "bootc":
            return str(self.tr(
                "This host uses bootc. System update and recovery actions remain manual until the backend "
                "capability is qualified; no update plan is created here."
            ))
        if self.deployment_backend == "unknown":
            return str(self.tr(
                "The deployment backend could not be identified safely. System update and recovery actions "
                "remain unavailable until the host is identified."
            ))
        return str(self.tr(
            "System updates change the current Fedora installation. Loofi checks the package manager, "
            "runs one source at a time, and verifies the result automatically."
        ))

    def _set_update_state(
        self,
        lifecycle: str,
        title: str,
        message: str,
        *,
        kind: str = "info",
    ) -> None:
        """Present the update lifecycle while execution remains Action Center-owned."""
        self.update_state.show()
        self.update_state.setProperty("updateLifecycleState", lifecycle)
        self.update_state.set_result(kind, title, message)
        status_kind = {
            "succeeded": "success",
            "completed": "success",
            "awaiting_reboot": "warning",
            "verification_failed": "error",
            "failed": "error",
            "blocked": "warning",
            "review_required": "warning",
            "cancelled": "warning",
            "unavailable": "warning",
        }.get(lifecycle, "info")
        self.update_summary.set_status(title, kind=status_kind, description=message)

    def set_checking(self, source: str) -> None:
        self._selected_source = None
        for button in (self.btn_dnf, self.btn_flatpak, self.btn_fw):
            button.setEnabled(False)
        self._set_update_state(
            "checking",
            self.tr("Checking update status"),
            self.tr("Reading available updates for %1 without applying changes.").replace("%1", source),
        )

    def set_updates_available(self, source: str, count: int) -> None:
        source_buttons = (
            ("system", self.btn_dnf, self.tr("System")),
            ("flatpak", self.btn_flatpak, self.tr("Flatpak")),
            ("firmware", self.btn_fw, self.tr("Firmware")),
        )
        for source_id, button, label in source_buttons:
            if label.lower() in source.lower() or source_id in source.lower():
                ready = count >= 0
                button.setEnabled(ready)
                button.setProperty("sourceStatus", "available" if count else "up_to_date")
                button.setProperty("readyForReview", ready)
                button.setProperty("readyForExecution", ready)
                if self._selected_source != source_id:
                    button.setText(
                        self.tr("Update %1" if ready else "Check %1 updates")
                        .replace("%1", label)
                    )
                    button.setAccessibleName(
                        self.tr("Update %1" if ready else "Check %1 updates")
                        .replace("%1", label)
                    )
        self._set_update_state(
            "available",
            self.tr("Updates available"),
            self.tr("%1 has %2 available update(s). Choose Update to prepare and run it on this page.")
            .replace("%1", source)
            .replace("%2", str(max(0, count))),
        )

    def update_progress(self: typing.Any, percent: typing.Any, status: typing.Any) -> typing.Any:
        self._set_update_state(
            "running",
            self.tr("Update operation in progress"),
            str(status),
        )
        self.action_progress.show()
        self.action_progress.status_label.setText(str(status))
        if percent == -1:
            if self.progress_bar.value() == 0 or self.progress_bar.value() == 100:
                self.progress_bar.setRange(0, 0)  # Indeterminate
            self.progress_bar.setFormat(f"{status}")
        else:
            self.progress_bar.setRange(0, 100)
            self.progress_bar.setValue(percent)
            self.progress_bar.setFormat(f"{percent}% - {status}")

    def run_dnf_update(self: typing.Any) -> typing.Any:
        translate = getattr(self, "tr", lambda value: value)
        backend = getattr(self, "deployment_backend", None)
        if backend in {"bootc", "unknown"}:
            self._set_update_state(
                "unavailable",
                translate("System update unavailable"),
                self._update_guidance(),
                kind="warning",
            )
            return
        restart = (
            translate("Required to use the new deployment")
            if backend == "rpm_ostree"
            else translate("Shown in the plan when required")
        )
        _UpdatesSubTab._request_update_plan(
            self,
            "update-fedora-system",
            translate("Fedora system packages"),
            restart,
        )

    def run_flatpak_update(self: typing.Any) -> typing.Any:
        translate = getattr(self, "tr", lambda value: value)
        _UpdatesSubTab._request_update_plan(
            self,
            "update-flatpaks",
            translate("Flatpak applications"),
            translate("Not normally required"),
        )

    def run_fw_update(self: typing.Any) -> typing.Any:
        translate = getattr(self, "tr", lambda value: value)
        _UpdatesSubTab._request_update_plan(
            self,
            "update-firmware",
            translate("Device firmware"),
            translate("Shown in the plan when required"),
        )

    def _request_update_plan(
        self,
        action_id: str,
        source: str,
        restart_requirement: str,
    ) -> None:
        translate = getattr(self, "tr", lambda value: value)
        if not hasattr(self, "_direct_service"):
            self.actionCenterRequested.emit(action_id, {})
            return
        if getattr(self, "_direct_thread", None) is not None:
            self._set_update_state(
                "running",
                translate("An update is already running"),
                translate("Wait for the current update to finish before starting another one."),
                kind="warning",
            )
            return
        self._pending_update = {
            "action_id": action_id,
            "source": source,
            "restart": restart_requirement,
        }
        self._prepared_update = None
        self._set_update_state(
            "preparing",
            translate("Preparing update"),
            translate("Checking the current host and preparing the exact update scope…"),
        )
        self.update_summary.set_status(
            translate("Preparing"),
            kind="info",
            description=source,
        )
        self.action_progress.show()
        self.progress_bar.setRange(0, 0)
        self.progress_bar.setFormat(translate("Preparing update…"))
        self.action_progress.status_label.setText(translate("Checking preconditions"))
        self._set_update_buttons_enabled(False)
        self._start_direct_operation(
            lambda: self._direct_service.run(
                action_id,
                {},
                dry_run=True,
                execution_mode="direct",
            ),
            self._accept_direct_preview,
            translate("Update preparation failed"),
        )

    def _set_update_buttons_enabled(self, enabled: bool) -> None:
        for button in (self.btn_dnf, self.btn_flatpak, self.btn_fw, self.btn_update_all):
            button.setEnabled(enabled)

    def _restore_update_buttons(self) -> None:
        self._on_overview_snapshot(getattr(self.overview, "snapshot", None))
        self.btn_update_all.setEnabled(True)

    def _start_direct_operation(
        self,
        operation: typing.Callable[[], typing.Any],
        on_success: typing.Callable[[typing.Any], None],
        failure_title: str,
    ) -> None:
        """Run one Action Center operation off the GUI thread."""
        if self._direct_thread is not None:
            return
        thread = QThread(self)
        worker = _ActionCenterOperationWorker(operation)
        worker.moveToThread(thread)
        thread.started.connect(worker.run)

        def safe_success(result: typing.Any) -> None:
            try:
                on_success(result)
            except (RuntimeError, TypeError, ValueError) as exc:
                self._direct_operation_failed(str(exc), failure_title)

        worker.finished.connect(safe_success)
        worker.finished.connect(thread.quit)
        worker.failed.connect(lambda message: self._direct_operation_failed(message, failure_title))
        worker.failed.connect(thread.quit)
        thread.finished.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)
        thread.finished.connect(self._clear_direct_operation)
        self._direct_thread = thread
        self._direct_worker = worker
        thread.start()

    def _clear_direct_operation(self) -> None:
        self._direct_thread = None
        self._direct_worker = None

    def _accept_direct_preview(self, result: typing.Any) -> None:
        from core.actions.direct import DirectActionResult

        if not isinstance(result, DirectActionResult):
            self._direct_operation_failed(
                self.tr("The prepared update result was invalid."),
                self.tr("Update preparation failed"),
            )
            return
        self._prepared_update = result
        if result.status != "preview" or not result.plan_id:
            self._present_direct_result(result)
            self._prepared_update = None
            self._restore_update_buttons()
            return

        settings = self._direct_service.settings_store.load()
        needs_confirmation = (
            result.eligibility.kind == "confirmation"
            or (
                (
                    getattr(self._direct_service.settings_store, "explicit_mode", False)
                    or settings.future_schema
                )
                and settings.effective_mode == "review_first"
            )
        )
        if needs_confirmation:
            source = (self._pending_update or {}).get("source", result.action_id)
            restart = {
                "required": self.tr("Required"),
                "may_require": self.tr("May be required"),
                "none": self.tr("Not normally required"),
            }.get(
                str(getattr(result, "reboot_policy", "none")),
                (self._pending_update or {}).get("restart", self.tr("Check result")),
            )
            preview = " ".join(result.preview) if result.preview else self.tr("The exact command is protected by Action Center.")
            answer = QMessageBox.question(
                self,
                self.tr("Confirm update"),
                self.tr(
                    "Update %1 now?\n\nScope: %2\nRestart: %3\nPrepared operation: %4"
                ).replace("%1", source).replace("%2", ", ".join(result.outcome.affected_resources) or self.tr("system state"))
                .replace("%3", restart)
                .replace("%4", preview),
            )
            if answer != QMessageBox.StandardButton.Yes:
                self._set_update_state(
                    "cancelled",
                    self.tr("Update cancelled"),
                    self.tr("No change was applied."),
                    kind="warning",
                )
                self._prepared_update = None
                self._restore_update_buttons()
                return
        QTimer.singleShot(0, self._run_prepared_update)

    def _run_prepared_update(self) -> None:
        prepared = self._prepared_update
        if prepared is None:
            return
        if self._direct_thread is not None:
            QTimer.singleShot(10, self._run_prepared_update)
            return
        self._set_update_state(
            "running",
            self.tr("Updating"),
            self.tr("Action Center is applying the prepared update and verifying the result."),
        )
        self.action_progress.status_label.setText(self.tr("Applying update"))
        self.progress_bar.setRange(0, 0)
        self.progress_bar.setFormat(self.tr("Applying update…"))
        self._start_direct_operation(
            lambda: self._direct_service.run_prepared(
                prepared.plan_id,
                confirmed=True,
                execution_mode="direct",
            ),
            self._accept_direct_result,
            self.tr("Update failed"),
        )

    def _accept_direct_result(self, result: typing.Any) -> None:
        self._prepared_update = None
        self._present_direct_result(result)
        self._restore_update_buttons()

    def _present_direct_result(self, result: typing.Any) -> None:
        status = str(getattr(result, "status", "failed"))
        label = str(getattr(result, "display_label", "Update result"))
        message = str(getattr(result, "message", result))
        lifecycle = {
            "completed_verified": "succeeded",
            "completed_awaiting_reboot": "awaiting_reboot",
            "completed_verification_failed": "verification_failed",
            "preview": "prepared",
            "blocked_by_preflight": "blocked",
            "review_required": "review_required",
            "cancelled": "cancelled",
        }.get(status, "failed")
        kind = {
            "succeeded": "success",
            "awaiting_reboot": "warning",
            "verification_failed": "error",
            "blocked": "warning",
            "review_required": "warning",
            "cancelled": "warning",
        }.get(lifecycle, "error")
        preview = tuple(getattr(result, "preview", ()) or ())
        if preview:
            message = f"{message}\n\n{self.tr('Prepared scope')}: {' '.join(preview)}"
        self._set_update_state(lifecycle, label, message, kind=kind)
        self.action_progress.show()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(100 if status.startswith("completed_") else 0)
        self.progress_bar.setFormat(self.tr("Done") if status.startswith("completed_") else label)
        self.action_progress.status_label.setText(label)

    def _direct_operation_failed(self, message: str, title: str) -> None:
        self._prepared_update = None
        self._set_update_state("failed", title, str(message), kind="error")
        self.action_progress.status_label.setText(title)
        self._restore_update_buttons()

    def run_update_all(self: typing.Any) -> typing.Any:
        update_state = getattr(self, "update_state", None)
        if update_state is not None:
            update_state.set_result(
                "info",
                self.tr("Choose one update source"),
                self.tr("Separate plans keep package lists, restart requirements, and verification clear."),
            )
        self.output_area.setPlainText(
            self.tr("Choose one update source. Action Center prepares and verifies each source separately.")
        )

    def start_process(self: typing.Any) -> typing.Any:
        self._set_update_state(
            "running",
            self.tr("Maintenance operation running"),
            self.tr("Progress and technical output are shown below."),
        )
        self.output_area.clear()
        self.progress_bar.setValue(0)
        self.progress_bar.setFormat("%p% - Waiting...")
        self.action_progress.status_label.setText(self.tr("Update in progress"))
        self.btn_dnf.setEnabled(False)
        self.btn_flatpak.setEnabled(False)
        self.btn_fw.setEnabled(False)
        self.btn_update_all.setEnabled(False)

    def on_command_finished(self: typing.Any, exit_code: typing.Any) -> typing.Any:
        self.append_output(self.tr("\nCommand finished with exit code: {}").format(exit_code))

        for button in (self.btn_dnf, self.btn_flatpak, self.btn_fw):
            ready = button.property("readyForReview")
            button.setEnabled(ready if isinstance(ready, bool) else True)
        self.btn_update_all.setEnabled(True)
        self.progress_bar.setValue(100)
        self.progress_bar.setFormat(self.tr("100% - Done"))
        self.action_progress.status_label.setText(self.tr("Maintenance operation completed") if exit_code == 0 else self.tr("Maintenance operation failed"))
        if exit_code == 0:
            self._set_update_state(
                "succeeded",
                self.tr("Maintenance operation completed"),
                self.tr("Review the technical output and verification result."),
                kind="success",
            )
        else:
            self._set_update_state(
                "failed",
                self.tr("Maintenance operation failed"),
                self.tr("No success is assumed. Review the technical output before retrying."),
                kind="error",
            )

    def _cancel_command(self: typing.Any) -> typing.Any:
        super()._cancel_command()
        self._set_update_state(
            "cancelled",
            self.tr("Update operation cancelled"),
            self.tr("The operation was stopped. Review output and current system state before retrying."),
            kind="warning",
        )

    def run_single_command(self: typing.Any, cmd: typing.Any, args: typing.Any, description: typing.Any) -> typing.Any:
        self.progress_bar.setValue(0)
        self.run_command(cmd, args, description)



class _CleanupSubTab(BaseTab):
    """Sub-tab containing all cleanup and maintenance functionality.

    Preserves every feature from the original CleanupTab:
    - Clean DNF Cache
    - Remove Unused Packages (autoremove, with DNF lock check)
    - Vacuum Journal (2 weeks)
    - SSD Trim (fstrim)
    - Rebuild RPM Database
    - Timeshift snapshot check
    - Output log
    """

    actionCenterRequested = pyqtSignal(str, object)

    def __init__(self: typing.Any) -> None:
        super().__init__()
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        self.scaffold = PageScaffold(
            self.tr("Cleanup"),
            self.tr("Analyze reclaimable data separately from confirmed maintenance actions."),
        )
        root.addWidget(self.scaffold)
        layout = self.scaffold.content_layout

        self.output_area.setAccessibleName(self.tr("Cleanup output"))

        cleanup_group = QGroupBox(self.tr("Safe cleanup choices"))
        cleanup_layout = QVBoxLayout()
        cleanup_group.setLayout(cleanup_layout)
        safe_intro = QLabel(
            self.tr("Nothing is removed on this page. Review creates a plan before any cleanup runs.")
        )
        safe_intro.setWordWrap(True)
        cleanup_layout.addWidget(safe_intro)

        btn_dnf_clean = QPushButton(self.tr("Review DNF Cache Cleanup"))
        btn_dnf_clean.setAccessibleName(self.tr("Review DNF Cache Cleanup in Action Center"))
        btn_dnf_clean.setToolTip(MAINT_CLEANUP)
        btn_dnf_clean.setObjectName("maintReviewDnfClean")
        btn_dnf_clean.clicked.connect(lambda: self.actionCenterRequested.emit("dnf-clean-all", {}))
        cleanup_layout.addWidget(btn_dnf_clean)

        layout.addWidget(cleanup_group)

        maint_group = QGroupBox(self.tr("Additional cleanup and maintenance"))
        maint_group.setObjectName("cleanupAdvancedChoices")
        maint_layout = QVBoxLayout()
        maint_group.setLayout(maint_layout)

        btn_autoremove = QPushButton(self.tr("Review Unused Packages"))
        btn_autoremove.setAccessibleName(self.tr("Remove Unused Packages"))
        btn_autoremove.setObjectName("maintAutoremoveBtn")
        btn_autoremove.setToolTip(MAINT_ORPHANS)
        btn_autoremove.clicked.connect(self.run_autoremove)
        maint_layout.addWidget(btn_autoremove)

        btn_journal = QPushButton(self.tr("Review Journal Retention"))
        btn_journal.setAccessibleName(self.tr("Vacuum Journal"))
        btn_journal.setToolTip(MAINT_JOURNAL)
        btn_journal.clicked.connect(self._review_journal)
        maint_layout.addWidget(btn_journal)

        btn_trim = QPushButton(self.tr("Review SSD Trim"))
        btn_trim.setAccessibleName(self.tr("Review SSD Trim in Action Center"))
        btn_trim.setObjectName("maintReviewFstrim")
        btn_trim.clicked.connect(lambda: self.actionCenterRequested.emit("fstrim-all", {}))
        maint_layout.addWidget(btn_trim)

        btn_rpmdb = QPushButton(self.tr("Rebuild RPM Database"))
        btn_rpmdb.setAccessibleName(self.tr("Rebuild RPM Database"))
        btn_rpmdb.clicked.connect(self._show_rpmdb_manual_guidance)
        maint_layout.addWidget(btn_rpmdb)

        ts_layout = QHBoxLayout()
        btn_check_ts = QPushButton(self.tr("Check for Timeshift Snapshots"))
        btn_check_ts.setAccessibleName(self.tr("Check for Timeshift Snapshots"))
        btn_check_ts.clicked.connect(self.check_timeshift)
        ts_layout.addWidget(btn_check_ts)
        maint_layout.addLayout(ts_layout)

        self.advanced_cleanup = DetailsDisclosure(
            summary=self.tr("Show additional cleanup choices")
        )
        self.advanced_cleanup.setObjectName("cleanupAdvancedDisclosure")
        self.advanced_cleanup.add_widget(maint_group)
        layout.addWidget(self.advanced_cleanup)

        preview_group = QGroupBox(self.tr("Reclaim Preview"))
        preview_layout = QVBoxLayout(preview_group)
        preview_intro = QLabel(
            self.tr("Analyze package-cache and journal sizes without deleting anything. Recovery points are always managed separately.")
        )
        preview_intro.setWordWrap(True)
        preview_layout.addWidget(preview_intro)
        self.reclaim_banner = ResultBanner(
            self.tr("Reclaim analysis"),
            self.tr("Select Analyze Reclaimable Space to collect bounded size estimates."),
        )
        self.reclaim_result = self.reclaim_banner.message_label
        self.reclaim_result.setAccessibleName(self.tr("Reclaim analysis result"))
        preview_layout.addWidget(self.reclaim_banner)
        self.reclaim_button = QPushButton(self.tr("Analyze Reclaimable Space"))
        self.reclaim_button.clicked.connect(self._analyze_reclaim)
        preview_layout.addWidget(self.reclaim_button)
        layout.insertWidget(0, preview_group)
        self.add_output_disclosure(layout, self.tr("Show cleanup command output"))
        self._reclaim_thread = None
        self._reclaim_worker = None

    def _analyze_reclaim(self: typing.Any) -> None:
        if self._reclaim_thread is not None:
            return
        from services.storage import ReclaimProbeService

        self.reclaim_button.setEnabled(False)
        self.reclaim_banner.set_result(
            "info",
            self.tr("Analyzing reclaimable space"),
            self.tr("Collecting bounded package-cache and journal estimates…"),
        )
        thread = QThread(self)
        worker = _ActionCenterOperationWorker(ReclaimProbeService().analyze)
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.finished.connect(self._show_reclaim_analysis)
        worker.finished.connect(thread.quit)
        worker.failed.connect(self._show_reclaim_error)
        worker.failed.connect(thread.quit)
        thread.finished.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)
        thread.finished.connect(self._clear_reclaim_worker)
        self._reclaim_thread = thread
        self._reclaim_worker = worker
        thread.start()

    def _show_reclaim_analysis(self: typing.Any, analysis: typing.Any) -> None:
        lines = []
        for category in analysis.categories:
            size = self.tr("estimate unavailable")
            if category.estimated_bytes is not None:
                size = self._format_bytes(category.estimated_bytes)
            if category.selected_by_default:
                mode = self.tr("safe default")
            elif category.manual_only:
                mode = self.tr("manual guidance")
            else:
                mode = self.tr("not selected")
            lines.append(f"{category.title}: {size} · {category.risk} · {mode}\n{category.guidance}")
        lines.append(self.tr("Selected safe estimate: %s") % self._format_bytes(analysis.estimated_selected_bytes))
        lines.append(
            self.tr(
                "After a cleanup run, analyze again to verify reclaimed space. "
                "Action Center reports any category that only partially completed."
            )
        )
        self.reclaim_banner.set_result(
            "success",
            self.tr("Reclaim analysis complete"),
            "\n\n".join(lines),
        )

    def _show_reclaim_error(self: typing.Any, message: str) -> None:
        self.reclaim_banner.set_result(
            "error",
            self.tr("Reclaim analysis failed"),
            str(message),
        )

    def _clear_reclaim_worker(self: typing.Any) -> None:
        self._reclaim_thread = None
        self._reclaim_worker = None
        self.reclaim_button.setEnabled(True)

    @staticmethod
    def _format_bytes(value: int) -> str:
        size = float(max(0, value))
        for unit in ("B", "KiB", "MiB", "GiB", "TiB"):
            if size < 1024 or unit == "TiB":
                return f"{size:.1f} {unit}"
            size /= 1024
        return "0 B"

    def check_timeshift(self: typing.Any) -> typing.Any:
        if cached_which("timeshift"):
            self.run_command("timeshift", ["--list"], self.tr("Checking Timeshift Snapshots..."))
        else:
            self.append_output(self.tr("Timeshift not found. Please install it for system safety.\n"))

    def run_autoremove(self: typing.Any) -> typing.Any:
        self.actionCenterRequested.emit("autoremove-packages", {})

    def _review_journal(self: typing.Any) -> None:
        value, accepted = QInputDialog.getItem(
            self,
            self.tr("Journal Retention"),
            self.tr("Keep journal entries for:"),
            [self.tr("7 days"), self.tr("14 days"), self.tr("30 days")],
            1,
            False,
        )
        if accepted:
            days = int(str(value).split()[0])
            self.actionCenterRequested.emit("vacuum-journal", {"days": days})

    def _show_rpmdb_manual_guidance(self: typing.Any) -> None:
        QMessageBox.information(
            self,
            self.tr("Manual Troubleshooting Action"),
            self.tr("RPM database repair is available only as a manual high-risk troubleshooting step."),
        )

    def on_command_finished(self: typing.Any, exit_code: typing.Any) -> typing.Any:
        self.append_output(self.tr("\nCommand finished with exit code: {}").format(exit_code))
        if exit_code == 0:
            self.show_success(self.tr("Cleanup completed successfully"))
        else:
            self.show_error(self.tr("Cleanup failed (exit code {})").format(exit_code))



class _OverlaysSubTab(QWidget):
    """Sub-tab for managing rpm-ostree layered packages.

    Only instantiated on Fedora Atomic systems (Silverblue, Kinoite, etc.).
    Preserves every feature from the original OverlaysTab:
    - Info card showing system variant
    - Layered packages list with refresh
    - Remove selected / Reset to base image
    - Pending-reboot warning and reboot button
    """

    actionCenterRequested = pyqtSignal(str, object)

    def __init__(self: typing.Any) -> None:
        super().__init__()
        self._loaded = False
        self.init_ui()

    def showEvent(self: typing.Any, event: typing.Any) -> typing.Any:
        super().showEvent(event)
        if not self._loaded:
            self._loaded = True
            QTimer.singleShot(0, self.refresh_list)

    def init_ui(self: typing.Any) -> typing.Any:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        self.scaffold = PageScaffold(
            self.tr("Atomic Overlays"),
            self.tr("Review layered packages and pending deployments on Atomic Fedora."),
        )
        root.addWidget(self.scaffold)
        layout = self.scaffold.content_layout

        info_frame = QFrame()
        info_frame.setObjectName("maintOverlayInfoFrame")
        info_layout = QVBoxLayout(info_frame)

        variant = SystemManager.get_variant_name()
        info_label = QLabel(self.tr("System: Fedora {} (Immutable)").format(variant))
        info_label.setObjectName("maintOverlayInfoLabel")
        info_layout.addWidget(info_label)

        desc_label = QLabel(self.tr("Layered packages are RPMs installed on top of the base OS image.\nChanges require a reboot to fully apply."))
        desc_label.setObjectName("maintOverlayDesc")
        info_layout.addWidget(desc_label)

        self.reboot_warning = QLabel(self.tr("Pending changes require reboot."))
        self.reboot_warning.setObjectName("maintRebootWarning")
        self.reboot_warning.setVisible(False)
        info_layout.addWidget(self.reboot_warning)

        layout.addWidget(info_frame)

        packages_group = QGroupBox(self.tr("Layered Packages"))
        packages_layout = QVBoxLayout(packages_group)

        self.packages_list = QListWidget()
        self.packages_list.setMinimumHeight(200)
        packages_layout.addWidget(self.packages_list)

        btn_layout = QHBoxLayout()

        self.btn_refresh = QPushButton(self.tr("Refresh"))
        self.btn_refresh.setAccessibleName(self.tr("Refresh"))
        self.btn_refresh.clicked.connect(self.refresh_list)
        btn_layout.addWidget(self.btn_refresh)

        self.btn_remove = QPushButton(self.tr("Remove Selected"))
        self.btn_remove.setAccessibleName(self.tr("Remove Selected"))
        self.btn_remove.setObjectName("dangerAction")
        self.btn_remove.clicked.connect(self.remove_selected)
        btn_layout.addWidget(self.btn_remove)

        btn_layout.addStretch()

        self.btn_reset = QPushButton(self.tr("Reset to Base Image"))
        self.btn_reset.setAccessibleName(self.tr("Reset to Base Image"))
        self.btn_reset.setObjectName("dangerAction")
        self.btn_reset.clicked.connect(self.reset_to_base)
        btn_layout.addWidget(self.btn_reset)

        packages_layout.addLayout(btn_layout)
        layout.addWidget(packages_group)

        self.btn_reboot = QPushButton(self.tr("Reboot to Apply Changes"))
        self.btn_reboot.setAccessibleName(self.tr("Reboot to Apply Changes"))
        self.btn_reboot.setObjectName("maintRebootBtn")
        self.btn_reboot.clicked.connect(self.reboot_system)
        self.btn_reboot.setVisible(False)
        layout.addWidget(self.btn_reboot)

        layout.addStretch()

    def refresh_list(self: typing.Any) -> typing.Any:
        """Refresh the list of layered packages."""
        self.packages_list.clear()

        packages = SystemManager.get_layered_packages()

        if packages:
            for pkg in packages:
                item = QListWidgetItem(str(pkg))
                self.packages_list.addItem(item)
        else:
            item = QListWidgetItem(self.tr("No layered packages (clean base image)"))
            item.setForeground(semantic_qcolor("text_muted"))
            self.packages_list.addItem(item)

        has_pending = SystemManager.has_pending_deployment()
        self.reboot_warning.setVisible(has_pending is True or has_pending is None)
        self.btn_reboot.setVisible(has_pending is True)
        if has_pending is None:
            self.reboot_warning.setText(
                self.tr("Reboot status could not be verified. Inspect the deployment before continuing.")
            )

    def remove_selected(self: typing.Any) -> typing.Any:
        """Remove the selected layered package."""
        selected = self.packages_list.currentItem()
        if not selected:
            QMessageBox.warning(
                self,
                self.tr("No Selection"),
                self.tr("Please select a package to remove."),
            )
            return

        pkg_name = selected.text().removeprefix("\U0001f4e6 ").strip()

        if "No layered" in pkg_name:
            return

        reply = QMessageBox.question(
            self,
            self.tr("Confirm Removal"),
            self.tr("Remove '{}' from system overlays?\n\nThis requires a reboot.").format(pkg_name),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )

        if reply == QMessageBox.StandardButton.Yes:
            self.actionCenterRequested.emit(
                "legacy-ui-manual-review",
                {
                    "description": (
                        "Review rpm-ostree uninstall for the selected layered package: "
                        f"{pkg_name}"
                    )
                },
            )

    def reset_to_base(self: typing.Any) -> typing.Any:
        """Reset to base image, removing all layered packages."""
        reply = QMessageBox.warning(
            self,
            self.tr("Reset to Base Image"),
            self.tr("This will REMOVE ALL layered packages and reset to the clean base image.\n\nAre you absolutely sure?"),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )

        if reply == QMessageBox.StandardButton.Yes:
            QMessageBox.information(
                self,
                self.tr("Manual review required"),
                self.tr("Resetting every overlay has no bounded Action Center definition. Review rpm-ostree status and perform the reset manually."),
            )

    def reboot_system(self: typing.Any) -> typing.Any:
        """Offer to reboot the system."""
        reply = QMessageBox.question(
            self,
            self.tr("Reboot Now?"),
            self.tr("Reboot now to apply pending changes?"),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )

        if reply == QMessageBox.StandardButton.Yes:
            QMessageBox.information(
                self,
                self.tr("Reboot remains manual"),
                self.tr("Loofi never initiates a reboot. Use the desktop session controls when ready."),
            )
