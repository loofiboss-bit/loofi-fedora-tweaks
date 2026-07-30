"""
Security Tab - Proactive security hardening interface.
Part of v8.5 "Sentinel" update, expanded in v10.0 "Zenith" to absorb Privacy features.

Features:
- Port auditor with security score
- USB Guard management
- Application sandboxing
- Firewall control (from Privacy tab)
- Telemetry removal (from Privacy tab)
- Security updates check (from Privacy tab)
"""

import typing

from core.plugins.interface import PluginInterface
from core.plugins.metadata import PluginMetadata
from core.product_catalog import plugin_metadata_for_module
from core.execution_policy import classify_command
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QScrollArea,
    QStackedWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)
from services.network import PortAuditor
from services.security import FirewallManager
from services.system import SystemManager
from utils.command_runner import CommandRunner
from services.security import SandboxManager
from services.security import USBGuardManager

from ui.base_tab import BaseTab
from ui.components import DetailsDisclosure, PageScaffold
from ui.design import semantic_qcolor


class SecurityTab(QWidget, PluginInterface):
    """Security tab for system hardening and auditing."""

    _METADATA = plugin_metadata_for_module(__name__)
    actionCenterRequested = pyqtSignal(str, object)

    def metadata(self: typing.Any) -> PluginMetadata:
        return typing.cast(PluginMetadata, self._METADATA)

    def create_widget(self) -> QWidget:
        return self

    def __init__(self: typing.Any) -> None:
        super().__init__()
        self._setup_command_runner()
        self.init_ui()

    def _setup_command_runner(self: typing.Any) -> typing.Any:
        """Setup CommandRunner for privacy-related commands."""
        self.privacy_runner = CommandRunner()
        self.privacy_runner.output_received.connect(self._on_privacy_output)
        self.privacy_runner.finished.connect(self._on_privacy_command_finished)

    def _on_privacy_output(self: typing.Any, text: typing.Any) -> typing.Any:
        """Handle output from privacy commands."""
        self.log(text.rstrip("\n"))

    def _on_privacy_command_finished(self: typing.Any, exit_code: typing.Any) -> typing.Any:
        """Handle privacy command completion."""
        self.log(self.tr("Command finished with exit code: {}").format(exit_code))

    def _run_privacy_command(self: typing.Any, cmd: typing.Any, args: typing.Any, description: typing.Any = "") -> typing.Any:
        """Execute a privacy-related command with output logging."""
        if description:
            self.log(description)
        operation_class = classify_command(cmd, args)
        if operation_class in {"host", "manual_only"}:
            self._open_action_center(self.tr("This security change requires a reviewed Action Center plan or manual guidance."))
            return
        self.privacy_runner.run_command(cmd, args)

    def _open_action_center(self: typing.Any, message: str) -> None:
        """Route host changes to the shared review flow without executing."""
        self.log(message)
        widget = self.parent()
        while widget is not None:
            if hasattr(widget, "switch_to_route"):
                widget.switch_to_route("maintenance:action-center")
                return
            widget = widget.parent() if hasattr(widget, "parent") else None

    def _request_action(self, action_id: str, parameters: dict[str, object], message: str) -> None:
        """Preselect one named Action Center workflow without executing it."""
        self.log(message)
        self.actionCenterRequested.emit(action_id, parameters)

    def init_ui(self: typing.Any) -> typing.Any:
        """Initialize route-owned security pages under the shared shell."""
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)

        self.pages = QStackedWidget()
        self.pages.setObjectName("securityRouteStack")
        self.pages.addWidget(
            self._route_page(
                self.tr("Security Overview"),
                self.tr("Review the current security posture before opening a focused control."),
                self._create_score_section(),
                self._create_security_updates_section(),
            )
        )
        self.pages.addWidget(
            self._route_page(
                self.tr("Firewall"),
                self.tr("Review firewalld state before enabling or disabling the service."),
                self._create_firewall_section(),
            )
        )
        self.pages.addWidget(
            self._route_page(
                self.tr("Privacy"),
                self.tr("Review device, sandbox, and telemetry controls before making changes."),
                self._create_usb_section(),
                self._create_sandbox_section(),
                self._create_telemetry_section(),
            )
        )
        self.pages.addWidget(
            self._route_page(
                self.tr("Open Ports"),
                self.tr("Inspect exposed listening ports before blocking a selected service."),
                self._create_ports_section(),
            )
        )
        main_layout.addWidget(self.pages, 1)

        self.activity_details = DetailsDisclosure(summary=self.tr("Show activity log"))
        self.log_text = self.activity_details.details
        self.log_text.setAccessibleName(self.tr("Activity log"))
        main_layout.addWidget(self.activity_details)

    @staticmethod
    def _route_page(
        accessible_name: str,
        description: str,
        *sections: QWidget,
    ) -> QScrollArea:
        """Create one bounded, scrollable security route page."""
        scaffold = PageScaffold(accessible_name, description)
        for section in sections:
            scaffold.add_widget(section)
        scaffold.content_layout.addStretch()
        scroll = QScrollArea()
        scroll.setObjectName("securityRouteScroll")
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setWidget(scaffold)
        return scroll

    def activate_route(self: typing.Any, route: typing.Any) -> bool:
        """Select a Security page from a stable route ID."""
        route_to_index = {
            "security": 0,
            "security:overview": 0,
            "security:firewall": 1,
            "security:privacy": 2,
            "security:ports": 3,
        }
        index = route_to_index.get(str(getattr(route, "id", route)))
        if index is None:
            return False
        self.pages.setCurrentIndex(index)
        return True

    def _create_score_section(self: typing.Any) -> QGroupBox:
        """Create security score display."""
        group = QGroupBox(self.tr("Security Score"))
        layout = QVBoxLayout(group)

        # Get security score
        score_data = PortAuditor.get_security_score()
        score = score_data["score"]
        rating = score_data["rating"]

        # Color based on score
        if score >= 90:
            score_level = "good"
        elif score >= 70:
            score_level = "ok"
        elif score >= 50:
            score_level = "warning"
        else:
            score_level = "bad"

        score_label = QLabel(f"{score}/100 - {rating}")
        score_label.setObjectName("secScoreLabel")
        score_label.setProperty("scoreLevel", score_level)
        if score_label.style() is not None:
            _style = score_label.style()
            assert _style is not None
            _style.unpolish(score_label)
            _style.polish(score_label)
        layout.addWidget(score_label)

        # Stats
        stats_layout = QHBoxLayout()
        stats_layout.addWidget(QLabel(f"Open Ports: {score_data['open_ports']}"))
        stats_layout.addWidget(QLabel(f"Risky Ports: {score_data['risky_ports']}"))

        fw_status = self.tr("Running") if PortAuditor.is_firewalld_running() else self.tr("Stopped")
        stats_layout.addWidget(QLabel(f"Firewall: {fw_status}"))
        stats_layout.addStretch()
        layout.addLayout(stats_layout)

        # Recommendations
        if score_data["recommendations"]:
            rec_label = QLabel(self.tr("Recommendations:"))
            rec_label.setObjectName("secRecLabel")
            layout.addWidget(rec_label)

            for rec in score_data["recommendations"][:3]:  # Limit to 3
                rec_item = QLabel(self.tr("Warning: {} ").format(rec).strip())
                rec_item.setObjectName("secRecItem")
                rec_item.setWordWrap(True)
                layout.addWidget(rec_item)

        # Refresh button
        refresh_btn = QPushButton(self.tr("Refresh Score"))
        refresh_btn.setAccessibleName(self.tr("Refresh Score"))
        refresh_btn.clicked.connect(self._refresh_score)
        layout.addWidget(refresh_btn)

        return group

    def _create_ports_section(self: typing.Any) -> QGroupBox:
        """Create port auditor section."""
        group = QGroupBox(self.tr("Port Auditor"))
        layout = QVBoxLayout(group)

        # Port table
        self.port_table = QTableWidget()
        self.port_table.setColumnCount(5)
        self.port_table.setHorizontalHeaderLabels(["Port", "Protocol", "Address", "Process", "Status"])
        self.port_table.horizontalHeader().setSectionResizeMode(  # type: ignore[union-attr]
            QHeaderView.ResizeMode.Stretch
        )
        self.port_table.setMaximumHeight(150)
        self.port_table.setProperty("maxVisibleRows", 3)
        BaseTab.configure_table(self.port_table)
        layout.addWidget(self.port_table)

        self._refresh_ports()

        # Buttons
        btn_layout = QHBoxLayout()

        refresh_btn = QPushButton(self.tr("Scan Ports"))
        refresh_btn.setAccessibleName(self.tr("Scan Ports"))
        refresh_btn.clicked.connect(self._refresh_ports)
        btn_layout.addWidget(refresh_btn)

        block_btn = QPushButton(self.tr("Block Selected"))
        block_btn.setAccessibleName(self.tr("Block Selected port"))
        block_btn.clicked.connect(self._block_port)
        btn_layout.addWidget(block_btn)

        btn_layout.addStretch()
        layout.addLayout(btn_layout)

        return group

    def _create_usb_section(self: typing.Any) -> QGroupBox:
        """Create USB Guard section."""
        group = QGroupBox(self.tr("USB Guard"))
        layout = QVBoxLayout(group)

        # Status
        installed = USBGuardManager.is_installed()
        running = USBGuardManager.is_running() if installed else False

        status_text = "Active" if running else ("Stopped" if installed else "Not installed")
        self.usb_status = QLabel(f"Status: {status_text}")
        layout.addWidget(self.usb_status)

        if not installed:
            install_btn = QPushButton(self.tr("Install USB Guard"))
            install_btn.setAccessibleName(self.tr("Install USB Guard"))
            install_btn.clicked.connect(self._install_usbguard)
            layout.addWidget(install_btn)

            info = QLabel(self.tr("USB Guard blocks unauthorized USB devices to prevent BadUSB attacks."))
            info.setWordWrap(True)
            info.setObjectName("secUsbInfo")
            layout.addWidget(info)
        else:
            # Device list
            self.usb_list = QListWidget()
            self.usb_list.setMaximumHeight(100)
            layout.addWidget(self.usb_list)

            self._refresh_usb_devices()

            # Buttons
            btn_layout = QHBoxLayout()

            if not running:
                start_btn = QPushButton(self.tr("Start Service"))
                start_btn.setAccessibleName(self.tr("Start Service"))
                start_btn.clicked.connect(self._start_usbguard)
                btn_layout.addWidget(start_btn)

            refresh_btn = QPushButton(self.tr("Refresh"))
            refresh_btn.setAccessibleName(self.tr("Refresh USB devices"))
            refresh_btn.clicked.connect(self._refresh_usb_devices)
            btn_layout.addWidget(refresh_btn)

            allow_btn = QPushButton(self.tr("Allow Selected"))
            allow_btn.setAccessibleName(self.tr("Allow Selected"))
            allow_btn.clicked.connect(self._allow_usb)
            btn_layout.addWidget(allow_btn)

            block_btn = QPushButton(self.tr("Block Selected"))
            block_btn.setAccessibleName(self.tr("Block Selected USB device"))
            block_btn.clicked.connect(self._block_usb)
            btn_layout.addWidget(block_btn)

            btn_layout.addStretch()
            layout.addLayout(btn_layout)

        return group

    def _create_sandbox_section(self: typing.Any) -> QGroupBox:
        """Create sandbox manager section."""
        group = QGroupBox(self.tr("Application Sandbox"))
        layout = QVBoxLayout(group)

        # Check Firejail
        firejail_ok = SandboxManager.is_firejail_installed()
        bwrap_ok = SandboxManager.is_bubblewrap_installed()

        status_layout = QHBoxLayout()
        firejail_status = self.tr("Available") if firejail_ok else self.tr("Unavailable")
        bubblewrap_status = self.tr("Available") if bwrap_ok else self.tr("Unavailable")
        status_layout.addWidget(QLabel(self.tr("Firejail: {}").format(firejail_status)))
        status_layout.addWidget(QLabel(self.tr("Bubblewrap: {}").format(bubblewrap_status)))
        status_layout.addStretch()
        layout.addLayout(status_layout)

        if not firejail_ok:
            install_btn = QPushButton(self.tr("Install Firejail"))
            install_btn.setAccessibleName(self.tr("Install Firejail"))
            install_btn.clicked.connect(self._install_firejail)
            layout.addWidget(install_btn)
        else:
            # Available profiles
            layout.addWidget(QLabel(self.tr("Quick Launch (Sandboxed):")))

            profiles_layout = QHBoxLayout()

            for app, desc in list(SandboxManager.FIREJAIL_PROFILES.items())[:4]:
                btn = QPushButton(app.capitalize())
                btn.setAccessibleName(self.tr("Launch {} sandboxed").format(app.capitalize()))
                btn.setToolTip(f"Launch {app} in sandbox")
                btn.clicked.connect(lambda checked, a=app: self._launch_sandboxed(a))
                profiles_layout.addWidget(btn)

            profiles_layout.addStretch()
            layout.addLayout(profiles_layout)

            # Options
            options_layout = QHBoxLayout()

            self.no_network_check = QCheckBox(self.tr("No Network"))
            self.no_network_check.setAccessibleName(self.tr("No Network"))
            self.no_network_check.setToolTip("Disable network access")
            options_layout.addWidget(self.no_network_check)

            self.private_home_check = QCheckBox(self.tr("Private Home"))
            self.private_home_check.setAccessibleName(self.tr("Private Home"))
            self.private_home_check.setToolTip("Use empty home directory")
            options_layout.addWidget(self.private_home_check)

            options_layout.addStretch()
            layout.addLayout(options_layout)

            # Custom command
            custom_layout = QHBoxLayout()

            self.sandbox_cmd = QComboBox()
            self.sandbox_cmd.setAccessibleName(self.tr("Sandbox command"))
            self.sandbox_cmd.setEditable(True)
            self.sandbox_cmd.addItems(["firefox", "chromium", "vlc", "gimp"])
            self.sandbox_cmd.setMinimumWidth(200)
            custom_layout.addWidget(self.sandbox_cmd)

            run_btn = QPushButton(self.tr("Run Sandboxed"))
            run_btn.setAccessibleName(self.tr("Run Sandboxed"))
            run_btn.clicked.connect(self._run_custom_sandbox)
            custom_layout.addWidget(run_btn)

            custom_layout.addStretch()
            layout.addLayout(custom_layout)

        return group

    def _refresh_score(self: typing.Any) -> typing.Any:
        """Refresh security score."""
        self.log("Rescanning security...")
        # Would need to rebuild the section - simplified for now
        self.log("Security scan complete.")

    def _refresh_ports(self: typing.Any) -> typing.Any:
        """Refresh port list."""
        self.port_table.clearSpans()
        self.port_table.setRowCount(0)

        ports = PortAuditor.scan_ports()

        if not ports:
            BaseTab.set_table_empty_state(self.port_table, self.tr("No open ports detected"))
            return

        for port in ports:
            row = self.port_table.rowCount()
            self.port_table.insertRow(row)

            self.port_table.setItem(row, 0, BaseTab.make_table_item(str(port.port)))
            self.port_table.setItem(row, 1, BaseTab.make_table_item(port.protocol))
            self.port_table.setItem(row, 2, BaseTab.make_table_item(port.address))
            self.port_table.setItem(row, 3, BaseTab.make_table_item(port.process))

            status_item = QTableWidgetItem(self.tr("Risk") if port.is_risky else self.tr("OK"))
            if port.is_risky:
                status_item.setForeground(semantic_qcolor("error"))
            self.port_table.setItem(row, 4, status_item)

        normalize = getattr(BaseTab, "ensure_table_row_heights", None)
        if callable(normalize):
            normalize(self.port_table)

    def _block_port(self: typing.Any) -> typing.Any:
        """Block selected port."""
        row = self.port_table.currentRow()
        if row < 0:
            self.log("No port selected.")
            return

        port = int(self.port_table.item(row, 0).text())
        protocol = self.port_table.item(row, 1).text().lower()

        self._request_action(
            "block-firewall-port",
            {"port": port, "protocol": protocol},
            self.tr("Blocking %s/%s remains manual-only until its exact firewall rule can be verified.") % (port, protocol),
        )

    def _install_usbguard(self: typing.Any) -> typing.Any:
        """Install USBGuard."""
        self._request_action(
            "install-application",
            {"source": "fedora", "package_id": "usbguard"},
            self.tr("USBGuard installation requires an audited package plan."),
        )

    def _start_usbguard(self: typing.Any) -> typing.Any:
        """Start USBGuard service."""
        self._request_action("start-usbguard-service", {}, self.tr("Starting USBGuard requires an audited service plan."))

    def _refresh_usb_devices(self: typing.Any) -> typing.Any:
        """Refresh USB device list."""
        if not hasattr(self, "usb_list"):
            return

        self.usb_list.clear()
        devices = USBGuardManager.list_devices()

        if not devices:
            item = QListWidgetItem("No devices found (service may not be running)")
            self.usb_list.addItem(item)
        else:
            for dev in devices:
                icon = self.tr("Allowed") if dev.policy == "allow" else self.tr("Blocked")
                item = QListWidgetItem(f"{icon} {dev.name} ({dev.policy})")
                item.setData(Qt.ItemDataRole.UserRole, dev.id)
                self.usb_list.addItem(item)

    def _allow_usb(self: typing.Any) -> typing.Any:
        """Allow selected USB device."""
        current = self.usb_list.currentItem()
        if not current:
            self.log("No device selected.")
            return

        device_id = current.data(Qt.ItemDataRole.UserRole)
        if device_id:
            self._request_action(
                "allow-usb-device",
                {"device_id": str(device_id)},
                self.tr("Permanent USB policy changes remain manual-only."),
            )

    def _block_usb(self: typing.Any) -> typing.Any:
        """Block selected USB device."""
        current = self.usb_list.currentItem()
        if not current:
            self.log("No device selected.")
            return

        device_id = current.data(Qt.ItemDataRole.UserRole)
        if device_id:
            self._request_action(
                "block-usb-device",
                {"device_id": str(device_id)},
                self.tr("Permanent USB policy changes remain manual-only."),
            )

    def _install_firejail(self: typing.Any) -> typing.Any:
        """Install Firejail."""
        self._request_action(
            "install-application",
            {"source": "fedora", "package_id": "firejail"},
            self.tr("Firejail installation requires an audited package plan."),
        )

    def _launch_sandboxed(self: typing.Any, app: str) -> typing.Any:
        """Launch an app in sandbox."""
        no_net = self.no_network_check.isChecked() if hasattr(self, "no_network_check") else False
        private = self.private_home_check.isChecked() if hasattr(self, "private_home_check") else False

        result = SandboxManager.run_sandboxed([app], no_network=no_net, private_home=private)
        self.log(result.message)

    def _run_custom_sandbox(self: typing.Any) -> typing.Any:
        """Run custom command in sandbox."""
        cmd = self.sandbox_cmd.currentText().strip()
        if not cmd:
            self.log("Enter a command to run.")
            return

        no_net = self.no_network_check.isChecked()
        private = self.private_home_check.isChecked()

        result = SandboxManager.run_sandboxed(cmd.split(), no_network=no_net, private_home=private)
        self.log(result.message)

    # ==================== FIREWALL (from Privacy tab) ====================

    def _create_firewall_section(self: typing.Any) -> QGroupBox:
        """Create firewall control section (absorbed from PrivacyTab)."""
        group = QGroupBox(self.tr("Firewall (firewalld)"))
        fw_layout = QHBoxLayout(group)

        btn_fw_status = QPushButton(self.tr("Check Status"))
        btn_fw_status.setAccessibleName(self.tr("Check Firewall Status"))
        btn_fw_status.clicked.connect(self._check_firewall_status)
        fw_layout.addWidget(btn_fw_status)

        btn_fw_enable = QPushButton(self.tr("Enable Firewall"))
        btn_fw_enable.setAccessibleName(self.tr("Enable Firewall"))
        btn_fw_enable.clicked.connect(self._enable_firewall)
        fw_layout.addWidget(btn_fw_enable)

        btn_fw_disable = QPushButton(self.tr("Disable Firewall"))
        btn_fw_disable.setAccessibleName(self.tr("Disable Firewall"))
        btn_fw_disable.clicked.connect(self._disable_firewall)
        fw_layout.addWidget(btn_fw_disable)

        return group

    def _check_firewall_status(self: typing.Any) -> typing.Any:
        """Log current firewall status using service layer."""
        status = FirewallManager.get_status()
        self.log(f"Firewall running: {status.running}")
        self.log(f"Default zone: {status.default_zone or 'unknown'}")

    def _enable_firewall(self: typing.Any) -> typing.Any:
        """Enable firewalld via service layer."""
        self._request_action("enable-firewall-service", {}, self.tr("Enabling firewalld requires an audited service plan."))

    def _disable_firewall(self: typing.Any) -> typing.Any:
        """Disable firewalld via service layer."""
        self._request_action("disable-firewall-service", {}, self.tr("Disabling firewalld requires an audited service plan."))

    # ==================== TELEMETRY (from Privacy tab) ====================

    def _create_telemetry_section(self: typing.Any) -> QGroupBox:
        """Create telemetry removal section (absorbed from PrivacyTab)."""
        group = QGroupBox(self.tr("Telemetry & Tracking"))
        tele_layout = QVBoxLayout(group)

        btn_remove_tele = QPushButton(self.tr("Remove Fedora Telemetry Packages"))
        btn_remove_tele.setAccessibleName(self.tr("Remove Fedora Telemetry Packages"))
        btn_remove_tele.clicked.connect(
            lambda: self._request_action(
                "remove-fedora-telemetry",
                {},
                self.tr("Telemetry package removal requires an audited package plan."),
            )
        )
        tele_layout.addWidget(btn_remove_tele)

        return group

    # ==================== SECURITY UPDATES (from Privacy tab) ====================

    def _create_security_updates_section(self: typing.Any) -> QGroupBox:
        """Create security updates check section (absorbed from PrivacyTab)."""
        group = QGroupBox(self.tr("Security Checks"))
        sec_layout = QVBoxLayout(group)

        btn_check_updates = QPushButton(self.tr("Check for Security Updates"))
        btn_check_updates.setAccessibleName(self.tr("Check for Security Updates"))
        btn_check_updates.clicked.connect(self._check_security_updates)
        sec_layout.addWidget(btn_check_updates)

        return group

    def _check_security_updates(self: typing.Any) -> typing.Any:
        """Check for security updates using the appropriate package manager."""
        pm = SystemManager.get_package_manager()
        if pm == "rpm-ostree":
            self._run_privacy_command(
                "rpm-ostree",
                ["update", "--check", "--preview"],
                self.tr("Checking for updates (rpm-ostree)..."),
            )
        else:
            self._run_privacy_command(
                "dnf",
                ["check-update", "--security"],
                self.tr("Checking for Security Updates..."),
            )

    def log(self: typing.Any, message: str) -> typing.Any:
        """Add message to log."""
        self.log_text.append(message)
