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
    QComboBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMenu,
    QMessageBox,
    QPushButton,
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
    - Services browser with failed/active/all-user filters
    - Right-click context menu that routes review requests to Action Center
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
            review_action = menu.addAction(self.tr("Review restart in Action Center"))
            review_action.triggered.connect(lambda: self._review_failed_service(service.name))
        else:
            review_action = menu.addAction(self.tr("Review service guidance"))
            review_action.triggered.connect(lambda: self._service_action("review", service))

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
            "legacy-ui-manual-review",
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
    """Read-only boot diagnostics plus reviewed Secure Boot handoffs."""

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
            self.tr("Inspect boot-time state and review supported security handoffs."),
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
        """Create a read-only kernel state section.

        Kernel parameters and GRUB configuration are intentionally outside the
        maintained product boundary.  Users can still copy the observed state
        into a support bundle or follow their distribution's native tooling.
        """
        group = QGroupBox(self.tr("Kernel Parameters"))
        layout = QVBoxLayout(group)

        current_layout = QHBoxLayout()
        current_layout.addWidget(QLabel(self.tr("Current cmdline:")))
        self.current_params_label = QLabel()
        self.current_params_label.setWordWrap(True)
        self.current_params_label.setObjectName("diagKernelParams")
        current_layout.addWidget(self.current_params_label, 1)
        layout.addLayout(current_layout)
        note = QLabel(
            self.tr(
                "Kernel and boot-loader changes are not offered here. "
                "Use the native Fedora workflow after reviewing this state."
            )
        )
        note.setWordWrap(True)
        layout.addWidget(note)

        return group

    # ==================== ZRAM Section ====================================

    def create_zram_section(self: typing.Any) -> QGroupBox:
        """Create a read-only ZRAM state section."""
        group = QGroupBox(self.tr("ZRAM (Compressed Swap)"))
        layout = QVBoxLayout(group)

        self.zram_status_label = QLabel()
        self.zram_status_label.setWordWrap(True)
        layout.addWidget(self.zram_status_label)
        note = QLabel(self.tr("ZRAM configuration is observed for diagnostics and is not changed by this application."))
        note.setWordWrap(True)
        layout.addWidget(note)

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
    """Canonical Troubleshoot journey with retained Watchtower and Boot routes.

    Uses one route-owned stack without duplicating shell navigation or history.
    """

    _METADATA = plugin_metadata_for_module(__name__)
    routeRequested = pyqtSignal(str, object)

    def metadata(self: typing.Any) -> PluginMetadata:
        return typing.cast(PluginMetadata, self._METADATA)

    def create_widget(self) -> QWidget:
        return self

    def __init__(self: typing.Any) -> None:
        super().__init__()
        from ui.troubleshoot_widget import TroubleshootWidget

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.pages = QStackedWidget()
        self.pages.setObjectName("diagnosticsRouteStack")
        self.troubleshoot = TroubleshootWidget()
        watchtower = _WatchtowerSubTab()
        boot = _BootSubTab()
        self.troubleshoot.actionCenterRequested.connect(
            self.actionCenterRequested.emit
        )
        self.troubleshoot.routeRequested.connect(self.routeRequested.emit)
        watchtower.actionCenterRequested.connect(self.actionCenterRequested.emit)
        boot.actionCenterRequested.connect(self.actionCenterRequested.emit)
        self.pages.addWidget(self.troubleshoot)
        self.pages.addWidget(watchtower)
        self.pages.addWidget(boot)

        layout.addWidget(self.pages)

    def activate_route(self: typing.Any, route: typing.Any) -> bool:
        """Select Troubleshooting or Boot from the stable shell route."""
        subroute = str(getattr(route, "subroute", "") or "")
        if subroute not in {"", "watchtower", "boot"}:
            return False
        self.pages.setCurrentIndex(
            2 if subroute == "boot" else 1 if subroute == "watchtower" else 0
        )
        return True

    def cleanup(self) -> None:
        """Cancel only the currently running explicit troubleshooting session."""
        self.troubleshoot.cleanup()
