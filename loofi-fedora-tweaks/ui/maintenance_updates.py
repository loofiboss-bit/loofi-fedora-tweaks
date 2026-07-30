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
        self.package_manager = SystemManager.get_package_manager()
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        self.scaffold = PageScaffold(
            self.tr("Updates"),
            self.tr("Review system, Flatpak, and firmware updates before applying changes."),
        )
        root.addWidget(self.scaffold)
        layout = self.scaffold.content_layout

        update_guidance = QLabel(
            self.tr(
                "Review system, Flatpak, and firmware updates together. Traditional Fedora "
                "updates the current system; Atomic Fedora creates a new rpm-ostree deployment "
                "and may require a reboot."
            )
        )
        update_guidance.setWordWrap(True)
        layout.addWidget(update_guidance)

        self.btn_update_all = QPushButton(self.tr("Review updates independently"))
        self.btn_update_all.setAccessibleName(self.tr("Review independent update plans"))
        self.btn_update_all.setObjectName("maintUpdateAllBtn")
        self.btn_update_all.clicked.connect(self.run_update_all)
        layout.addWidget(self.btn_update_all)

        # Individual Update Buttons
        btn_layout = QHBoxLayout()

        if self.package_manager == "rpm-ostree":
            self.btn_dnf = QPushButton(self.tr("Review System Update (rpm-ostree)"))
        else:
            self.btn_dnf = QPushButton(self.tr("Review System Update (DNF)"))
        self.btn_dnf.setAccessibleName(self.tr("Review System Update"))
        self.btn_dnf.clicked.connect(self.run_dnf_update)
        btn_layout.addWidget(self.btn_dnf)

        self.btn_flatpak = QPushButton(self.tr("Review Flatpak Updates"))
        self.btn_flatpak.setAccessibleName(self.tr("Review Flatpak Updates"))
        self.btn_flatpak.clicked.connect(self.run_flatpak_update)
        btn_layout.addWidget(self.btn_flatpak)

        self.btn_fw = QPushButton(self.tr("Review Firmware Updates"))
        self.btn_fw.setAccessibleName(self.tr("Review Firmware Updates"))
        self.btn_fw.clicked.connect(self.run_fw_update)
        btn_layout.addWidget(self.btn_fw)

        layout.addLayout(btn_layout)

        # Kernel Management Group
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

        # Preserve the Smart Updates backend as one advanced section inside
        # the canonical Updates workflow instead of a duplicate top-level tab.
        self.advanced_group = QGroupBox(self.tr("Advanced Options"))
        self.advanced_group.setObjectName("maintAdvancedUpdateOptions")
        self.advanced_group.setCheckable(True)
        self.advanced_group.setChecked(False)
        advanced_layout = QVBoxLayout(self.advanced_group)
        self.advanced_updates = _SmartUpdatesSubTab()
        self.advanced_updates.setVisible(False)
        self.advanced_group.toggled.connect(self.advanced_updates.setVisible)
        advanced_layout.addWidget(self.advanced_updates)
        layout.addWidget(self.advanced_group)

        # Progress Bar
        self.action_progress = ActionProgress(self.tr("Waiting for an update action."))
        self.progress_bar = self.action_progress.progress_bar
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(True)
        self.progress_bar.setFormat("%p% - %v")
        layout.addWidget(self.action_progress)

        # Use BaseTab's output_area and runner (no shadowing)
        self.output_area.setAccessibleName(self.tr("Update output"))
        self.output_area.setMaximumHeight(16777215)
        self.add_output_disclosure(layout, self.tr("Show update command output"))

        self.runner.progress_update.connect(self.update_progress)

    def reveal_advanced_options(self: typing.Any) -> None:
        """Reveal the former Smart Updates surface after a compatible deep link."""
        self.advanced_group.setChecked(True)

    # -- Progress ----------------------------------------------------------

    def update_progress(self: typing.Any, percent: typing.Any, status: typing.Any) -> typing.Any:
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
        self.actionCenterRequested.emit("update-fedora-system", {})

    def run_flatpak_update(self: typing.Any) -> typing.Any:
        self.actionCenterRequested.emit("update-flatpaks", {})

    def run_fw_update(self: typing.Any) -> typing.Any:
        self.actionCenterRequested.emit("update-firmware", {})

    # -- Update All (sequential queue) -------------------------------------

    def run_update_all(self: typing.Any) -> typing.Any:
        self.output_area.setPlainText(
            self.tr("Assurance keeps Fedora, Flatpak, and firmware updates independent. Choose one review button to create one auditable plan.")
        )

    # -- Helpers -----------------------------------------------------------

    def start_process(self: typing.Any) -> typing.Any:
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

        self.btn_dnf.setEnabled(True)
        self.btn_flatpak.setEnabled(True)
        self.btn_fw.setEnabled(True)
        self.btn_update_all.setEnabled(True)
        self.progress_bar.setValue(100)
        self.progress_bar.setFormat(self.tr("100% - Done"))
        self.action_progress.status_label.setText(self.tr("Advanced operation completed") if exit_code == 0 else self.tr("Advanced operation failed"))

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
        cleanup_group = QGroupBox(self.tr("Cleanup"))
        cleanup_layout = QVBoxLayout()
        cleanup_group.setLayout(cleanup_layout)

        btn_dnf_clean = QPushButton(self.tr("Review DNF Cache Cleanup"))
        btn_dnf_clean.setAccessibleName(self.tr("Review DNF Cache Cleanup in Action Center"))
        btn_dnf_clean.setToolTip(MAINT_CLEANUP)
        btn_dnf_clean.setObjectName("maintReviewDnfClean")
        btn_dnf_clean.clicked.connect(lambda: self.actionCenterRequested.emit("dnf-clean-all", {}))
        cleanup_layout.addWidget(btn_dnf_clean)

        btn_autoremove = QPushButton(self.tr("Review Unused Packages"))
        btn_autoremove.setAccessibleName(self.tr("Remove Unused Packages"))
        btn_autoremove.setObjectName("maintAutoremoveBtn")
        btn_autoremove.setToolTip(MAINT_ORPHANS)
        btn_autoremove.clicked.connect(self.run_autoremove)
        cleanup_layout.addWidget(btn_autoremove)

        btn_journal = QPushButton(self.tr("Review Journal Retention"))
        btn_journal.setAccessibleName(self.tr("Vacuum Journal"))
        btn_journal.setToolTip(MAINT_JOURNAL)
        btn_journal.clicked.connect(self._review_journal)
        cleanup_layout.addWidget(btn_journal)

        layout.addWidget(cleanup_group)

        # Maintenance Group
        maint_group = QGroupBox(self.tr("Maintenance"))
        maint_layout = QVBoxLayout()
        maint_group.setLayout(maint_layout)

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

        layout.addWidget(maint_group)

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
        layout.addWidget(preview_group)
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
            mode = self.tr("manual-only") if category.manual_only else self.tr("reviewable")
            lines.append(f"{category.title}: {size} · {category.risk} · {mode}\n{category.guidance}")
        lines.append(self.tr("Selected safe estimate: %s") % self._format_bytes(analysis.estimated_selected_bytes))
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
        self.reboot_warning.setVisible(has_pending)
        self.btn_reboot.setVisible(has_pending)

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
                "remove-application",
                {"source": "fedora", "package_id": pkg_name},
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
# Smart Updates sub-tab
# ---------------------------------------------------------------------------


class _SmartUpdatesSubTab(QWidget):
    """Sub-tab for advanced update management.

    Uses UpdateManager to check updates, preview conflicts,
    schedule updates, and rollback.
    """

    def __init__(self: typing.Any) -> None:
        super().__init__()
        self._loaded = False
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # Check Updates
        check_group = QGroupBox(self.tr("Available Updates"))
        check_layout = QVBoxLayout(check_group)

        btn_row = QHBoxLayout()
        self.btn_check = QPushButton(self.tr("Check for Updates"))
        self.btn_check.setAccessibleName(self.tr("Check for Updates"))
        self.btn_check.clicked.connect(self._check_updates)
        btn_row.addWidget(self.btn_check)

        self.btn_conflicts = QPushButton(self.tr("Preview Conflicts"))
        self.btn_conflicts.setAccessibleName(self.tr("Preview Conflicts"))
        self.btn_conflicts.clicked.connect(self._preview_conflicts)
        btn_row.addWidget(self.btn_conflicts)
        btn_row.addStretch()
        check_layout.addLayout(btn_row)

        self.updates_list = QListWidget()
        self.updates_list.setMinimumHeight(120)
        check_layout.addWidget(self.updates_list)
        layout.addWidget(check_group)

        # Schedule & Rollback
        actions_group = QGroupBox(self.tr("Actions"))
        actions_layout = QVBoxLayout(actions_group)

        schedule_row = QHBoxLayout()
        self.btn_schedule = QPushButton(self.tr("Schedule Update (02:00)"))
        self.btn_schedule.setAccessibleName(self.tr("Schedule Update"))
        self.btn_schedule.clicked.connect(self._schedule_update)
        schedule_row.addWidget(self.btn_schedule)

        self.btn_rollback = QPushButton(self.tr("Rollback Last Update"))
        self.btn_rollback.setAccessibleName(self.tr("Rollback Last Update"))
        self.btn_rollback.setObjectName("dangerAction")
        self.btn_rollback.clicked.connect(self._rollback_last)
        schedule_row.addWidget(self.btn_rollback)
        schedule_row.addStretch()
        actions_layout.addLayout(schedule_row)
        layout.addWidget(actions_group)

        # Output
        self.output_area = QTextEdit()
        self.output_area.setReadOnly(True)
        self.output_area.setMaximumHeight(150)
        self.output_area.setAccessibleName(self.tr("Smart updates output"))
        self.output_details = DetailsDisclosure(summary=self.tr("Show smart update output"))
        self.output_details.add_widget(self.output_area)
        layout.addWidget(self.output_details)

        layout.addStretch()

    def _append_output(self: typing.Any, text: typing.Any) -> typing.Any:
        self.output_area.moveCursor(self.output_area.textCursor().MoveOperation.End)
        self.output_area.insertPlainText(text)
        self.output_area.moveCursor(self.output_area.textCursor().MoveOperation.End)

    def _check_updates(self: typing.Any) -> typing.Any:
        """Check for available updates."""
        try:
            from utils.update_manager import UpdateManager

            updates = UpdateManager.check_updates()
            self.updates_list.clear()
            for u in updates:
                old_version = f"{u.old_version} → " if u.old_version else ""
                source = u.repo or u.severity
                item = QListWidgetItem(f"{u.name}  {old_version}{u.version}  ({source})")
                self.updates_list.addItem(item)
            if not updates:
                self.updates_list.addItem(QListWidgetItem(self.tr("System is up to date.")))
            self._append_output(self.tr("Found {} available updates.\n").format(len(updates)))
        except (RuntimeError, OSError, ValueError) as e:
            self._append_output(f"[ERROR] {e}\n")

    def _preview_conflicts(self: typing.Any) -> typing.Any:
        try:
            from utils.update_manager import UpdateManager

            conflicts = UpdateManager.preview_conflicts()
            self.updates_list.clear()
            for c in conflicts:
                item = QListWidgetItem(f"WARNING {c.package}: {c.reason}")
                self.updates_list.addItem(item)
            if not conflicts:
                self.updates_list.addItem(QListWidgetItem(self.tr("No conflicts detected.")))
        except (RuntimeError, OSError, ValueError) as e:
            self._append_output(f"[ERROR] {e}\n")

    def _schedule_update(self: typing.Any) -> typing.Any:
        self._append_output(
            self.tr(
                "Unattended update execution is disabled. Create and review the Fedora, "
                "Flatpak, and firmware plans in Action Center when you are present.\n"
            )
        )

    def _rollback_last(self: typing.Any) -> typing.Any:
        self._append_output(self.tr("Rollback remains manual-only. Loofi never initiates rollback or reboot automatically.\n"))


# ---------------------------------------------------------------------------
# Upgrade Assistant sub-tab
# ---------------------------------------------------------------------------


class _UpgradeAssistantSubTab(QWidget):
    """Guided release planning entry point backed by ReleaseReadiness."""

    def __init__(self: typing.Any) -> None:
        super().__init__()
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        self.scaffold = PageScaffold(
            self.tr("Fedora Upgrade"),
            self.tr("Review release readiness and export support evidence before upgrading Fedora."),
        )
        root.addWidget(self.scaffold)
        layout = self.scaffold.content_layout

        intro = QLabel(
            self.tr(
                "Plan Fedora release work with read-only checks, risk explanations, "
                "command previews, confirmed actions, verification, and support export."
            )
        )
        intro.setWordWrap(True)
        layout.addWidget(intro)

        from core.diagnostics.release_readiness import ReleaseReadiness

        for target in ReleaseReadiness.list_targets():
            group = QGroupBox(target.label)
            group_layout = QVBoxLayout(group)
            summary = QLabel(f"{target.status_label} · {target.release_phase}")
            summary.setWordWrap(True)
            group_layout.addWidget(summary)

            if target.important_changes:
                changes = QLabel("\n".join(f"- {change.title}: {change.summary}" for change in target.important_changes))
                changes.setWordWrap(True)
                group_layout.addWidget(changes)

            actions = QHBoxLayout()
            open_button = QPushButton(self.tr("Open Guided Check"))
            open_button.clicked.connect(lambda _checked=False, key=target.key: self._open_readiness(key))
            actions.addWidget(open_button)

            export_button = QPushButton(self.tr("Export Bundle"))
            export_button.clicked.connect(lambda _checked=False, key=target.key: self._export_bundle(key))
            actions.addWidget(export_button)
            actions.addStretch()
            group_layout.addLayout(actions)

            layout.addWidget(group)

        layout.addStretch()

    def _open_readiness(self: typing.Any, target_key: str) -> None:
        from ui.release_readiness_dialog import ReleaseReadinessDialog

        dialog = ReleaseReadinessDialog(target_key, self)
        dialog.exec()

    def _export_bundle(self: typing.Any, target_key: str) -> None:
        from core.export.support_bundle import SupportBundleWriter

        path = f"loofi-readiness-{target_key}.json"
        try:
            SupportBundleWriter.save_json(path, target=target_key)
            QMessageBox.information(self, self.tr("Export Complete"), self.tr("Saved support bundle to %1").replace("%1", path))
        except (OSError, RuntimeError, ValueError) as exc:
            QMessageBox.critical(self, self.tr("Export Failed"), str(exc))


# ---------------------------------------------------------------------------
# Action Center sub-tab
# ---------------------------------------------------------------------------
