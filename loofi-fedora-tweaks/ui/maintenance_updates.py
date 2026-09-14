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

# ---------------------------------------------------------------------------
# Sub-tab: Updates
# ---------------------------------------------------------------------------


class _UpdatesSubTab(BaseTab):
    """Preview-first entry point for independent verified update plans."""

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
            self.tr("Review system, Flatpak, and firmware updates before applying changes."),
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
        """Add risk and state context before any plan handoff."""

        update_guidance = QLabel(self._update_guidance())
        update_guidance.setWordWrap(True)
        self.plan_details = DetailsDisclosure(summary=self.tr("How update plans work"))
        self.plan_details.add_widget(update_guidance)
        layout.addWidget(self.plan_details)
        self.update_state = FeedbackBanner(
            self.tr("Ready to review updates"),
            self.tr("Choose System, Flatpak, or Firmware to create one reviewable plan."),
            kind="info",
        )
        self.update_state.setObjectName("updatesState")
        self.update_state.setProperty("updateLifecycleState", "idle")
        layout.addWidget(self.update_state)
        self.update_state.hide()

        self.update_summary = TaskSummary(
            self.tr("Update plan summary"),
            self.tr("One source per plan keeps package lists, restart impact, and verification explicit."),
            status=self.tr("Awaiting source selection"),
        )
        self.update_summary.add_fact(self.tr("System mode"), self.package_manager)
        self.update_summary.add_fact(self.tr("Execution"), self.tr("Action Center only"))
        self.update_summary.add_fact(self.tr("Verification"), self.tr("Required after execution"))
        self.plan_details.add_widget(self.update_summary)

        self.btn_update_all = QuietButton(
            self.tr("Why separate plans?"),
            description=self.tr("Explain why update sources are reviewed independently."),
        )
        self.btn_update_all.setAccessibleName(self.tr("Explain independent update plans"))
        self.btn_update_all.setObjectName("maintUpdateAllBtn")
        self.btn_update_all.clicked.connect(self.run_update_all)
        self.plan_details.add_widget(self.btn_update_all)

    def _add_source_actions(self, layout: QVBoxLayout) -> None:
        """Add one explicit select-then-review action per update source."""
        if self.deployment_backend == "rpm_ostree":
            self.btn_dnf = SecondaryButton(self.tr("Review System Update (rpm-ostree)"))
        elif self.deployment_backend == "bootc":
            self.btn_dnf = SecondaryButton(self.tr("System updates require manual bootc guidance"))
        elif self.deployment_backend == "unknown":
            self.btn_dnf = SecondaryButton(self.tr("System update backend is unknown"))
        else:
            self.btn_dnf = SecondaryButton(self.tr("Review System Update (DNF)"))
        self.btn_dnf.setAccessibleName(self.tr("Select System updates"))
        self.btn_dnf.setProperty("sourceId", "system")
        self.btn_dnf.clicked.connect(lambda _checked=False: self._select_or_review_source("system"))

        self.btn_flatpak = SecondaryButton(self.tr("Select Flatpak updates"))
        self.btn_flatpak.setAccessibleName(self.tr("Select Flatpak updates"))
        self.btn_flatpak.setProperty("sourceId", "flatpak")
        self.btn_flatpak.clicked.connect(lambda _checked=False: self._select_or_review_source("flatpak"))

        self.btn_fw = SecondaryButton(self.tr("Select Firmware updates"))
        self.btn_fw.setAccessibleName(self.tr("Select Firmware updates"))
        self.btn_fw.setProperty("sourceId", "firmware")
        self.btn_fw.clicked.connect(lambda _checked=False: self._select_or_review_source("firmware"))

        # A source cannot enter the Action Center until the explicit read-only
        # overview has established a fresh result for it.
        for button in (self.btn_dnf, self.btn_flatpak, self.btn_fw):
            button.setEnabled(False)

        overview_layout = self.overview.layout()
        if isinstance(overview_layout, QVBoxLayout):
            for source, button in (("system", self.btn_dnf), ("flatpak", self.btn_flatpak), ("firmware", self.btn_fw)):
                overview_layout.insertWidget(overview_layout.indexOf(self.overview.rows[source][2]), button)

    def _on_overview_snapshot(self, snapshot: object) -> None:
        """Enable source review only after a fresh, truthful source check."""
        results = {
            str(getattr(result, "source", "")): result
            for result in getattr(snapshot, "sources", ())
        }
        backend_value = getattr(snapshot, "backend", "unknown")
        backend = str(getattr(backend_value, "value", backend_value))
        support_status = str(getattr(snapshot, "support_status", "unknown"))
        review_policy_allowed = (
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
            ready = fresh_result and review_policy_allowed
            button.setEnabled(ready)
            button.setProperty("sourceStatus", status)
            button.setProperty("reviewPolicyAllowed", review_policy_allowed)
            button.setProperty("readyForReview", ready)
            if source != self._selected_source:
                label = {
                    "system": self.tr("Review System"),
                    "flatpak": self.tr("Review Flatpak"),
                    "firmware": self.tr("Review Firmware"),
                }[source] if ready else {
                    "system": self.tr("Select System"),
                    "flatpak": self.tr("Select Flatpak"),
                    "firmware": self.tr("Select Firmware"),
                }[source]
                button.setText(
                    self.tr("%1 updates").replace("%1", label)
                )
                button.setAccessibleName(
                    self.tr("Review %1 updates" if ready else "Select %1 updates").replace("%1", label)
                )

    def _select_or_review_source(self, source: str) -> None:
        """Make source selection a visible step before Action Center review."""
        buttons = {
            "system": self.btn_dnf,
            "flatpak": self.btn_flatpak,
            "firmware": self.btn_fw,
        }
        button = buttons.get(source)
        if button is None or not button.isEnabled():
            return
        if button.property("readyForReview") is True:
            {
                "system": self.run_dnf_update,
                "flatpak": self.run_flatpak_update,
                "firmware": self.run_fw_update,
            }[source]()
            return
        if self._selected_source != source:
            previous = buttons.get(self._selected_source or "")
            if previous is not None:
                previous.setText(
                    self.tr("Select %1 updates").replace(
                        "%1",
                        {
                            "system": self.tr("System"),
                            "flatpak": self.tr("Flatpak"),
                            "firmware": self.tr("Firmware"),
                        }[str(previous.property("sourceId"))],
                    )
                )
            self._selected_source = source
            source_label = {
                "system": self.tr("System"),
                "flatpak": self.tr("Flatpak"),
                "firmware": self.tr("Firmware"),
            }[source]
            button.setText(
                self.tr("Review %1 changes").replace("%1", source_label)
            )
            button.setAccessibleName(
                self.tr("Review %1 changes").replace("%1", source_label)
            )
            self._set_update_state(
                "source_selected",
                self.tr("Source selected"),
                self.tr("%1 is selected. Choose Review changes to inspect the exact plan.").replace(
                    "%1", source_label
                ),
            )
            self.update_summary.set_status(
                self.tr("Source selected"),
                kind="info",
                description=source_label,
            )
            return
        {
            "system": self.run_dnf_update,
            "flatpak": self.run_flatpak_update,
            "firmware": self.run_fw_update,
        }[source]()

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
                "System updates create a new Atomic deployment. Review the plan, restart when requested, "
                "then let Action Center verify the new deployment."
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
            "System updates change the current Fedora installation. Review one source at a time, "
            "then let Action Center verify the result."
        ))

    def _set_update_state(
        self,
        lifecycle: str,
        title: str,
        message: str,
        *,
        kind: str = "info",
    ) -> None:
        """Present an explicit update lifecycle without owning execution."""
        self.update_state.show()
        self.update_state.setProperty("updateLifecycleState", lifecycle)
        self.update_state.set_result(kind, title, message)
        status_kind = {
            "succeeded": "success",
            "failed": "error",
            "cancelled": "warning",
            "unavailable": "warning",
        }.get(lifecycle, "info")
        self.update_summary.set_status(title, kind=status_kind, description=message)

    def set_checking(self, source: str) -> None:
        # A new inspection invalidates the previous selection until the fresh
        # source result is available. This keeps the review handoff truthful.
        self._selected_source = None
        for button in (self.btn_dnf, self.btn_flatpak, self.btn_fw):
            button.setEnabled(False)
        self._set_update_state(
            "checking",
            self.tr("Checking update status"),
            self.tr("Reading available updates for %1 without applying changes.").replace("%1", source),
        )

    def set_updates_available(self, source: str, count: int) -> None:
        # Keep the helper useful for injected check services and tests: an
        # explicit availability result is enough to unlock review.
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
                if self._selected_source != source_id:
                    button.setText(
                        self.tr("Review %1 updates" if ready else "Select %1 updates")
                        .replace("%1", label)
                    )
                    button.setAccessibleName(
                        self.tr("Review %1 updates" if ready else "Select %1 updates")
                        .replace("%1", label)
                    )
        self._set_update_state(
            "available",
            self.tr("Updates available"),
            self.tr("%1 has %2 available update(s). Review the source before creating a plan.")
            .replace("%1", source)
            .replace("%2", str(max(0, count))),
        )

    # -- Progress ----------------------------------------------------------

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

    # -- Individual update actions -----------------------------------------

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
        update_state = getattr(self, "update_state", None)
        if update_state is not None:
            update_state.show()
            update_state.setProperty("updateLifecycleState", "review")
            update_state.set_result(
                "info",
                translate("Opening Action Center"),
                translate(
                    "Source: %1 · Restart: %2 · Verification: required after the reviewed plan runs."
                )
                .replace("%1", source)
                .replace("%2", restart_requirement),
            )
        update_summary = getattr(self, "update_summary", None)
        if update_summary is not None:
            update_summary.set_status(
                translate("Plan review requested"),
                kind="info",
                description=source,
            )
        self.actionCenterRequested.emit(action_id, {})

    # -- Update All (sequential queue) -------------------------------------

    def run_update_all(self: typing.Any) -> typing.Any:
        update_state = getattr(self, "update_state", None)
        if update_state is not None:
            update_state.set_result(
                "info",
                self.tr("Choose one update source"),
                self.tr("Separate plans keep package lists, restart requirements, and verification clear."),
            )
        self.output_area.setPlainText(
            self.tr("Choose one review button to create one Action Center plan.")
        )

    # -- Helpers -----------------------------------------------------------

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

        # Command completion must not bypass the preview gate. Only
        # sources with a fresh, supported overview result become selectable.
        # The ``readyForReview`` property is also absent on legacy injected
        # button doubles, where the historical helper contract is retained.
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


# ---------------------------------------------------------------------------
# Sub-tab: Cleanup
# ---------------------------------------------------------------------------


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

        # Use BaseTab's output_area and runner (no shadowing)
        self.output_area.setAccessibleName(self.tr("Cleanup output"))

        # Cleanup Group
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

        # Maintenance Group
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

        # Timeshift Check
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


# ---------------------------------------------------------------------------
# Sub-tab: Overlays (Atomic / rpm-ostree only)
# ---------------------------------------------------------------------------


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

        # Info Card
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

        # Pending Reboot Warning
        self.reboot_warning = QLabel(self.tr("Pending changes require reboot."))
        self.reboot_warning.setObjectName("maintRebootWarning")
        self.reboot_warning.setVisible(False)
        info_layout.addWidget(self.reboot_warning)

        layout.addWidget(info_frame)

        # Layered Packages List
        packages_group = QGroupBox(self.tr("Layered Packages"))
        packages_layout = QVBoxLayout(packages_group)

        self.packages_list = QListWidget()
        self.packages_list.setMinimumHeight(200)
        packages_layout.addWidget(self.packages_list)

        # Buttons
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

        # Reboot Button
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

        # Check for pending reboot
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

        # Accept the pre-v15 decorated value if an existing widget or plugin
        # supplies it, while new rows remain plain text.
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


# ---------------------------------------------------------------------------
# Action Center sub-tab
# ---------------------------------------------------------------------------
