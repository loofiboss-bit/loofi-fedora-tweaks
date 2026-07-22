"""
Diagnostics Tab - Consolidated tab merging Watchtower and Boot.
Part of v11.0 "Aurora Update".

Uses a route-owned stack for Troubleshooting and Boot while preserving
Watchtower's content tabs (services, boot analysis, journal).
"""

import typing

from core.plugins.metadata import PluginMetadata
from core.product_catalog import plugin_metadata_for_module
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QGroupBox,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMenu,
    QMessageBox,
    QPushButton,
    QSlider,
    QStackedWidget,
    QTabWidget,
    QTextEdit,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)
from services.system import ServiceManager, UnitScope, UnitState
from utils.boot_analyzer import BootAnalyzer
from utils.journal import JournalManager
from utils.kernel import KernelManager
from services.security import SecureBootManager
from utils.zram import ZramManager

from ui.base_tab import BaseTab
from ui.components.layout import PageScaffold
from ui.tab_utils import configure_top_tabs

# ---------------------------------------------------------------------------
# Sub-tab: Watchtower
# ---------------------------------------------------------------------------


class _WatchtowerSubTab(QWidget):
    """Sub-tab with system diagnostics and service management.

    Preserves every feature from the original WatchtowerTab:
    - Services browser with filter (Gaming / Failed / Active / All User)
    - Right-click context menu: Start, Stop, Restart, Mask, Unmask
    - Boot analysis with time summary, slow services, optimisation tips
    - Journal viewer with error counts, failed services, panic log export
    - Internal QTabWidget for its own three sub-sections
    """

    actionCenterRequested = pyqtSignal(str, object)

    def __init__(self: typing.Any) -> None:
        super().__init__()
        self.init_ui()

    def init_ui(self: typing.Any) -> typing.Any:
        """Initialise the UI components."""
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        self.scaffold = PageScaffold(
            self.tr("Troubleshooting"),
            self.tr("Diagnose system issues and inspect supporting evidence."),
        )
        root.addWidget(self.scaffold)
        layout = self.scaffold.content_layout

        # Internal sub-tabs for different diagnostic areas
        self.tabs = QTabWidget()
        configure_top_tabs(self.tabs)
        self.tabs.addTab(
            self._create_services_tab(),
            self.tr("Services"),
        )
        self.tabs.addTab(
            self._create_boot_tab(),
            self.tr("Boot Analysis"),
        )
        self.tabs.addTab(
            self._create_journal_tab(),
            self.tr("Journal"),
        )

        layout.addWidget(self.tabs)

    # ==================== Services ========================================

    def _create_services_tab(self: typing.Any) -> QWidget:
        """Create the services management sub-tab."""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # Filter controls
        filter_layout = QHBoxLayout()
        filter_layout.addWidget(QLabel(self.tr("Filter:")))

        self.service_filter = QComboBox()
        self.service_filter.setAccessibleName(self.tr("Service filter"))
        self.service_filter.addItem(self.tr("Gaming Services"), "gaming")
        self.service_filter.addItem(self.tr("Failed Services"), "failed")
        self.service_filter.addItem(self.tr("Active Services"), "active")
        self.service_filter.addItem(self.tr("All User Services"), "all")
        self.service_filter.currentIndexChanged.connect(self._refresh_services)
        filter_layout.addWidget(self.service_filter)

        filter_layout.addStretch()

        refresh_btn = QPushButton(self.tr("Refresh"))
        refresh_btn.setAccessibleName(self.tr("Refresh services"))
        refresh_btn.clicked.connect(self._refresh_services)
        filter_layout.addWidget(refresh_btn)

        layout.addLayout(filter_layout)

        # Service tree
        self.service_tree = QTreeWidget()
        self.service_tree.setHeaderLabels(
            [
                self.tr("Service"),
                self.tr("Status"),
                self.tr("Description"),
            ]
        )
        self.service_tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.service_tree.customContextMenuRequested.connect(self._show_service_menu)
        self.service_tree.setColumnWidth(0, 250)
        self.service_tree.setColumnWidth(1, 100)
        layout.addWidget(self.service_tree)

        # Status log
        self.service_log = QTextEdit()
        self.service_log.setReadOnly(True)
        self.service_log.setMaximumHeight(100)
        layout.addWidget(self.service_log)

        self._refresh_services()
        return widget

    # ==================== Boot Analysis ===================================

    def _create_boot_tab(self: typing.Any) -> QWidget:
        """Create the boot analysis sub-tab."""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # Boot stats summary
        stats_group = QGroupBox(self.tr("Boot Time Summary"))
        stats_layout = QVBoxLayout(stats_group)

        self.boot_stats_label = QLabel()
        self.boot_stats_label.setWordWrap(True)
        stats_layout.addWidget(self.boot_stats_label)

        # Visual bars for boot phases
        self.boot_bars_layout = QVBoxLayout()
        stats_layout.addLayout(self.boot_bars_layout)

        layout.addWidget(stats_group)

        # Slow services
        slow_group = QGroupBox(self.tr("Slowest Services (>5s)"))
        slow_layout = QVBoxLayout(slow_group)

        self.slow_services_list = QTextEdit()
        self.slow_services_list.setReadOnly(True)
        slow_layout.addWidget(self.slow_services_list)

        layout.addWidget(slow_group)

        # Optimisation suggestions
        opt_group = QGroupBox(self.tr("Optimization Suggestions"))
        opt_layout = QVBoxLayout(opt_group)

        self.suggestions_label = QLabel()
        self.suggestions_label.setWordWrap(True)
        opt_layout.addWidget(self.suggestions_label)

        layout.addWidget(opt_group)

        # Refresh button
        refresh_btn = QPushButton(self.tr("Analyze Boot"))
        refresh_btn.setAccessibleName(self.tr("Analyze Boot"))
        refresh_btn.clicked.connect(self._refresh_boot_analysis)
        layout.addWidget(refresh_btn)

        self._refresh_boot_analysis()
        return widget

    # ==================== Journal =========================================

    def _create_journal_tab(self: typing.Any) -> QWidget:
        """Create the journal viewer sub-tab."""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # Quick diagnostic
        diag_group = QGroupBox(self.tr("Quick Diagnostic"))
        diag_layout = QHBoxLayout(diag_group)

        self.error_count_label = QLabel()
        diag_layout.addWidget(self.error_count_label)

        self.failed_count_label = QLabel()
        diag_layout.addWidget(self.failed_count_label)

        diag_layout.addStretch()

        layout.addWidget(diag_group)

        # Journal output
        journal_group = QGroupBox(self.tr("Recent Errors"))
        journal_layout = QVBoxLayout(journal_group)

        self.journal_output = QTextEdit()
        self.journal_output.setReadOnly(True)
        self.journal_output.setObjectName("diagJournalOutput")
        journal_layout.addWidget(self.journal_output)

        layout.addWidget(journal_group)

        support_note = QLabel(
            self.tr(
                "Support export creates privacy-redacted diagnostic evidence for troubleshooting; "
                "it is not a backup, recovery point, or rollback mechanism."
            )
        )
        support_note.setWordWrap(True)
        layout.addWidget(support_note)

        # Action buttons
        btn_layout = QHBoxLayout()

        refresh_btn = QPushButton(self.tr("Refresh"))
        refresh_btn.setAccessibleName(self.tr("Refresh journal"))
        refresh_btn.clicked.connect(self._refresh_journal)
        btn_layout.addWidget(refresh_btn)

        btn_layout.addStretch()

        panic_btn = QPushButton(self.tr("Export Panic Log"))
        panic_btn.setAccessibleName(self.tr("Export Panic Log"))
        panic_btn.setObjectName("diagPanicBtn")
        panic_btn.clicked.connect(self._export_panic_log)
        btn_layout.addWidget(panic_btn)

        bundle_btn = QPushButton(self.tr("Export Support Bundle"))
        bundle_btn.setAccessibleName(self.tr("Export Support Bundle"))
        bundle_btn.clicked.connect(self._export_support_bundle)
        btn_layout.addWidget(bundle_btn)

        layout.addLayout(btn_layout)

        self._refresh_journal()
        return widget

    # ==================== Service logic ===================================

    def _refresh_services(self: typing.Any) -> typing.Any:
        """Refresh the services list."""
        self.service_tree.clear()
        filter_type = self.service_filter.currentData()

        # Get user services
        services = ServiceManager.list_units(UnitScope.USER, filter_type)

        # Add gaming services from system scope too
        if filter_type == "gaming":
            services.extend(ServiceManager.list_units(UnitScope.SYSTEM, filter_type))

        for service in services:
            item = QTreeWidgetItem(
                [
                    service.name,
                    self._state_to_emoji(service.state),
                    service.description[:50] if service.description else "",
                ]
            )
            item.setData(0, Qt.ItemDataRole.UserRole, service)
            self.service_tree.addTopLevelItem(item)

        self.service_log.append(self.tr("Loaded {} services").format(len(services)))

    def _state_to_emoji(self: typing.Any, state: UnitState) -> str:
        """Convert service state to display string."""
        mapping = {
            UnitState.ACTIVE: "active",
            UnitState.INACTIVE: "inactive",
            UnitState.FAILED: "failed",
            UnitState.ACTIVATING: "starting",
            UnitState.UNKNOWN: "unknown",
        }
        return mapping.get(state, "unknown")

    def _show_service_menu(self: typing.Any, position: typing.Any) -> typing.Any:
        """Show context menu for service actions."""
        item = self.service_tree.itemAt(position)
        if not item:
            return

        service = item.data(0, Qt.ItemDataRole.UserRole)
        if not service:
            return

        menu = QMenu()

        if service.state == UnitState.FAILED and service.scope == UnitScope.SYSTEM:
            review_action = menu.addAction(self.tr("Review Restart in Action Center"))
            review_action.triggered.connect(lambda: self._review_failed_service(service.name))
            menu.addSeparator()

        if service.state == UnitState.ACTIVE:
            stop_action = menu.addAction(self.tr("Stop"))
            stop_action.triggered.connect(lambda: self._service_action("stop", service))

            restart_action = menu.addAction(self.tr("Restart"))
            restart_action.triggered.connect(lambda: self._service_action("restart", service))
        else:
            start_action = menu.addAction(self.tr("Start"))
            start_action.triggered.connect(lambda: self._service_action("start", service))

        menu.addSeparator()

        mask_action = menu.addAction(self.tr("Mask (Disable)"))
        mask_action.triggered.connect(lambda: self._service_action("mask", service))

        unmask_action = menu.addAction(self.tr("Unmask"))
        unmask_action.triggered.connect(lambda: self._service_action("unmask", service))

        menu.exec(self.service_tree.viewport().mapToGlobal(position))

    def _review_failed_service(self: typing.Any, unit: str) -> None:
        """Navigate with an exact unit; never plan or execute from Diagnostics."""
        main_window = self.window() if hasattr(self, "window") else None
        switch = getattr(main_window, "switch_to_route", None)
        preselect = getattr(main_window, "_preselect_action_center", None)
        if not callable(switch) or not switch("maintenance:action-center"):
            return
        if callable(preselect):
            preselect("restart-failed-service", {"service": str(unit)})

    def _service_action(self: typing.Any, action: str, service: typing.Any) -> typing.Any:
        """Route general service changes to manual Action Center review."""
        scope = getattr(service.scope, "value", str(service.scope))
        self.actionCenterRequested.emit(
            "service-control",
            {"service": str(service.name), "action": str(action), "scope": str(scope)},
        )
        self.service_log.append(self.tr("Review this service change in Action Center."))

    # ==================== Boot analysis logic ==============================

    def _refresh_boot_analysis(self: typing.Any) -> typing.Any:
        """Refresh boot analysis data."""
        stats = BootAnalyzer.get_boot_stats()

        # Stats summary
        if stats.total_time:
            summary = f"Total boot time: {stats.total_time:.1f}s\n"
            if stats.firmware_time:
                summary += f"  \u2022 Firmware: {stats.firmware_time:.1f}s\n"
            if stats.loader_time:
                summary += f"  \u2022 Bootloader: {stats.loader_time:.1f}s\n"
            if stats.kernel_time:
                summary += f"  \u2022 Kernel: {stats.kernel_time:.1f}s\n"
            if stats.userspace_time:
                summary += f"  \u2022 Userspace: {stats.userspace_time:.1f}s"
            self.boot_stats_label.setText(summary)
        else:
            self.boot_stats_label.setText(self.tr("Unable to analyze boot (run as user, after first boot)"))

        # Slow services
        slow = BootAnalyzer.get_slow_services()
        if slow:
            slow_text = "\n".join(f"{s.service}: {s.time_seconds:.1f}s" for s in slow[:10])
            self.slow_services_list.setText(slow_text)
        else:
            self.slow_services_list.setText(self.tr("No services taking >5s to start"))

        # Suggestions
        suggestions = BootAnalyzer.get_optimization_suggestions()
        self.suggestions_label.setText("\n".join(suggestions))

    # ==================== Journal logic ====================================

    def _refresh_journal(self: typing.Any) -> typing.Any:
        """Refresh journal diagnostic view."""
        diag = JournalManager.get_quick_diagnostic()

        self.error_count_label.setText(self.tr("Errors: {}").format(diag["error_count"]))
        self.failed_count_label.setText(self.tr("Failed Services: {}").format(len(diag["failed_services"])))

        # Show recent errors
        errors = JournalManager.get_boot_errors()
        self.journal_output.setText(errors if errors else self.tr("No errors in current boot"))

    def _export_panic_log(self: typing.Any) -> typing.Any:
        """Export panic log for forum support."""
        result = JournalManager.export_panic_log()

        if result.success:
            QMessageBox.information(
                self,
                self.tr("Panic Log Exported"),
                self.tr("Log saved to:\n{path}\n\nYou can share this file when asking for help online.").format(
                    path=(result.data or {}).get("path", "")
                ),
            )
        else:
            QMessageBox.warning(self, self.tr("Export Failed"), result.message)

    def _export_support_bundle(self: typing.Any) -> typing.Any:
        """Export support bundle ZIP."""
        result = JournalManager.export_support_bundle()

        if result.success:
            QMessageBox.information(
                self,
                self.tr("Support Bundle Exported"),
                self.tr("Bundle saved to:\n{path}\n\nShare this ZIP file when reporting issues.").format(
                    path=(result.data or {}).get("path", "")
                ),
            )
        else:
            QMessageBox.warning(self, self.tr("Export Failed"), result.message)


# ---------------------------------------------------------------------------
# Sub-tab: Boot (Kernel, ZRAM, Secure Boot)
# ---------------------------------------------------------------------------


class _BootSubTab(QWidget):
    """Sub-tab for kernel parameters, ZRAM, and Secure Boot management.

    Preserves every feature from the original BootTab:
    - Current kernel cmdline display
    - Common parameter quick-add checkboxes (AMD GPU, Intel IOMMU,
      NVIDIA modesetting, mitigations, watchdog)
    - Custom parameter add/remove
    - GRUB backup / restore
    - ZRAM configuration (size slider, compression algorithm)
    - Secure Boot status and MOK key generation / enrollment
    - Output log
    """

    actionCenterRequested = pyqtSignal(str, object)

    def __init__(self: typing.Any) -> None:
        super().__init__()
        self.init_ui()
        self.refresh_all()

    def init_ui(self: typing.Any) -> typing.Any:
        """Initialise the UI components."""
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        self.scaffold = PageScaffold(
            self.tr("Boot Diagnostics"),
            self.tr("Inspect and manage boot-time configuration and security."),
        )
        root.addWidget(self.scaffold)
        layout = self.scaffold.content_layout
        layout.setSpacing(15)

        # Kernel Parameters Section
        layout.addWidget(self.create_kernel_section())

        # ZRAM Section
        layout.addWidget(self.create_zram_section())

        # Secure Boot Section
        layout.addWidget(self.create_secureboot_section())

        # Output Log
        output_group = QGroupBox(self.tr("Output Log:"))
        output_layout = QVBoxLayout(output_group)
        self.output_text = QTextEdit()
        self.output_text.setReadOnly(True)
        self.output_text.setMaximumHeight(150)
        output_layout.addWidget(self.output_text)
        layout.addWidget(output_group)

        layout.addStretch()

    # ==================== Kernel Section ==================================

    def create_kernel_section(self: typing.Any) -> QGroupBox:
        """Create the kernel parameters section."""
        group = QGroupBox(self.tr("Kernel Parameters"))
        layout = QVBoxLayout(group)

        # Current parameters display
        current_layout = QHBoxLayout()
        current_layout.addWidget(QLabel(self.tr("Current cmdline:")))
        self.current_params_label = QLabel()
        self.current_params_label.setWordWrap(True)
        self.current_params_label.setObjectName("diagKernelParams")
        current_layout.addWidget(self.current_params_label, 1)
        layout.addLayout(current_layout)

        # Common parameters checkboxes
        params_group = QGroupBox(self.tr("Quick Add Parameters"))
        params_layout = QVBoxLayout(params_group)

        self.param_checkboxes = {}
        common_params = [
            ("amdgpu.ppfeaturemask=0xffffffff", self.tr("AMD GPU: Enable all power features")),
            ("intel_iommu=on", self.tr("Intel IOMMU: GPU passthrough support")),
            ("nvidia-drm.modeset=1", self.tr("NVIDIA: Kernel modesetting")),
            ("mitigations=off", self.tr("Disable CPU mitigations (unsafe but faster)")),
            ("nowatchdog", self.tr("Disable watchdog (reduce interrupts)")),
        ]

        for param, desc in common_params:
            cb = QCheckBox(desc)
            cb.setAccessibleName(desc)
            cb.setProperty("param", param)
            cb.stateChanged.connect(lambda state, p=param: self.on_param_toggled(p, state))
            self.param_checkboxes[param] = cb
            params_layout.addWidget(cb)

        layout.addWidget(params_group)

        # Custom parameter input
        custom_layout = QHBoxLayout()
        custom_layout.addWidget(QLabel(self.tr("Custom:")))
        self.custom_param_input = QLineEdit()
        self.custom_param_input.setAccessibleName(self.tr("Custom kernel parameter"))
        self.custom_param_input.setPlaceholderText("e.g., mem=4G")
        custom_layout.addWidget(self.custom_param_input)

        add_btn = QPushButton(self.tr("Add"))
        add_btn.setAccessibleName(self.tr("Add custom parameter"))
        add_btn.clicked.connect(self.add_custom_param)
        custom_layout.addWidget(add_btn)

        remove_btn = QPushButton(self.tr("Remove"))
        remove_btn.setAccessibleName(self.tr("Remove custom parameter"))
        remove_btn.clicked.connect(self.remove_custom_param)
        custom_layout.addWidget(remove_btn)

        layout.addLayout(custom_layout)

        # Backup/Restore
        backup_layout = QHBoxLayout()
        backup_btn = QPushButton(self.tr("Backup GRUB"))
        backup_btn.setAccessibleName(self.tr("Backup GRUB"))
        backup_btn.clicked.connect(self.backup_grub)
        backup_layout.addWidget(backup_btn)

        restore_btn = QPushButton(self.tr("Restore Backup"))
        restore_btn.setAccessibleName(self.tr("Restore Backup"))
        restore_btn.clicked.connect(self.restore_grub)
        backup_layout.addWidget(restore_btn)

        backup_layout.addStretch()
        layout.addLayout(backup_layout)

        return group

    # ==================== ZRAM Section ====================================

    def create_zram_section(self: typing.Any) -> QGroupBox:
        """Create the ZRAM configuration section."""
        group = QGroupBox(self.tr("ZRAM (Compressed Swap)"))
        layout = QVBoxLayout(group)

        # Status
        status_layout = QHBoxLayout()
        self.zram_status_label = QLabel()
        status_layout.addWidget(self.zram_status_label)
        status_layout.addStretch()
        layout.addLayout(status_layout)

        # Size slider
        size_layout = QHBoxLayout()
        size_layout.addWidget(QLabel(self.tr("Size (% of RAM):")))

        self.zram_slider = QSlider(Qt.Orientation.Horizontal)
        self.zram_slider.setAccessibleName(self.tr("ZRAM size percent of RAM"))
        self.zram_slider.setMinimum(25)
        self.zram_slider.setMaximum(150)
        self.zram_slider.setValue(100)
        self.zram_slider.setTickInterval(25)
        self.zram_slider.setTickPosition(QSlider.TickPosition.TicksBelow)
        self.zram_slider.valueChanged.connect(self.on_zram_slider_changed)
        size_layout.addWidget(self.zram_slider)

        self.zram_size_label = QLabel("100%")
        self.zram_size_label.setMinimumWidth(50)
        size_layout.addWidget(self.zram_size_label)

        layout.addLayout(size_layout)

        # Algorithm
        algo_layout = QHBoxLayout()
        algo_layout.addWidget(QLabel(self.tr("Compression:")))

        self.zram_algo_combo = QComboBox()
        self.zram_algo_combo.setAccessibleName(self.tr("ZRAM compression algorithm"))
        for algo, desc in ZramManager.ALGORITHMS.items():
            self.zram_algo_combo.addItem(f"{algo} - {desc}", algo)
        algo_layout.addWidget(self.zram_algo_combo, 1)

        layout.addLayout(algo_layout)

        # Apply button
        btn_layout = QHBoxLayout()
        apply_btn = QPushButton(self.tr("Apply ZRAM Settings"))
        apply_btn.setAccessibleName(self.tr("Apply ZRAM Settings"))
        apply_btn.clicked.connect(self.apply_zram)
        btn_layout.addWidget(apply_btn)
        btn_layout.addStretch()
        layout.addLayout(btn_layout)

        return group

    # ==================== Secure Boot Section =============================

    def create_secureboot_section(self: typing.Any) -> QGroupBox:
        """Create the Secure Boot section."""
        group = QGroupBox(self.tr("Secure Boot (MOK Management)"))
        layout = QVBoxLayout(group)

        # Status
        self.sb_status_label = QLabel()
        layout.addWidget(self.sb_status_label)

        # Key status
        self.mok_status_label = QLabel()
        layout.addWidget(self.mok_status_label)

        # Actions
        btn_layout = QHBoxLayout()

        generate_btn = QPushButton(self.tr("Generate MOK Key"))
        generate_btn.setAccessibleName(self.tr("Generate MOK Key"))
        generate_btn.clicked.connect(self.generate_mok_key)
        btn_layout.addWidget(generate_btn)

        enroll_btn = QPushButton(self.tr("Enroll Key"))
        enroll_btn.setAccessibleName(self.tr("Enroll Key"))
        enroll_btn.clicked.connect(self.enroll_mok_key)
        btn_layout.addWidget(enroll_btn)

        btn_layout.addStretch()
        layout.addLayout(btn_layout)

        # Help text
        help_label = QLabel(self.tr("MOK keys are needed to sign third-party kernel modules (NVIDIA, VirtualBox) when Secure Boot is enabled."))
        help_label.setWordWrap(True)
        help_label.setObjectName("diagSecureBootHelp")
        layout.addWidget(help_label)

        return group

    # ==================== Refresh helpers =================================

    def refresh_all(self: typing.Any) -> typing.Any:
        """Refresh all sections with current data."""
        self.refresh_kernel()
        self.refresh_zram()
        self.refresh_secureboot()

    def refresh_kernel(self: typing.Any) -> typing.Any:
        """Refresh kernel parameters display."""
        current = KernelManager.get_current_params()
        self.current_params_label.setText(" ".join(current[:10]) + ("..." if len(current) > 10 else ""))

        # Update checkboxes
        for param, cb in self.param_checkboxes.items():
            cb.blockSignals(True)
            cb.setChecked(KernelManager.has_param(param))
            cb.blockSignals(False)

    def refresh_zram(self: typing.Any) -> typing.Any:
        """Refresh ZRAM status."""
        config = ZramManager.get_current_config()
        usage = ZramManager.get_current_usage()

        status_parts = []
        if config.enabled:
            status_parts.append(self.tr("Active"))
            if usage:
                status_parts.append(f"{usage[0]}MB / {usage[1]}MB")
        else:
            status_parts.append(self.tr("Inactive"))

        status_parts.append(f"{config.size_percent}% RAM ({config.size_mb}MB)")
        status_parts.append(f"{config.algorithm}")

        self.zram_status_label.setText(" | ".join(status_parts))

        self.zram_slider.blockSignals(True)
        self.zram_slider.setValue(config.size_percent)
        self.zram_slider.blockSignals(False)
        self.zram_size_label.setText(f"{config.size_percent}%")

        # Set algorithm combobox
        idx = self.zram_algo_combo.findData(config.algorithm)
        if idx >= 0:
            self.zram_algo_combo.setCurrentIndex(idx)

    def refresh_secureboot(self: typing.Any) -> typing.Any:
        """Refresh Secure Boot status."""
        status = SecureBootManager.get_status()

        if status.secure_boot_enabled:
            self.sb_status_label.setText(self.tr("Secure Boot: Enabled"))
        else:
            self.sb_status_label.setText(self.tr("Secure Boot: Disabled"))

        if SecureBootManager.has_keys():
            self.mok_status_label.setText(self.tr("MOK Key: Generated"))
        else:
            self.mok_status_label.setText(self.tr("MOK Key: Not generated"))

        if status.pending_mok:
            self.mok_status_label.setText(self.mok_status_label.text() + f" ({self.tr('Pending enrollment')})")

    def log(self: typing.Any, message: str) -> typing.Any:
        """Add message to output log."""
        self.output_text.append(message)

    # ==================== Kernel actions ==================================

    def on_param_toggled(self: typing.Any, param: str, state: int) -> typing.Any:
        """Handle parameter checkbox toggle."""
        self.actionCenterRequested.emit(
            "configure-kernel-parameter",
            {"parameter": param, "enabled": state == Qt.CheckState.Checked.value},
        )
        self.log(self.tr("Review the kernel parameter change in Action Center."))

    def add_custom_param(self: typing.Any) -> typing.Any:
        """Add a custom kernel parameter."""
        param = self.custom_param_input.text().strip()
        if param:
            self.actionCenterRequested.emit("configure-kernel-parameter", {"parameter": param, "enabled": True})
            self.log(self.tr("Review the kernel parameter change in Action Center."))
            self.custom_param_input.clear()

    def remove_custom_param(self: typing.Any) -> typing.Any:
        """Remove a custom kernel parameter."""
        param = self.custom_param_input.text().strip()
        if param:
            self.actionCenterRequested.emit("configure-kernel-parameter", {"parameter": param, "enabled": False})
            self.log(self.tr("Review the kernel parameter change in Action Center."))
            self.custom_param_input.clear()

    def backup_grub(self: typing.Any) -> typing.Any:
        """Create GRUB backup."""
        result = KernelManager.backup_grub()
        self.log(result.message)
        if result.backup_path:
            self.log(self.tr("Saved to: {}").format(result.backup_path))

    def restore_grub(self: typing.Any) -> typing.Any:
        """Restore GRUB from backup."""
        backups = KernelManager.get_backups()
        if not backups:
            self.log(self.tr("No backups available."))
            return

        # Show backup selection
        items = [str(b.name) for b in backups[:10]]
        item, ok = QInputDialog.getItem(
            self,
            self.tr("Select Backup"),
            self.tr("Choose a backup to restore:"),
            items,
            0,
            False,
        )

        if ok and item:
            self.actionCenterRequested.emit("restore-grub-backup", {"backup": str(item)})
            self.log(self.tr("Review GRUB restoration guidance in Action Center."))

    # ==================== ZRAM actions ====================================

    def on_zram_slider_changed(self: typing.Any, value: int) -> typing.Any:
        """Update ZRAM size label."""
        self.zram_size_label.setText(f"{value}%")

    def apply_zram(self: typing.Any) -> typing.Any:
        """Apply ZRAM settings."""
        size = self.zram_slider.value()
        algo = self.zram_algo_combo.currentData()

        self.actionCenterRequested.emit(
            "configure-zram",
            {"size_percent": int(size), "algorithm": str(algo)},
        )
        self.log(self.tr("Review ZRAM configuration guidance in Action Center."))

    # ==================== Secure Boot actions ==============================

    def generate_mok_key(self: typing.Any) -> typing.Any:
        """Route MOK key generation without collecting a secret in this view."""
        self.actionCenterRequested.emit("generate-mok-key", {})
        self.log(self.tr("Passwords are never stored in plans; review MOK key guidance in Action Center."))

    def enroll_mok_key(self: typing.Any) -> typing.Any:
        """Enroll MOK key for Secure Boot."""
        if not SecureBootManager.has_keys():
            self.log(self.tr("No MOK key found. Generate one first."))
            return

        self.actionCenterRequested.emit("enroll-mok-key", {})
        self.log(self.tr("Passwords are never stored in plans; review MOK enrollment guidance in Action Center."))


# ---------------------------------------------------------------------------
# Main consolidated tab
# ---------------------------------------------------------------------------


class DiagnosticsTab(BaseTab):
    """Consolidated diagnostics tab merging Watchtower and Boot.

    Uses a route-owned stack between the Watchtower diagnostic suite
    and Boot configuration without duplicating shell navigation.
    """

    _METADATA = plugin_metadata_for_module(__name__)

    def metadata(self: typing.Any) -> PluginMetadata:
        return typing.cast(PluginMetadata, self._METADATA)

    def create_widget(self: typing.Any) -> QWidget:
        return self

    def __init__(self: typing.Any) -> None:
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.pages = QStackedWidget()
        self.pages.setObjectName("diagnosticsRouteStack")
        watchtower = _WatchtowerSubTab()
        boot = _BootSubTab()
        watchtower.actionCenterRequested.connect(self.actionCenterRequested.emit)
        boot.actionCenterRequested.connect(self.actionCenterRequested.emit)
        self.pages.addWidget(watchtower)
        self.pages.addWidget(boot)

        layout.addWidget(self.pages)

    def activate_route(self: typing.Any, route: typing.Any) -> bool:
        """Select Troubleshooting or Boot from the stable shell route."""
        subroute = str(getattr(route, "subroute", "") or "")
        if subroute not in {"", "watchtower", "boot"}:
            return False
        self.pages.setCurrentIndex(1 if subroute == "boot" else 0)
        return True
