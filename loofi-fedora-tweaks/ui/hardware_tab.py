"""
Hardware Tab - Consolidated hardware control interface.
CPU Governor, GPU Mode, Fan Control, Battery Limits
Expanded in v10.0 "Zenith" to absorb Tweaks tab features:
- Audio services restart (Pipewire)
- Battery charge limit control
- Fingerprint enrollment
"""

import typing

from core.plugins.interface import PluginInterface
from core.plugins.metadata import PluginMetadata
from core.product_catalog import plugin_metadata_for_module
from core.execution_policy import classify_command
from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtWidgets import (
    QComboBox,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QSlider,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)
from services.hardware import BluetoothManager, HardwareManager
from utils.command_runner import CommandRunner
from utils.log import get_logger

from ui.tooltips import HW_CPU_GOVERNOR, HW_FAN_MODE
from ui.components.layout import PageScaffold

logger = get_logger(__name__)


class HardwareTab(QWidget, PluginInterface):
    """Consolidated hardware control tab."""

    _METADATA = plugin_metadata_for_module(__name__)
    actionCenterRequested = pyqtSignal(str, object)

    def metadata(self: typing.Any) -> PluginMetadata:
        return typing.cast(PluginMetadata, self._METADATA)

    def create_widget(self: typing.Any) -> QWidget:
        return typing.cast(QWidget, self)

    def __init__(self: typing.Any) -> None:
        super().__init__()
        self._setup_command_runner()
        self.init_ui()

        # Auto-refresh timer for dynamic values
        self.refresh_timer = QTimer()
        self.refresh_timer.timeout.connect(self.refresh_status)

    def on_activate(self: typing.Any) -> None:
        """Start dynamic hardware probes only while the route is active."""
        if not self.refresh_timer.isActive():
            self.refresh_timer.start(5000)
        QTimer.singleShot(0, self.refresh_status)

    def on_deactivate(self: typing.Any) -> None:
        """Stop periodic hardware probes while hidden."""
        if self.refresh_timer.isActive():
            self.refresh_timer.stop()

    def _setup_command_runner(self: typing.Any) -> typing.Any:
        """Setup CommandRunner for hardware commands (from Tweaks tab)."""
        self.hw_runner = CommandRunner()
        self.hw_runner.output_received.connect(self._on_hw_output)
        self.hw_runner.finished.connect(self._on_hw_command_finished)

    def _on_hw_output(self: typing.Any, text: typing.Any) -> typing.Any:
        """Handle output from hardware commands."""
        if hasattr(self, "hw_output_area"):
            self.hw_output_area.moveCursor(self.hw_output_area.textCursor().MoveOperation.End)
            self.hw_output_area.insertPlainText(text)
            self.hw_output_area.moveCursor(self.hw_output_area.textCursor().MoveOperation.End)

    def _on_hw_command_finished(self: typing.Any, exit_code: typing.Any) -> typing.Any:
        """Handle hardware command completion."""
        if hasattr(self, "hw_output_area"):
            self.hw_output_area.moveCursor(self.hw_output_area.textCursor().MoveOperation.End)
            self.hw_output_area.insertPlainText(self.tr("\nCommand finished with exit code: {}\n").format(exit_code))

    def _run_hw_command(self: typing.Any, cmd: typing.Any, args: typing.Any, description: typing.Any = "") -> typing.Any:
        """Execute a hardware command with output logging."""
        if hasattr(self, "hw_output_area"):
            self.hw_output_area.clear()
            if description:
                self.hw_output_area.setPlainText(description + "\n")
        if classify_command(cmd, args) not in {"read_only", "session"}:
            self.actionCenterRequested.emit("legacy-ui-manual-review", {})
            return
        self.hw_runner.run_command(cmd, args)

    def init_ui(self: typing.Any) -> typing.Any:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        self.scaffold = PageScaffold(
            self.tr("Hardware & Power"),
            self.tr("Hardware devices, batteries, and power state."),
        )
        root.addWidget(self.scaffold)
        layout = self.scaffold.content_layout
        layout.setSpacing(20)

        # Grid for cards
        grid = QGridLayout()
        grid.setSpacing(20)

        # CPU Card
        cpu_card = self.create_cpu_card()
        grid.addWidget(cpu_card, 0, 0)

        # Power Profile Card
        power_card = self.create_power_profile_card()
        grid.addWidget(power_card, 0, 1)

        # GPU Card (if hybrid)
        gpu_card = self.create_gpu_card()
        grid.addWidget(gpu_card, 1, 0)

        # Fan Control Card
        fan_card = self.create_fan_card()
        grid.addWidget(fan_card, 1, 1)

        # Audio Card (from Tweaks tab, row 2, col 0)
        audio_card = self.create_audio_card()
        grid.addWidget(audio_card, 2, 0)

        # Battery Limit Card (from Tweaks tab, row 2, col 1)
        battery_card = self.create_battery_limit_card()
        grid.addWidget(battery_card, 2, 1)

        # Fingerprint Card (from Tweaks tab, row 3, col 0)
        fingerprint_card = self.create_fingerprint_card()
        grid.addWidget(fingerprint_card, 3, 0)

        # Bluetooth Card (v17.0 Atlas)
        bluetooth_card = self.create_bluetooth_card()
        grid.addWidget(bluetooth_card, 3, 1)

        # Boot Configuration Card (v37.0 Pinnacle)
        boot_card = self.create_boot_config_card()
        grid.addWidget(boot_card, 4, 0, 1, 2)

        layout.addLayout(grid)

        # Output area for hardware commands (from Tweaks tab)
        layout.addWidget(QLabel(self.tr("Output Log:")))
        self.hw_output_area = QTextEdit()
        self.hw_output_area.setReadOnly(True)
        self.hw_output_area.setMaximumHeight(150)
        layout.addWidget(self.hw_output_area)

        layout.addStretch()

    def create_card(self: typing.Any, title: str, icon: str) -> QGroupBox:
        """Create a text-labelled card; ``icon`` remains a compatibility input."""
        card = QGroupBox(title)
        card.setObjectName("hwCard")
        return typing.cast(QGroupBox, card)

    # ==================== CPU GOVERNOR ====================

    def create_cpu_card(self: typing.Any) -> QGroupBox:
        card = self.create_card(self.tr("CPU Governor"), "maintenance-health")
        layout = QVBoxLayout(card)

        # Current frequency display
        freq = HardwareManager.get_cpu_frequency()
        self.lbl_cpu_freq = QLabel(self.tr("Current: {} MHz / {} MHz").format(freq["current"], freq["max"]))
        self.lbl_cpu_freq.setObjectName("hwCpuFreq")
        layout.addWidget(self.lbl_cpu_freq)

        # Governor dropdown
        h_layout = QHBoxLayout()
        h_layout.addWidget(QLabel(self.tr("Governor:")))

        self.combo_governor = QComboBox()
        self.combo_governor.setAccessibleName(self.tr("CPU governor"))
        self.combo_governor.setToolTip(HW_CPU_GOVERNOR)
        governors = HardwareManager.get_available_governors()
        self.combo_governor.addItems(governors)

        # Set current governor
        current = HardwareManager.get_current_governor()
        if current in governors:
            self.combo_governor.setCurrentText(current)

        self.combo_governor.currentTextChanged.connect(self.on_governor_changed)
        h_layout.addWidget(self.combo_governor)
        layout.addLayout(h_layout)

        # Description
        desc = QLabel(self.tr("Controls CPU frequency scaling policy"))
        desc.setObjectName("hwCpuDesc")
        layout.addWidget(desc)

        return typing.cast(QGroupBox, card)

    def on_governor_changed(self: typing.Any, governor: str) -> typing.Any:
        """Route a governor change to the shared review boundary."""
        self.actionCenterRequested.emit("set-cpu-governor", {"governor": governor})

    # ==================== POWER PROFILE ====================

    def create_power_profile_card(self: typing.Any) -> QGroupBox:
        card = self.create_card(self.tr("Power Profile"), "hardware-performance")
        layout = QVBoxLayout(card)

        if not HardwareManager.is_power_profiles_available():
            layout.addWidget(QLabel(self.tr("power-profiles-daemon not installed")))
            return typing.cast(QGroupBox, card)

        # Current profile
        current = HardwareManager.get_power_profile()
        self.lbl_power_profile = QLabel(self.tr("Current: {}").format(current.title()))
        self.lbl_power_profile.setObjectName("hwPowerStatus")
        layout.addWidget(self.lbl_power_profile)

        # Profile buttons
        btn_layout = QHBoxLayout()

        profiles = [
            ("Power Saver", "power-saver", "hwPowerSaver"),
            ("Balanced", "balanced", "hwPowerBalanced"),
            ("Performance", "performance", "hwPowerPerformance"),
        ]

        for label, profile, obj_name in profiles:
            btn = QPushButton(label)
            btn.setObjectName(obj_name)
            btn.clicked.connect(lambda checked, p=profile: self.set_power_profile(p))
            btn.setAccessibleName(self.tr("{} profile").format(profile))
            btn_layout.addWidget(btn)

        layout.addLayout(btn_layout)
        return typing.cast(QGroupBox, card)

    def set_power_profile(self: typing.Any, profile: str) -> typing.Any:
        self.actionCenterRequested.emit("set-power-profile", {"profile": profile})

    # ==================== GPU MODE ====================

    def create_gpu_card(self: typing.Any) -> QGroupBox:
        card = self.create_card(self.tr("GPU Mode"), "hardware-performance")
        layout = QVBoxLayout(card)

        if not HardwareManager.is_hybrid_gpu():
            layout.addWidget(QLabel(self.tr("No hybrid GPU detected")))
            return typing.cast(QGroupBox, card)

        tools = HardwareManager.get_available_gpu_tools()
        if not tools:
            layout.addWidget(QLabel(self.tr("No GPU switching tool found")))
            install_btn = QPushButton(self.tr("Install envycontrol"))
            install_btn.setAccessibleName(self.tr("Install envycontrol"))
            install_btn.clicked.connect(self.install_envycontrol)
            layout.addWidget(install_btn)
            return typing.cast(QGroupBox, card)

        # Current mode
        current = HardwareManager.get_gpu_mode()
        self.lbl_gpu_mode = QLabel(self.tr("Current: {}").format(current.title()))
        self.lbl_gpu_mode.setObjectName("hwGpuStatus")
        layout.addWidget(self.lbl_gpu_mode)

        # Mode buttons
        btn_layout = QHBoxLayout()

        modes = [
            ("Integrated", "integrated", "hwGpuIntegrated"),
            ("Hybrid", "hybrid", "hwGpuHybrid"),
            ("NVIDIA", "nvidia", "hwGpuNvidia"),
        ]

        for label, mode, obj_name in modes:
            btn = QPushButton(label)
            btn.setObjectName(obj_name)
            btn.clicked.connect(lambda checked, m=mode: self.set_gpu_mode(m))
            btn.setAccessibleName(self.tr("{} GPU mode").format(mode))
            btn_layout.addWidget(btn)

        layout.addLayout(btn_layout)

        # Warning
        warn = QLabel(self.tr("Requires logout/reboot"))
        warn.setObjectName("hwGpuWarning")
        layout.addWidget(warn)

        return typing.cast(QGroupBox, card)

    def set_gpu_mode(self: typing.Any, mode: str) -> typing.Any:
        self.actionCenterRequested.emit("set-gpu-mode", {"mode": mode})

    def install_envycontrol(self: typing.Any) -> typing.Any:
        """Guide user to install envycontrol."""
        QMessageBox.information(
            self,
            self.tr("Install envycontrol"),
            self.tr(
                "To control GPU modes, install envycontrol:\n\npip install --user envycontrol\n\nOr visit: https://github.com/bayasdev/envycontrol"
            ),
        )

    # ==================== FAN CONTROL ====================

    def create_fan_card(self: typing.Any) -> QGroupBox:
        card = self.create_card(self.tr("Fan Control"), "hardware-performance")
        layout = QVBoxLayout(card)

        if not HardwareManager.is_nbfc_available():
            layout.addWidget(QLabel(self.tr("nbfc-linux not installed")))
            install_btn = QPushButton(self.tr("Learn how to install"))
            install_btn.setAccessibleName(self.tr("Install NBFC"))
            install_btn.clicked.connect(self.show_nbfc_help)
            layout.addWidget(install_btn)
            return typing.cast(QGroupBox, card)

        # Current status
        status = HardwareManager.get_fan_status()
        self.lbl_fan_status = QLabel(self.tr("Speed: {}% | Temp: {}°C").format(int(status["speed"]), int(status["temperature"])))
        self.lbl_fan_status.setObjectName("hwFanStatus")
        layout.addWidget(self.lbl_fan_status)

        # Fan speed slider
        slider_layout = QHBoxLayout()
        slider_layout.addWidget(QLabel(self.tr("Manual:")))

        self.slider_fan = QSlider(Qt.Orientation.Horizontal)
        self.slider_fan.setAccessibleName(self.tr("Fan speed"))
        self.slider_fan.setToolTip(HW_FAN_MODE)
        self.slider_fan.setRange(0, 100)
        self.slider_fan.setValue(50)
        self.slider_fan.setTickPosition(QSlider.TickPosition.TicksBelow)
        self.slider_fan.setTickInterval(25)
        slider_layout.addWidget(self.slider_fan)

        self.lbl_fan_percent = QLabel("50%")
        slider_layout.addWidget(self.lbl_fan_percent)

        self.slider_fan.valueChanged.connect(lambda v: self.lbl_fan_percent.setText(f"{v}%"))
        layout.addLayout(slider_layout)

        # Buttons
        btn_layout = QHBoxLayout()

        btn_apply = QPushButton(self.tr("Apply"))
        btn_apply.setAccessibleName(self.tr("Apply fan speed"))
        btn_apply.clicked.connect(lambda: self.set_fan_speed(self.slider_fan.value()))
        btn_layout.addWidget(btn_apply)

        btn_auto = QPushButton(self.tr("Auto"))
        btn_auto.setAccessibleName(self.tr("Auto fan mode"))
        btn_auto.clicked.connect(lambda: self.set_fan_speed(-1))
        btn_layout.addWidget(btn_auto)

        layout.addLayout(btn_layout)
        return typing.cast(QGroupBox, card)

    def set_fan_speed(self: typing.Any, speed: int) -> typing.Any:
        self.actionCenterRequested.emit("set-fan-speed", {"speed": speed})

    def show_nbfc_help(self: typing.Any) -> typing.Any:
        QMessageBox.information(
            self,
            self.tr("Install nbfc-linux"),
            self.tr(
                "NBFC (NoteBook FanControl) for Linux:\n\n"
                "1. Visit: https://github.com/nbfc-linux/nbfc-linux\n"
                "2. Follow installation instructions for your distro\n"
                "3. Find a config for your laptop model\n"
                "4. Restart this app"
            ),
        )

    # ==================== AUDIO (from Tweaks tab) ====================

    def create_audio_card(self: typing.Any) -> QGroupBox:
        """Create audio services restart card (from TweaksTab)."""
        card = self.create_card(self.tr("Audio Services"), "hardware-performance")
        layout = QVBoxLayout(card)

        desc = QLabel(self.tr("Restart Pipewire audio services if sound is not working"))
        desc.setObjectName("hwAudioDesc")
        desc.setWordWrap(True)
        layout.addWidget(desc)

        btn_restart_audio = QPushButton(self.tr("Restart Audio Services (Pipewire)"))
        btn_restart_audio.setAccessibleName(self.tr("Restart audio"))
        btn_restart_audio.clicked.connect(
            lambda: self.actionCenterRequested.emit("restart-audio-session", {})
        )
        layout.addWidget(btn_restart_audio)

        return typing.cast(QGroupBox, card)

    # ==================== BATTERY LIMIT (from Tweaks tab) ====================

    def create_battery_limit_card(self: typing.Any) -> QGroupBox:
        """Create battery charge limit card (from TweaksTab)."""
        card = self.create_card(self.tr("Battery Charge Limit"), "hardware-performance")
        layout = QVBoxLayout(card)

        desc = QLabel(self.tr("Limit battery charge to extend battery lifespan"))
        desc.setObjectName("hwBatteryDesc")
        desc.setWordWrap(True)
        layout.addWidget(desc)

        btn_layout = QHBoxLayout()

        btn_limit_80 = QPushButton(self.tr("Limit to 80%"))
        btn_limit_80.setAccessibleName(self.tr("Limit charge 80%"))
        btn_limit_80.clicked.connect(lambda: self._set_battery_limit(80))
        btn_layout.addWidget(btn_limit_80)

        btn_limit_100 = QPushButton(self.tr("Limit to 100% (Full)"))
        btn_limit_100.setAccessibleName(self.tr("Limit charge 100%"))
        btn_limit_100.clicked.connect(lambda: self._set_battery_limit(100))
        btn_layout.addWidget(btn_limit_100)

        layout.addLayout(btn_layout)

        return typing.cast(QGroupBox, card)

    def _set_battery_limit(self: typing.Any, limit: typing.Any) -> typing.Any:
        """Route persistent battery service/sysfs changes to manual review."""
        action_id = "set-battery-limit-80" if int(limit) == 80 else "set-battery-limit-100"
        self.actionCenterRequested.emit(action_id, {})
        if hasattr(self, "hw_output_area"):
            self.hw_output_area.setPlainText(self.tr("Review the persistent battery limit guidance in Action Center.\n"))

    # ==================== FINGERPRINT (from Tweaks tab) ====================

    def create_fingerprint_card(self: typing.Any) -> QGroupBox:
        """Create fingerprint enrollment card (from TweaksTab)."""
        card = self.create_card(self.tr("Fingerprint Reader"), "hardware-performance")
        layout = QVBoxLayout(card)

        desc = QLabel(self.tr("Enroll your fingerprint for authentication"))
        desc.setObjectName("hwFingerprintDesc")
        desc.setWordWrap(True)
        layout.addWidget(desc)

        btn_enroll_finger = QPushButton(self.tr("Enroll Fingerprint (GUI)"))
        btn_enroll_finger.setAccessibleName(self.tr("Enroll fingerprint"))
        btn_enroll_finger.clicked.connect(self._enroll_fingerprint)
        layout.addWidget(btn_enroll_finger)

        return typing.cast(QGroupBox, card)

    def _enroll_fingerprint(self: typing.Any) -> typing.Any:
        """Route authentication enrollment to manual security review."""
        self.actionCenterRequested.emit("enroll-fingerprint", {})

    # ==================== BLUETOOTH (v17.0 Atlas) ====================

    def create_bluetooth_card(self: typing.Any) -> QGroupBox:
        """Create Bluetooth management card."""
        card = self.create_card(self.tr("Bluetooth"), "network-connectivity")
        layout = QVBoxLayout(card)

        # Adapter status
        self.lbl_bt_status = QLabel(self.tr("Bluetooth: detecting..."))
        self.lbl_bt_status.setObjectName("hwBtStatus")
        layout.addWidget(self.lbl_bt_status)

        # Device list (compact)
        self.lbl_bt_devices = QLabel(self.tr("Paired devices: —"))
        self.lbl_bt_devices.setObjectName("hwBtDevices")
        self.lbl_bt_devices.setWordWrap(True)
        layout.addWidget(self.lbl_bt_devices)

        # Buttons
        btn_layout = QHBoxLayout()

        btn_power_on = QPushButton(self.tr("Power On"))
        btn_power_on.setAccessibleName(self.tr("Bluetooth on"))
        btn_power_on.clicked.connect(self._bt_power_on)
        btn_layout.addWidget(btn_power_on)

        btn_power_off = QPushButton(self.tr("Power Off"))
        btn_power_off.setAccessibleName(self.tr("Bluetooth off"))
        btn_power_off.clicked.connect(self._bt_power_off)
        btn_layout.addWidget(btn_power_off)

        btn_scan = QPushButton(self.tr("Scan"))
        btn_scan.setAccessibleName(self.tr("Scan Bluetooth"))
        btn_scan.clicked.connect(self._bt_scan)
        btn_layout.addWidget(btn_scan)

        layout.addLayout(btn_layout)

        # Initial status check
        QTimer.singleShot(500, self._bt_refresh_status)

        return typing.cast(QGroupBox, card)

    def _bt_refresh_status(self: typing.Any) -> typing.Any:
        """Refresh Bluetooth adapter and device status."""
        try:
            status = BluetoothManager.get_adapter_status()
            if status.adapter_name:
                power = "On" if status.powered else "Off"
                self.lbl_bt_status.setText(self.tr("Bluetooth: {} | Adapter: {}").format(power, status.adapter_name))
            else:
                self.lbl_bt_status.setText(self.tr("Bluetooth: No adapter found"))
                return

            devices = BluetoothManager.list_devices(paired_only=True)
            if devices:
                names = [f"{d.name} ({'connected' if d.connected else 'paired'})" for d in devices[:5]]
                self.lbl_bt_devices.setText(self.tr("Paired devices: {}").format(", ".join(names)))
            else:
                self.lbl_bt_devices.setText(self.tr("Paired devices: none"))
        except (RuntimeError, OSError, ValueError) as e:
            logger.debug("Failed to refresh Bluetooth status: %s", e)
            self.lbl_bt_status.setText(self.tr("Bluetooth: bluetoothctl not available"))

    def _bt_power_on(self: typing.Any) -> typing.Any:
        """Turn Bluetooth adapter on."""
        result = BluetoothManager.power_on()
        if result.success:
            self.show_toast(self.tr("Bluetooth powered on"))
        else:
            QMessageBox.warning(self, self.tr("Error"), result.message)
        QTimer.singleShot(500, self._bt_refresh_status)

    def _bt_power_off(self: typing.Any) -> typing.Any:
        """Turn Bluetooth adapter off."""
        result = BluetoothManager.power_off()
        if result.success:
            self.show_toast(self.tr("Bluetooth powered off"))
        else:
            QMessageBox.warning(self, self.tr("Error"), result.message)
        QTimer.singleShot(500, self._bt_refresh_status)

    def _bt_scan(self: typing.Any) -> typing.Any:
        """Scan for nearby Bluetooth devices."""
        self._run_hw_command(
            "bluetoothctl",
            ["--timeout", "10", "scan", "on"],
            self.tr("Scanning for Bluetooth devices..."),
        )
        QTimer.singleShot(12000, self._bt_refresh_status)

    # ==================== BOOT CONFIGURATION (v37.0 Pinnacle) ====================

    def create_boot_config_card(self: typing.Any) -> QGroupBox:
        """Create boot configuration management card."""
        card = self.create_card(self.tr("Boot Configuration"), "settings")
        layout = QVBoxLayout(card)

        desc = QLabel(self.tr("Manage GRUB2 bootloader, kernels, and boot parameters."))
        desc.setObjectName("hwBootDesc")
        desc.setWordWrap(True)
        layout.addWidget(desc)

        # Current kernel info
        self.lbl_boot_info = QLabel(self.tr("Current kernel: loading..."))
        self.lbl_boot_info.setObjectName("hwBootInfo")
        layout.addWidget(self.lbl_boot_info)

        btn_layout = QHBoxLayout()

        btn_list_kernels = QPushButton(self.tr("List Kernels"))
        btn_list_kernels.setAccessibleName(self.tr("List boot kernels"))
        btn_list_kernels.clicked.connect(self._list_boot_kernels)
        btn_layout.addWidget(btn_list_kernels)

        btn_grub_config = QPushButton(self.tr("Show GRUB Config"))
        btn_grub_config.setAccessibleName(self.tr("Show GRUB config"))
        btn_grub_config.clicked.connect(self._show_grub_config)
        btn_layout.addWidget(btn_grub_config)

        btn_apply_grub = QPushButton(self.tr("Rebuild GRUB"))
        btn_apply_grub.setAccessibleName(self.tr("Rebuild GRUB config"))
        btn_apply_grub.clicked.connect(self._apply_grub)
        btn_layout.addWidget(btn_apply_grub)

        layout.addLayout(btn_layout)

        # Boot timeout slider
        timeout_layout = QHBoxLayout()
        timeout_layout.addWidget(QLabel(self.tr("GRUB Timeout:")))
        from PyQt6.QtWidgets import QSpinBox

        self.boot_timeout_spin = QSpinBox()
        self.boot_timeout_spin.setAccessibleName(self.tr("GRUB timeout seconds"))
        self.boot_timeout_spin.setRange(0, 30)
        self.boot_timeout_spin.setValue(5)
        self.boot_timeout_spin.setSuffix("s")
        timeout_layout.addWidget(self.boot_timeout_spin)

        btn_set_timeout = QPushButton(self.tr("Set Timeout"))
        btn_set_timeout.setAccessibleName(self.tr("Set GRUB timeout"))
        btn_set_timeout.clicked.connect(self._set_boot_timeout)
        timeout_layout.addWidget(btn_set_timeout)
        timeout_layout.addStretch()
        layout.addLayout(timeout_layout)

        # Load initial info
        QTimer.singleShot(1000, self._load_boot_info)

        return typing.cast(QGroupBox, card)

    def _load_boot_info(self: typing.Any) -> typing.Any:
        """Load current kernel info."""
        try:
            from utils.boot_config import BootConfigManager

            cmdline = BootConfigManager.get_current_cmdline()
            kernel_line = cmdline.split("\n")[0] if cmdline else "unknown"
            self.lbl_boot_info.setText(self.tr("Current: {}").format(kernel_line[:80]))
        except (RuntimeError, OSError, ValueError) as e:
            logger.debug("Failed to load boot info: %s", e)
            self.lbl_boot_info.setText(self.tr("Current kernel: detection failed"))

    def _list_boot_kernels(self: typing.Any) -> typing.Any:
        try:
            from utils.boot_config import BootConfigManager

            kernels = BootConfigManager.list_kernels()
            lines = [
                f"{k.title} ({getattr(k, 'version', '') or getattr(k, 'kernel', '')})"
                f"{' (default)' if bool(getattr(k, 'is_default', getattr(k, 'default', False))) else ''}"
                for k in kernels
            ]
            if hasattr(self, "hw_output_area"):
                self.hw_output_area.setPlainText("\n".join(lines) or "No kernels found.")
        except (RuntimeError, OSError, ValueError) as e:
            if hasattr(self, "hw_output_area"):
                self.hw_output_area.setPlainText(f"[ERROR] {e}")

    def _show_grub_config(self: typing.Any) -> typing.Any:
        try:
            from utils.boot_config import BootConfigManager

            config = BootConfigManager.get_grub_config()
            lines = [
                f"Default: {config.default_entry}",
                f"Timeout: {config.timeout}s",
                f"Theme: {config.theme or 'none'}",
                f"Cmdline: {config.cmdline_linux}",
            ]
            if hasattr(self, "hw_output_area"):
                self.hw_output_area.setPlainText("\n".join(lines))
        except (RuntimeError, OSError, ValueError) as e:
            if hasattr(self, "hw_output_area"):
                self.hw_output_area.setPlainText(f"[ERROR] {e}")

    def _set_boot_timeout(self: typing.Any) -> typing.Any:
        seconds = self.boot_timeout_spin.value()
        self.actionCenterRequested.emit("set-grub-timeout", {"seconds": seconds})

    def _apply_grub(self: typing.Any) -> typing.Any:
        self.actionCenterRequested.emit("apply-grub-config", {})

    # ==================== UTILITIES ====================

    def refresh_status(self: typing.Any) -> typing.Any:
        """Refresh dynamic values."""
        try:
            # CPU frequency
            freq = HardwareManager.get_cpu_frequency()
            self.lbl_cpu_freq.setText(self.tr("Current: {} MHz / {} MHz").format(freq["current"], freq["max"]))

            # Fan status
            if HardwareManager.is_nbfc_available():
                status = HardwareManager.get_fan_status()
                self.lbl_fan_status.setText(self.tr("Speed: {}% | Temp: {}°C").format(int(status["speed"]), int(status["temperature"])))
        except (RuntimeError, OSError, ValueError) as e:
            logger.debug("Failed to refresh hardware status: %s", e)

    def show_toast(self: typing.Any, message: str) -> typing.Any:
        """Show a quick toast notification (status bar style)."""
        # For now, just update window title briefly
        parent = self.window()
        if parent:
            original = parent.windowTitle()
            parent.setWindowTitle(message)
            QTimer.singleShot(2000, lambda: parent.setWindowTitle(original))
