"""
Maintenance Tab - Consolidated tab merging Updates, Cleanup, and Overlays.
Part of v11.0 "Aurora Update".

Uses QTabWidget for sub-navigation to preserve all features from the
original UpdatesTab, CleanupTab, and OverlaysTab.
The Overlays sub-tab is only shown on Atomic (rpm-ostree) systems.
"""

from services.system.system import cached_which

from core.plugins.metadata import PluginMetadata
from PyQt6.QtCore import QObject, QThread, QTimer, pyqtSignal
from PyQt6.QtWidgets import (
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)
from services.system import SystemManager
from utils.command_runner import CommandRunner
from utils.commands import PrivilegedCommand

from ui.base_tab import BaseTab
from ui.design import semantic_qcolor
from ui.shared_states import ActionProgress, DetailsDisclosure, ResultBanner
from ui.tab_utils import configure_top_tabs
from ui.tooltips import MAINT_CLEANUP, MAINT_JOURNAL, MAINT_ORPHANS

# ---------------------------------------------------------------------------
# Sub-tab: Updates
# ---------------------------------------------------------------------------


class _UpdatesSubTab(BaseTab):
    """Sub-tab containing all system update functionality.

    Preserves every feature from the original UpdatesTab:
    - Update All (DNF + Flatpak + Firmware) with sequential queue
    - Individual DNF / Flatpak / Firmware update buttons
    - Kernel Management (list / remove old kernels)
    - Progress bar with status text
    - Output log
    """

    def __init__(self):
        super().__init__()
        self.package_manager = SystemManager.get_package_manager()
        layout = QVBoxLayout()
        self.setLayout(layout)

        # Header
        header = QLabel(self.tr("System Updates"))
        header.setObjectName("header")
        layout.addWidget(header)

        update_guidance = QLabel(self.tr(
            "Review system, Flatpak, and firmware updates together. Traditional Fedora "
            "updates the current system; Atomic Fedora creates a new rpm-ostree deployment "
            "and may require a reboot."
        ))
        update_guidance.setWordWrap(True)
        layout.addWidget(update_guidance)

        # Update All Button (Prominent)
        self.btn_update_all = QPushButton(self.tr("Update All (DNF + Flatpak + Firmware)"))
        self.btn_update_all.setAccessibleName(self.tr("Update All (DNF + Flatpak + Firmware)"))
        self.btn_update_all.setObjectName("maintUpdateAllBtn")
        self.btn_update_all.clicked.connect(self.run_update_all)
        layout.addWidget(self.btn_update_all)

        # Individual Update Buttons
        btn_layout = QHBoxLayout()

        if self.package_manager == "rpm-ostree":
            self.btn_dnf = QPushButton(self.tr("Update System (rpm-ostree)"))
        else:
            self.btn_dnf = QPushButton(self.tr("Update System (DNF)"))
        self.btn_dnf.setAccessibleName(self.tr("Update System"))
        self.btn_dnf.clicked.connect(self.run_dnf_update)
        btn_layout.addWidget(self.btn_dnf)

        self.btn_flatpak = QPushButton(self.tr("Update Flatpaks"))
        self.btn_flatpak.setAccessibleName(self.tr("Update Flatpaks"))
        self.btn_flatpak.clicked.connect(self.run_flatpak_update)
        btn_layout.addWidget(self.btn_flatpak)

        self.btn_fw = QPushButton(self.tr("Update Firmware"))
        self.btn_fw.setAccessibleName(self.tr("Update Firmware"))
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
            lambda: self.run_single_command(
                *PrivilegedCommand.dnf("remove", flags=["--oldinstallonly"]),
            )
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
        layout.addWidget(self.output_area)

        self.runner.progress_update.connect(self.update_progress)

        self.update_queue = []
        self.current_update_index = 0

    def reveal_advanced_options(self) -> None:
        """Reveal the former Smart Updates surface after a compatible deep link."""
        self.advanced_group.setChecked(True)

    # -- Progress ----------------------------------------------------------

    def update_progress(self, percent, status):
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

    @staticmethod
    def _system_update_step(package_manager):
        if package_manager == "rpm-ostree":
            return ("pkexec", ["rpm-ostree", "upgrade"], "Starting System Upgrade...")
        return (
            "pkexec",
            [package_manager, "update", "-y"],
            "Starting System Update...",
        )

    def run_dnf_update(self):
        from services.security import SafetyManager

        if self.package_manager == "dnf" and SafetyManager.check_dnf_lock():
            QMessageBox.warning(
                self,
                self.tr("Update Locked"),
                self.tr("Another package manager (DNF/RPM) is currently running.\nPlease wait for it to finish."),
            )
            return

        action_name = self.tr("System Upgrade (rpm-ostree)") if self.package_manager == "rpm-ostree" else self.tr("System Update (DNF)")

        if not SafetyManager.confirm_action(self, action_name):
            return

        self.start_process()
        cmd, args, desc = self._system_update_step(self.package_manager)
        self.append_output(self.tr(desc) + "\n")
        self.runner.run_command(cmd, args)

    def run_flatpak_update(self):
        self.start_process()
        self.append_output(self.tr("Starting Flatpak Update...\n"))
        self.runner.run_command("flatpak", ["update", "-y"])

    def run_fw_update(self):
        from services.security import SafetyManager

        if not SafetyManager.confirm_action(self, self.tr("Firmware Update")):
            return

        self.start_process()
        self.append_output(self.tr("Starting Firmware Update...\n"))
        self.runner.run_command("pkexec", ["fwupdmgr", "update", "-y"])

    # -- Update All (sequential queue) -------------------------------------

    def run_update_all(self):
        from services.security import SafetyManager

        if self.package_manager == "dnf" and SafetyManager.check_dnf_lock():
            QMessageBox.warning(
                self,
                self.tr("Update Locked"),
                self.tr("Another package manager is running.\nPlease wait."),
            )
            return

        if not SafetyManager.confirm_action(self, self.tr("Full System Update")):
            return

        self.start_process()
        self.update_queue = [
            self._system_update_step(self.package_manager),
            ("flatpak", ["update", "-y"], self.tr("Starting Flatpak Update...")),
            ("pkexec", ["fwupdmgr", "update", "-y"], self.tr("Starting Firmware Update...")),
        ]
        self.current_update_index = 0
        cmd, args, desc = self.update_queue[0]
        self.append_output(self.tr(desc) + "\n")
        self.runner.run_command(cmd, args)

    # -- Helpers -----------------------------------------------------------

    def start_process(self):
        self.output_area.clear()
        self.progress_bar.setValue(0)
        self.progress_bar.setFormat("%p% - Waiting...")
        self.action_progress.status_label.setText(self.tr("Update in progress"))
        self.btn_dnf.setEnabled(False)
        self.btn_flatpak.setEnabled(False)
        self.btn_fw.setEnabled(False)
        self.btn_update_all.setEnabled(False)

    def on_command_finished(self, exit_code):
        self.append_output(self.tr("\nCommand finished with exit code: {}").format(exit_code))

        # Handle sequential update-all queue
        if self.update_queue and self.current_update_index < len(self.update_queue) - 1:
            self.current_update_index += 1
            cmd, args, desc = self.update_queue[self.current_update_index]
            self.append_output(f"\n\n{desc}\n")
            self.progress_bar.setValue(0)
            self.progress_bar.setFormat(f"0% - {desc}")
            self.runner.run_command(cmd, args)
        else:
            self.update_queue = []
            self.current_update_index = 0
            self.btn_dnf.setEnabled(True)
            self.btn_flatpak.setEnabled(True)
            self.btn_fw.setEnabled(True)
            self.btn_update_all.setEnabled(True)
            self.progress_bar.setValue(100)
            self.progress_bar.setFormat(self.tr("100% - Done"))
            self.action_progress.status_label.setText(
                self.tr("Update completed") if exit_code == 0 else self.tr("Update failed")
            )
            if exit_code == 0:
                self.show_success(self.tr("Update completed successfully"))
            else:
                self.show_error(self.tr("Update failed (exit code {})").format(exit_code))

    def run_single_command(self, cmd, args, description):
        self.output_area.clear()
        self.progress_bar.setValue(0)
        self.append_output(f"{description}\n")
        self.runner.run_command(cmd, args)


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

    def __init__(self):
        super().__init__()
        layout = QVBoxLayout()
        self.setLayout(layout)

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
        btn_dnf_clean.clicked.connect(
            lambda: self.actionCenterRequested.emit("dnf-clean-all", {})
        )
        cleanup_layout.addWidget(btn_dnf_clean)

        btn_autoremove = QPushButton(self.tr("Remove Unused Packages (Risky)"))
        btn_autoremove.setAccessibleName(self.tr("Remove Unused Packages"))
        btn_autoremove.setObjectName("maintAutoremoveBtn")
        btn_autoremove.setToolTip(MAINT_ORPHANS)
        btn_autoremove.clicked.connect(self.run_autoremove)
        cleanup_layout.addWidget(btn_autoremove)

        btn_journal = QPushButton(self.tr("Vacuum Journal (2 weeks)"))
        btn_journal.setAccessibleName(self.tr("Vacuum Journal"))
        btn_journal.setToolTip(MAINT_JOURNAL)
        btn_journal.clicked.connect(lambda: self.run_command("pkexec", ["journalctl", "--vacuum-time=2weeks"], self.tr("Vacuuming Journal...")))
        cleanup_layout.addWidget(btn_journal)

        layout.addWidget(cleanup_group)

        # Maintenance Group
        maint_group = QGroupBox(self.tr("Maintenance"))
        maint_layout = QVBoxLayout()
        maint_group.setLayout(maint_layout)

        btn_trim = QPushButton(self.tr("Review SSD Trim"))
        btn_trim.setAccessibleName(self.tr("Review SSD Trim in Action Center"))
        btn_trim.setObjectName("maintReviewFstrim")
        btn_trim.clicked.connect(
            lambda: self.actionCenterRequested.emit("fstrim-all", {})
        )
        maint_layout.addWidget(btn_trim)

        btn_rpmdb = QPushButton(self.tr("Rebuild RPM Database"))
        btn_rpmdb.setAccessibleName(self.tr("Rebuild RPM Database"))
        btn_rpmdb.clicked.connect(lambda: self.run_command("pkexec", ["rpm", "--rebuilddb"], self.tr("Rebuilding RPM Database...")))
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
        preview_intro = QLabel(self.tr(
            "Analyze package-cache and journal sizes without deleting anything. "
            "Recovery points are always managed separately."
        ))
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
        layout.addWidget(QLabel(self.tr("Output Log:")))
        layout.addWidget(self.output_area)
        self._reclaim_thread = None
        self._reclaim_worker = None

    def _analyze_reclaim(self) -> None:
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

    def _show_reclaim_analysis(self, analysis) -> None:
        lines = []
        for category in analysis.categories:
            size = self.tr("estimate unavailable")
            if category.estimated_bytes is not None:
                size = self._format_bytes(category.estimated_bytes)
            mode = self.tr("manual-only") if category.manual_only else self.tr("reviewable")
            lines.append(
                f"{category.title}: {size} · {category.risk} · {mode}\n"
                f"{category.guidance}"
            )
        lines.append(
            self.tr("Selected safe estimate: %s")
            % self._format_bytes(analysis.estimated_selected_bytes)
        )
        self.reclaim_banner.set_result(
            "success",
            self.tr("Reclaim analysis complete"),
            "\n\n".join(lines),
        )

    def _show_reclaim_error(self, message: str) -> None:
        self.reclaim_banner.set_result(
            "error",
            self.tr("Reclaim analysis failed"),
            str(message),
        )

    def _clear_reclaim_worker(self) -> None:
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

    def check_timeshift(self):
        if cached_which("timeshift"):
            self.run_command("pkexec", ["timeshift", "--list"], self.tr("Checking Timeshift Snapshots..."))
        else:
            self.append_output(self.tr("Timeshift not found. Please install it for system safety.\n"))

    def run_autoremove(self):
        from services.security import SafetyManager

        if SafetyManager.check_dnf_lock():
            QMessageBox.warning(
                self,
                self.tr("Update Locked"),
                self.tr("Another package manager is running."),
            )
            return

        if SafetyManager.confirm_action(self, self.tr("Remove Unused Packages (Risky)")):
            self.run_command(
                *PrivilegedCommand.dnf("autoremove"),
            )

    def on_command_finished(self, exit_code):
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

    def __init__(self):
        super().__init__()
        from utils.package_manager import PackageManager

        self.pkg_manager = PackageManager()
        self.reboot_runner = CommandRunner()
        self._loaded = False
        self.init_ui()

    def showEvent(self, event):
        super().showEvent(event)
        if not self._loaded:
            self._loaded = True
            QTimer.singleShot(0, self.refresh_list)

    def init_ui(self):
        layout = QVBoxLayout()
        layout.setContentsMargins(30, 30, 30, 30)
        layout.setSpacing(20)
        self.setLayout(layout)

        # Header
        header = QLabel(self.tr("System Overlays (rpm-ostree)"))
        header.setObjectName("header")
        layout.addWidget(header)

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

    def refresh_list(self):
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

    def remove_selected(self):
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
            result = self.pkg_manager.remove([pkg_name])
            if result.success:
                QMessageBox.information(self, self.tr("Success"), result.message)
                self.refresh_list()
            else:
                QMessageBox.critical(self, self.tr("Error"), result.message)

    def reset_to_base(self):
        """Reset to base image, removing all layered packages."""
        reply = QMessageBox.warning(
            self,
            self.tr("Reset to Base Image"),
            self.tr("This will REMOVE ALL layered packages and reset to the clean base image.\n\nAre you absolutely sure?"),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )

        if reply == QMessageBox.StandardButton.Yes:
            result = self.pkg_manager.reset_to_base()
            if result.success:
                QMessageBox.information(
                    self,
                    self.tr("Reset Complete"),
                    self.tr("System reset to base image.\n\nPlease reboot to apply changes."),
                )
                self.refresh_list()
            else:
                QMessageBox.critical(self, self.tr("Error"), result.message)

    def reboot_system(self):
        """Offer to reboot the system."""
        reply = QMessageBox.question(
            self,
            self.tr("Reboot Now?"),
            self.tr("Reboot now to apply pending changes?"),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )

        if reply == QMessageBox.StandardButton.Yes:
            self.reboot_runner.run_command("pkexec", ["systemctl", "reboot"])


# ---------------------------------------------------------------------------
# Sub-tab: Smart Updates (v37.0 Pinnacle)
# ---------------------------------------------------------------------------


class _SmartUpdatesSubTab(QWidget):
    """Sub-tab for advanced update management.

    Uses UpdateManager to check updates, preview conflicts,
    schedule updates, and rollback.
    """

    def __init__(self):
        super().__init__()
        self._loaded = False
        layout = QVBoxLayout()
        self.setLayout(layout)

        header = QLabel(self.tr("Smart Updates"))
        header.setObjectName("header")
        layout.addWidget(header)

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
        layout.addWidget(self.output_area)

        self.runner = CommandRunner()
        self.runner.output_received.connect(self._append_output)
        self.runner.finished.connect(lambda ec: self._append_output(self.tr("\nCommand finished with exit code: {}\n").format(ec)))

        layout.addStretch()

    def _append_output(self, text):
        self.output_area.moveCursor(self.output_area.textCursor().MoveOperation.End)
        self.output_area.insertPlainText(text)
        self.output_area.moveCursor(self.output_area.textCursor().MoveOperation.End)

    def _check_updates(self):
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

    def _preview_conflicts(self):
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

    def _schedule_update(self):
        try:
            from utils.update_manager import UpdateManager

            scheduled = UpdateManager.schedule_update(when="02:00")
            cmds = UpdateManager.get_schedule_commands(scheduled)
            for binary, args, desc in cmds:
                self._append_output(f"{desc}\n")
                self.runner.run_command(binary, args)
        except (RuntimeError, OSError, ValueError) as e:
            self._append_output(f"[ERROR] {e}\n")

    def _rollback_last(self):
        try:
            from utils.update_manager import UpdateManager

            binary, args, desc = UpdateManager.rollback_last()
            self._append_output(f"{desc}\n")
            self.runner.run_command(binary, args)
        except (RuntimeError, OSError, ValueError) as e:
            self._append_output(f"[ERROR] {e}\n")


# ---------------------------------------------------------------------------
# Sub-tab: Upgrade Assistant (v10.0 Waypoint)
# ---------------------------------------------------------------------------


class _UpgradeAssistantSubTab(QWidget):
    """Guided release planning entry point backed by ReleaseReadiness."""

    def __init__(self):
        super().__init__()
        layout = QVBoxLayout()
        layout.setSpacing(14)
        self.setLayout(layout)

        header = QLabel(self.tr("Upgrade Assistant"))
        header.setObjectName("header")
        layout.addWidget(header)

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

    def _open_readiness(self, target_key: str) -> None:
        from ui.release_readiness_dialog import ReleaseReadinessDialog

        dialog = ReleaseReadinessDialog(target_key, self)
        dialog.exec()

    def _export_bundle(self, target_key: str) -> None:
        from core.export.support_bundle_v5 import SupportBundleV5

        path = f"loofi-readiness-{target_key}.json"
        try:
            SupportBundleV5.save_json(path, target=target_key)
            QMessageBox.information(self, self.tr("Export Complete"), self.tr("Saved support bundle to %1").replace("%1", path))
        except (OSError, RuntimeError, ValueError) as exc:
            QMessageBox.critical(self, self.tr("Export Failed"), str(exc))


# ---------------------------------------------------------------------------
# Sub-tab: Action Center (v11.0 Harbor)
# ---------------------------------------------------------------------------


class _ActionCenterOperationWorker(QObject):
    """Run Action Center probes and persistence away from the GUI thread."""

    finished = pyqtSignal(object)
    failed = pyqtSignal(str)

    def __init__(self, operation):
        super().__init__()
        self._operation = operation

    def run(self) -> None:
        try:
            self.finished.emit(self._operation())
        except (OSError, RuntimeError, ValueError, TypeError, AttributeError) as exc:
            self.failed.emit(str(exc))


class _ActionCenterSubTab(BaseTab):
    """Review, asynchronously run, verify, and inspect v14 action plans."""

    _ACTION_ID_ADAPTERS = {
        "readiness-repo-cache-clean": "dnf-clean-all",
    }

    def __init__(self):
        super().__init__()
        self._target_key = "44"
        self._items = []
        self._orchestrator = None
        self._current_plan = None
        self._current_run = None
        self._prepared_run = None
        self._interrupt_reason = None
        self._output_chunks = []
        self._stderr_chunks = []
        self._operation_thread = None
        self._operation_worker = None
        self._requested_action_id = ""
        self._requested_parameters = {}

        from core.actions.center import ActionCenterService

        self._service = ActionCenterService()

        layout = QVBoxLayout()
        layout.setSpacing(12)
        self.setLayout(layout)

        header = QLabel(self.tr("Action Center"))
        header.setObjectName("header")
        layout.addWidget(header)

        intro = QLabel(
            self.tr(
                "Review preflight, exact command, risk, and recovery guidance. Applying a plan "
                "runs asynchronously and never counts as success until separate verification passes."
            )
        )
        intro.setWordWrap(True)
        layout.addWidget(intro)

        target_row = QVBoxLayout()
        target_row.setObjectName("actionCenterControls")
        target_load_row = QHBoxLayout()
        target_review_row = QHBoxLayout()
        load_stable = QPushButton(self.tr("Load Fedora 44 Actions"))
        self.load_stable_button = load_stable
        load_stable.clicked.connect(lambda: self._load_target("44"))
        target_load_row.addWidget(load_stable)

        load_preview = QPushButton(self.tr("Load Fedora 45 Preview Actions"))
        self.load_preview_button = load_preview
        load_preview.clicked.connect(lambda: self._load_target("45-preview"))
        target_load_row.addWidget(load_preview)

        preview_button = QPushButton(self.tr("Preview Selected"))
        self.preview_button = preview_button
        preview_button.clicked.connect(self._preview_selected)
        target_load_row.addWidget(preview_button)

        review_button = QPushButton(self.tr("Review & Plan"))
        self.review_button = review_button
        review_button.clicked.connect(self._plan_selected)
        target_review_row.addWidget(review_button)

        self.run_button = QPushButton(self.tr("Run Plan"))
        self.run_button.clicked.connect(self._run_current_plan)
        self.run_button.setEnabled(False)
        target_review_row.addWidget(self.run_button)

        self.verify_button = QPushButton(self.tr("Verify Run"))
        self.verify_button.clicked.connect(self._verify_current_run)
        self.verify_button.setEnabled(False)
        target_review_row.addWidget(self.verify_button)

        history_button = QPushButton(self.tr("Show History"))
        self.history_button = history_button
        history_button.clicked.connect(self._show_history)
        target_review_row.addWidget(history_button)
        target_row.addLayout(target_load_row)
        target_row.addLayout(target_review_row)
        layout.addLayout(target_row)

        self.presentation_banner = ResultBanner(
            self.tr("Action Center status"),
            self.tr("Loading Action Center candidates…"),
        )
        self.presentation_status = self.presentation_banner.message_label
        self.presentation_status.setAccessibleName(self.tr("Action Center status"))
        layout.addWidget(self.presentation_banner)

        self.action_list = QListWidget()
        self.action_list.setAccessibleName(self.tr("Action Center candidates"))
        self.action_list.currentRowChanged.connect(self._selection_changed)
        layout.addWidget(self.action_list, 1)

        self.detail_disclosure = DetailsDisclosure(
            summary=self.tr("Action Center details")
        )
        self.detail_area = self.detail_disclosure.details
        self.detail_area.setAccessibleName(self.tr("Action Center details"))
        self.detail_disclosure.toggle_button.setChecked(True)
        layout.addWidget(self.detail_disclosure, 1)

        self.add_output_section(layout)
        self.runner.output_received.connect(self._capture_output)
        self.runner.stderr_received.connect(self._capture_stderr)

        self._load_target(self._target_key)

    def _orchestrator_instance(self):
        if self._orchestrator is None:
            from core.actions import ActionCenterOrchestrator

            self._orchestrator = ActionCenterOrchestrator()
        return self._orchestrator

    def _load_target(self, target_key: str) -> None:
        self._target_key = target_key
        self._current_plan = None
        self._current_run = None
        self.run_button.setEnabled(False)
        self.verify_button.setEnabled(False)
        self.action_list.clear()
        self.detail_area.setPlainText(self.tr("Loading Action Center candidates..."))
        self.presentation_banner.set_result(
            "info",
            self.tr("Loading Action Center"),
            self.tr("Loading Action Center candidates…"),
        )
        self._set_loading(True)
        self._start_operation(
            lambda: self._merged_items(target_key),
            self._accept_loaded_items,
            self.tr("Action Center Failed"),
        )

    def _merged_items(self, target_key: str):
        readiness = self._service.candidates_from_readiness(target_key)
        catalog = self._service.catalog_items(target_key)
        catalog_ids = {item.id for item in catalog}
        adapters = {item.id for item in readiness if self._ACTION_ID_ADAPTERS.get(item.id) in catalog_ids}
        return [*catalog, *(item for item in readiness if item.id not in adapters)]

    def _accept_loaded_items(self, items) -> None:
        self._items = list(items)
        self._set_loading(False)

        for item in self._items:
            marker = self.tr("manual") if item.manual_only else item.state
            self.action_list.addItem(f"{item.title} [{item.risk_level}] - {marker}")

        if self._items:
            self.presentation_banner.set_result(
                "info",
                self.tr("Maintenance review available"),
                self.tr("%d maintenance items are available. Select one to inspect its lifecycle.")
                % len(self._items),
            )
            selected = self._select_requested_action()
            if not selected:
                self.action_list.setCurrentRow(0)
                self._show_item(self._items[0])
        else:
            self.presentation_banner.set_result(
                "success",
                self.tr("Nothing needs review"),
                self.tr("No maintenance item needs review right now."),
            )
            self.detail_area.setPlainText(self.tr("No Action Center candidates are currently available."))

    def preselect_action(self, action_id: str, parameters=None) -> bool:
        """Preselect a candidate without creating a plan or running anything."""
        self._requested_action_id = self._ACTION_ID_ADAPTERS.get(
            str(action_id or ""), str(action_id or "")
        )
        self._requested_parameters = dict(parameters or {})
        if not self._requested_action_id:
            return False
        return self._select_requested_action() or not bool(self._items)

    def _set_loading(self, loading: bool) -> None:
        for button in (
            self.load_stable_button,
            self.load_preview_button,
            self.preview_button,
            self.review_button,
            self.history_button,
        ):
            button.setEnabled(not loading)

    def _selection_changed(self, row: int) -> None:
        if 0 <= row < len(self._items):
            self._show_item(self._items[row])

    def _select_requested_action(self) -> bool:
        if not self._requested_action_id:
            return False
        for index, item in enumerate(self._items):
            candidate_id = self._ACTION_ID_ADAPTERS.get(item.id, item.id)
            if candidate_id == self._requested_action_id:
                self.action_list.setCurrentRow(index)
                self._show_item(item)
                return True
        return False

    def _start_operation(self, operation, on_success, failure_title: str) -> None:
        if self._operation_thread is not None:
            QMessageBox.warning(self, self.tr("Action Center Busy"), self.tr("Wait for the current Action Center operation to finish."))
            return
        thread = QThread(self)
        worker = _ActionCenterOperationWorker(operation)
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.finished.connect(on_success)
        worker.finished.connect(thread.quit)
        worker.failed.connect(lambda message: QMessageBox.warning(self, failure_title, message))
        worker.failed.connect(lambda _message: self._set_loading(False))
        worker.failed.connect(thread.quit)
        thread.finished.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)
        thread.finished.connect(self._clear_operation_worker)
        self._operation_thread = thread
        self._operation_worker = worker
        thread.start()

    def _clear_operation_worker(self) -> None:
        self._operation_thread = None
        self._operation_worker = None

    def _selected_item(self):
        row = self.action_list.currentRow()
        if row < 0 or row >= len(self._items):
            return None
        return self._items[row]

    def _show_item(self, item) -> None:
        self.review_button.setEnabled(not item.manual_only)
        if item.manual_only:
            self.presentation_status.setText(
                self.tr(
                    "Manual-only recommendation: review the guidance; "
                    "Action Center will not execute it."
                )
            )
        command = " ".join(item.command_preview) if item.command_preview else self.tr("Manual-only")
        verification = " ".join(item.verification_command) if item.verification_command else self.tr("No verification command")
        self.detail_area.setPlainText(
            "\n".join(
                [
                    f"{self.tr('Title')}: {item.title}",
                    f"{self.tr('Source')}: {item.source}",
                    f"{self.tr('State')}: {item.state}",
                    f"{self.tr('Risk')}: {item.risk_level}",
                    f"{self.tr('Privilege')}: {item.privilege}",
                    f"{self.tr('Command preview')}: {command}",
                    f"{self.tr('Verification')}: {verification}",
                    f"{self.tr('Rollback')}: {item.rollback_hint}",
                    "",
                    item.description,
                ]
            )
        )

    def _preview_selected(self) -> None:
        item = self._selected_item()
        if item is None:
            QMessageBox.warning(self, self.tr("No Action Selected"), self.tr("Select an Action Center item first."))
            return

        if item.source == "catalog:v14":
            self.detail_area.setPlainText(
                "\n".join(
                    [
                        f"{self.tr('Preview')}: {item.title}",
                        self.tr("Create a plan to run fresh preflight and generate the exact command."),
                        f"{self.tr('Risk')}: {item.risk_level}",
                        f"{self.tr('Recovery')}: {item.rollback_hint}",
                    ]
                )
            )
            return

        result = self._service.preview(item)
        self.detail_area.setPlainText(
            "\n".join(
                [
                    f"{self.tr('Preview')}: {item.title}",
                    f"{self.tr('Result')}: {result.message}",
                    f"{self.tr('Risk')}: {item.risk_level}",
                    f"{self.tr('Rollback')}: {item.rollback_hint}",
                    f"{self.tr('Command')}: {' '.join(item.command_preview) if item.command_preview else self.tr('Manual-only')}",
                ]
            )
        )

    def _plan_selected(self) -> None:
        item = self._selected_item()
        if item is None:
            QMessageBox.warning(self, self.tr("No Action Selected"), self.tr("Select an Action Center item first."))
            return

        action_id = self._ACTION_ID_ADAPTERS.get(item.id, item.id)
        parameters = {}
        if action_id == "restart-failed-service":
            service = str(self._requested_parameters.get("service", ""))
            if not service:
                service = str(item.metadata.get("service", "")) if isinstance(item.metadata, dict) else ""
            if not service and item.command_preview:
                service = str(item.command_preview[-1])
            if not service:
                service, accepted = QInputDialog.getText(
                    self,
                    self.tr("Failed Service"),
                    self.tr("Enter the exact failed systemd unit (for example, example.service):"),
                )
                if not accepted:
                    return
            if service:
                parameters["service"] = service

        orchestrator = self._orchestrator_instance()
        self._start_operation(
            lambda: orchestrator.plan(action_id, parameters, target=self._target_key),
            self._accept_plan,
            self.tr("Action Plan Failed"),
        )

    def _accept_plan(self, plan) -> None:
        self._current_plan = plan
        self._current_run = None
        self.run_button.setEnabled(plan.state in {"ready", "needs_review"})
        self.verify_button.setEnabled(False)
        self._show_plan(plan)

    def _show_plan(self, plan) -> None:
        self.detail_area.setPlainText(
            "\n".join(
                [
                    f"{self.tr('Plan')}: {plan.plan_id}",
                    f"{self.tr('Action')}: {plan.action_id}",
                    f"{self.tr('State')}: {plan.state}",
                    f"{self.tr('Risk')}: {plan.risk_level}",
                    f"{self.tr('Privilege')}: {'pkexec' if plan.privileged else self.tr('none')}",
                    f"{self.tr('Preflight')}: {plan.policy_decision.reason_code}",
                    plan.policy_decision.explanation,
                    f"{self.tr('Command preview')}: {' '.join(plan.preview) if plan.preview else self.tr('Manual-only')}",
                    f"{self.tr('Recovery')}: {plan.recovery_guidance}",
                    f"{self.tr('Expires')}: {plan.expires_at}",
                ]
            )
        )

    def _run_current_plan(self) -> None:
        plan = self._current_plan
        if plan is None:
            QMessageBox.warning(self, self.tr("No Plan"), self.tr("Review and create a plan first."))
            return

        answer = QMessageBox.question(
            self,
            self.tr("Confirm Action"),
            self.tr("Run the reviewed command now? The preflight will be checked again."),
        )
        if answer != QMessageBox.StandardButton.Yes:
            return

        accept_no_rollback = False
        if plan.risk_level in {"medium", "high"} and not plan.rollback_supported:
            answer = QMessageBox.question(
                self,
                self.tr("No Automatic Rollback"),
                self.tr("This action has no supported rollback. Accept the recovery guidance and continue?"),
            )
            if answer != QMessageBox.StandardButton.Yes:
                return
            accept_no_rollback = True

        try:
            orchestrator = self._orchestrator_instance()
            prepared = orchestrator.prepare_run(
                plan.plan_id,
                confirmed=True,
                accept_no_rollback=accept_no_rollback,
            )
            vector = orchestrator.facade.asynchronous_execution_vector(
                prepared.command,
                privileged=prepared.privileged,
                action_id=prepared.action_id,
            )
        except (OSError, RuntimeError, ValueError, TypeError) as exc:
            QMessageBox.warning(self, self.tr("Action Blocked"), str(exc))
            return

        self._prepared_run = prepared
        self._output_chunks = []
        self._stderr_chunks = []
        self.run_button.setEnabled(False)
        self.verify_button.setEnabled(False)
        self.output_area.clear()
        self.append_output(self.tr("Running reviewed Action Center plan asynchronously...\n"))
        self.runner.run_command(vector[0], vector[1:])

    def _capture_output(self, text: str) -> None:
        self._output_chunks.append(str(text))

    def _capture_stderr(self, text: str) -> None:
        self._stderr_chunks.append(str(text))

    def on_command_finished(self, exit_code):
        prepared = self._prepared_run
        if prepared is None:
            return
        if self._interrupt_reason is not None:
            self._finalize_interrupted_run(prepared, self._interrupt_reason)
            return
        from core.executor.action_result import ActionResult

        result = ActionResult(
            success=exit_code == 0,
            message=self.tr("Execution finished; separate verification is required.") if exit_code == 0 else self.tr("Execution failed."),
            exit_code=int(exit_code),
            stdout="".join(self._output_chunks),
            stderr="".join(self._stderr_chunks),
            action_id=prepared.action_id,
        )
        self._prepared_run = None
        try:
            run = self._orchestrator_instance().complete_run(prepared.run_id, result)
        except (OSError, RuntimeError, ValueError, TypeError) as exc:
            QMessageBox.warning(self, self.tr("Run Recording Failed"), str(exc))
            return
        self._current_run = run
        self.verify_button.setEnabled(run.state == "verifying")
        self.append_output(self.tr("\nExecution state: %1\n").replace("%1", run.state))
        self._show_run(run)

    def on_error(self, error_msg):
        self.append_output(self.tr("\n[ERROR] %1\n").replace("%1", str(error_msg)))
        prepared = self._prepared_run
        if prepared is None:
            return
        self._interrupt_reason = "command-runner-error"
        # Timeout/error signals may arrive while QProcess is still alive. Keep
        # the cross-process mutation lease until termination is confirmed by
        # the finished signal. Failed-to-start is already safely not running.
        if not self.runner.is_running():
            self._finalize_interrupted_run(prepared, self._interrupt_reason)

    def _cancel_command(self):
        prepared = self._prepared_run
        if prepared is not None:
            self._interrupt_reason = "user-cancelled"
        self.runner.stop()
        if prepared is not None and not self.runner.is_running():
            self._finalize_interrupted_run(prepared, self._interrupt_reason or "user-cancelled")

    def _finalize_interrupted_run(self, prepared, reason: str) -> None:
        """Persist interruption only after the command process is not running."""
        self._prepared_run = None
        self._interrupt_reason = None
        try:
            self._current_run = self._orchestrator_instance().interrupt_run(prepared.run_id, reason)
        except (OSError, RuntimeError, ValueError, TypeError) as exc:
            QMessageBox.warning(self, self.tr("Run Recording Failed"), str(exc))
            return
        self.verify_button.setEnabled(False)
        self._show_run(self._current_run)

    def _verify_current_run(self) -> None:
        run = self._current_run
        if run is None:
            QMessageBox.warning(self, self.tr("No Run"), self.tr("Run a reviewed plan before verification."))
            return
        self.verify_button.setEnabled(False)
        orchestrator = self._orchestrator_instance()
        self._start_operation(
            lambda: orchestrator.verify(run.run_id),
            self._accept_verification,
            self.tr("Verification Failed"),
        )

    def _accept_verification(self, verified) -> None:
        self._current_run = verified
        self._show_run(verified)

    def _show_run(self, run) -> None:
        verification = run.verification_result or {}
        self.detail_area.setPlainText(
            "\n".join(
                [
                    f"{self.tr('Run')}: {run.run_id}",
                    f"{self.tr('Plan')}: {run.plan_id}",
                    f"{self.tr('Action')}: {run.action_id}",
                    f"{self.tr('State')}: {run.state}",
                    f"{self.tr('Execution')}: {(run.execution_result or {}).get('message', '')}",
                    f"{self.tr('Verification')}: {verification.get('message', self.tr('Pending'))}",
                    f"{self.tr('Recovery')}: {run.recovery_status}",
                ]
            )
        )

    def _show_history(self) -> None:
        from core.actions import ActionPlanStore, ActionRunStore

        history = self._service.recent_history(limit=25)
        plans = ActionPlanStore().list(limit=25)
        runs = ActionRunStore().list(limit=25)
        if not history and not plans and not runs:
            self.detail_area.setPlainText(self.tr("No Action Center history recorded."))
            return
        lines = []
        for plan in reversed(plans):
            lines.append(f"{plan.plan_id}: {plan.action_id} [{plan.state}]")
        for run in reversed(runs):
            lines.append(f"{run.run_id}: {run.action_id} [{run.state}]")
        for entry in history:
            event = entry.get("event", "event")
            action = entry.get("action", {})
            title = action.get("title", action.get("id", "unknown")) if isinstance(action, dict) else "unknown"
            lines.append(f"{event}: {title}")
        self.detail_area.setPlainText("\n".join(lines))
        viable = next((plan for plan in reversed(plans) if plan.state in {"ready", "needs_review"} and not plan.is_expired()), None)
        if viable is not None:
            self._current_plan = viable
            self.run_button.setEnabled(True)


# ---------------------------------------------------------------------------
# Sub-tab: Health Timeline (v12.0 Lighthouse)
# ---------------------------------------------------------------------------


class _HealthTimelineSubTab(QWidget):
    """My Fedora Today timeline surface backed by core.observability."""

    def __init__(self):
        super().__init__()
        from core.observability import MaintenanceTrendAnalyzer, ObservabilityService

        self._observability = ObservabilityService()
        self._store = self._observability.snapshots
        self._analyzer_cls = MaintenanceTrendAnalyzer

        layout = QVBoxLayout()
        layout.setSpacing(12)
        self.setLayout(layout)

        header = QLabel(self.tr("My Fedora Today"))
        header.setObjectName("header")
        layout.addWidget(header)

        button_row = QHBoxLayout()
        refresh_button = QPushButton(self.tr("Refresh"))
        refresh_button.clicked.connect(self._load_timeline)
        button_row.addWidget(refresh_button)

        snapshot_button = QPushButton(self.tr("Record Snapshot"))
        snapshot_button.clicked.connect(self._record_snapshot)
        button_row.addWidget(snapshot_button)
        button_row.addStretch()
        layout.addLayout(button_row)

        self.summary_label = QLabel()
        self.summary_label.setWordWrap(True)
        layout.addWidget(self.summary_label)

        self.timeline_list = QListWidget()
        self.timeline_list.setAccessibleName(self.tr("Health timeline snapshots"))
        layout.addWidget(self.timeline_list, 1)

        self.detail_area = QTextEdit()
        self.detail_area.setReadOnly(True)
        self.detail_area.setAccessibleName(self.tr("Health timeline details"))
        layout.addWidget(self.detail_area, 1)

        self._load_timeline()

    def _load_timeline(self) -> None:
        snapshots = self._store.load()
        summary = self._analyzer_cls(snapshots).analyze()
        self.timeline_list.clear()
        self.summary_label.setText(summary.summary)

        for snapshot in reversed(snapshots[-10:]):
            self.timeline_list.addItem(
                self.tr("%1 -- %2 issue(s)")
                .replace("%1", str(snapshot.timestamp))
                .replace("%2", str(len(snapshot.problem_fingerprints)))
            )

        self.detail_area.setPlainText(
            "\n".join(
                [
                    f"{self.tr('Snapshots')}: {len(snapshots)}",
                    f"{self.tr('New')}: {len(summary.new)}",
                    f"{self.tr('Recurring')}: {len(summary.recurring)}",
                    f"{self.tr('Resolved')}: {len(summary.resolved)}",
                    f"{self.tr('Worsening')}: {len(summary.worsening)}",
                    "",
                    summary.summary,
                ]
            )
        )

    def _record_snapshot(self) -> None:
        try:
            self._observability.collect_snapshot(target="44", source="gui")
        except (OSError, RuntimeError, ValueError, TypeError) as exc:
            QMessageBox.warning(self, self.tr("Snapshot Failed"), str(exc))
            return
        self._load_timeline()


# ---------------------------------------------------------------------------
# Main consolidated tab
# ---------------------------------------------------------------------------


class MaintenanceTab(BaseTab):
    """Consolidated maintenance tab merging Updates, Cleanup, and Overlays.

    Uses a QTabWidget for sub-navigation.  The Overlays sub-tab is only
    shown when the system is detected as Atomic (rpm-ostree based).
    """

    _METADATA = PluginMetadata(
        id="maintenance",
        name="Maintenance",
        description="System updates, cache cleanup, and overlay management for Fedora.",
        category="Packages",
        icon="maintenance-health",
        badge="recommended",
        order=20,
    )

    actionCenterRequested = pyqtSignal(str, object)

    def metadata(self) -> PluginMetadata:
        return self._METADATA

    def create_widget(self) -> QWidget:
        return self

    def __init__(self):
        super().__init__()
        layout = QVBoxLayout()
        self.setLayout(layout)

        self.tabs = QTabWidget()
        configure_top_tabs(self.tabs)

        self._sub_tab_factories = [
            (self.tr("Updates"), _UpdatesSubTab),
            (self.tr("Action Center"), _ActionCenterSubTab),
            (self.tr("Cleanup"), _CleanupSubTab),
            (self.tr("Health Timeline"), _HealthTimelineSubTab),
            (self.tr("Upgrade Assistant"), _UpgradeAssistantSubTab),
        ]

        if SystemManager.is_atomic():
            self._sub_tab_factories.append((self.tr("Overlays"), _OverlaysSubTab))

        self._loaded_tabs = {}

        for label, _ in self._sub_tab_factories:
            placeholder = QWidget()
            self.tabs.addTab(placeholder, label)

        self.tabs.currentChanged.connect(self._lazy_load_sub_tab)
        self._lazy_load_sub_tab(0)

        layout.addWidget(self.tabs)

    def _lazy_load_sub_tab(self, index):
        """Instantiate sub-tab on first visit to avoid eager construction."""
        if index in self._loaded_tabs:
            return

        if index < len(self._sub_tab_factories):
            label, factory = self._sub_tab_factories[index]
            widget = factory()
            request = getattr(widget, "actionCenterRequested", None)
            if request is not None and hasattr(request, "connect"):
                request.connect(self._open_action_center)
            self._loaded_tabs[index] = widget
            self.tabs.blockSignals(True)
            self.tabs.removeTab(index)
            self.tabs.insertTab(index, widget, label)
            self.tabs.setCurrentIndex(index)
            self.tabs.blockSignals(False)

    def _open_action_center(self, action_id: str, parameters=None) -> None:
        self.preselect_action(action_id, parameters)

    def preselect_action(self, action_id: str, parameters=None) -> bool:
        """Open Action Center and preselect one candidate without side effects."""
        for index, (label, _factory) in enumerate(self._sub_tab_factories):
            if label != self.tr("Action Center"):
                continue
            self.tabs.setCurrentIndex(index)
            self._lazy_load_sub_tab(index)
            action_center = self._loaded_tabs.get(index)
            preselect = getattr(action_center, "preselect_action", None)
            if not callable(preselect):
                return False
            if parameters is None:
                return bool(preselect(action_id))
            return bool(preselect(action_id, parameters))
        return False

    def activate_route(self, route) -> bool:
        """Resolve stable Maintenance subroutes after presentation consolidation."""
        original_subroute = str(getattr(route, "subroute", "") or "")
        subroute = "updates" if original_subroute == "smart-updates" else original_subroute
        labels = {
            "updates": self.tr("Updates"),
            "cleanup": self.tr("Cleanup"),
            "health-timeline": self.tr("Health Timeline"),
            "action-center": self.tr("Action Center"),
            "upgrade-assistant": self.tr("Upgrade Assistant"),
            "overlays": self.tr("Overlays"),
        }
        wanted = labels.get(subroute)
        if wanted is None:
            return not bool(subroute)
        for index, (label, _factory) in enumerate(self._sub_tab_factories):
            if label != wanted:
                continue
            self.tabs.setCurrentIndex(index)
            self._lazy_load_sub_tab(index)
            if original_subroute == "smart-updates":
                reveal = getattr(
                    self._loaded_tabs.get(index),
                    "reveal_advanced_options",
                    None,
                )
                if callable(reveal):
                    reveal()
            return True
        return False
