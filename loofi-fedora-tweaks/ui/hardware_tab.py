"""Read-only hardware status and reviewed device handoffs.

The maintenance core deliberately does not tune firmware, graphics, fans,
batteries, boot loaders, or desktop dotfiles. Those operations are hardware-
specific and difficult to verify safely across Fedora variants. This page
reports lightweight status and sends the few supported device requests through
Action Center for review.
"""

from __future__ import annotations

import platform
import typing

from core.plugins.interface import PluginInterface
from core.plugins.metadata import PluginMetadata
from core.product_catalog import plugin_metadata_for_module
from PyQt6.QtCore import QTimer, pyqtSignal
from PyQt6.QtWidgets import QGroupBox, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget
from services.hardware import BluetoothManager
from utils.log import get_logger

from ui.components.layout import PageScaffold

logger = get_logger(__name__)


class HardwareTab(QWidget, PluginInterface):
    """Display hardware facts without exposing specialist tuning controls."""

    _METADATA = plugin_metadata_for_module(__name__)
    actionCenterRequested = pyqtSignal(str, object)

    def metadata(self: typing.Any) -> PluginMetadata:
        return typing.cast(PluginMetadata, self._METADATA)

    def create_widget(self) -> QWidget:
        return self

    def __init__(self: typing.Any) -> None:
        super().__init__()
        self._build_ui()
        self.refresh_timer = QTimer()
        self.refresh_timer.timeout.connect(self.refresh_status)

    def on_activate(self: typing.Any) -> None:
        """Start the bounded Bluetooth status probe while the page is shown."""
        if not self.refresh_timer.isActive():
            self.refresh_timer.start(5000)
        QTimer.singleShot(0, self.refresh_status)

    def on_deactivate(self: typing.Any) -> None:
        """Stop periodic probes while the page is hidden."""
        if self.refresh_timer.isActive():
            self.refresh_timer.stop()

    def _build_ui(self: typing.Any) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        self.scaffold = PageScaffold(
            self.tr("Hardware status"),
            self.tr("Inspect devices and send supported requests to Action Center for review."),
        )
        root.addWidget(self.scaffold)
        layout = self.scaffold.content_layout

        summary = self.create_card(self.tr("Detected platform"))
        summary_layout = QVBoxLayout(summary)
        self.lbl_platform = QLabel(self._platform_summary())
        self.lbl_platform.setObjectName("hwPlatformSummary")
        self.lbl_platform.setWordWrap(True)
        summary_layout.addWidget(self.lbl_platform)
        layout.addWidget(summary)

        device_row = QHBoxLayout()
        device_row.addWidget(self.create_audio_card())
        device_row.addWidget(self.create_fingerprint_card())
        device_row.addWidget(self.create_bluetooth_card())
        layout.addLayout(device_row)

        self.lbl_status = QLabel(self.tr("Status checks run when this page is active."))
        self.lbl_status.setObjectName("hwStatus")
        self.lbl_status.setWordWrap(True)
        layout.addWidget(self.lbl_status)
        layout.addStretch()

    @staticmethod
    def _platform_summary() -> str:
        """Return safe local facts without running a command or guessing support."""
        machine = platform.machine() or "unknown"
        system = platform.system() or "unknown"
        return f"Operating system: {system}\nArchitecture: {machine}"

    def create_card(self: typing.Any, title: str) -> QGroupBox:
        card = QGroupBox(title)
        card.setObjectName("hwCard")
        return typing.cast(QGroupBox, card)

    def create_audio_card(self: typing.Any) -> QGroupBox:
        """Offer a reviewed PipeWire restart when audio recovery is needed."""
        card = self.create_card(self.tr("Audio"))
        layout = QVBoxLayout(card)
        desc = QLabel(self.tr("Restart the user audio session when sound is not working."))
        desc.setWordWrap(True)
        layout.addWidget(desc)
        button = QPushButton(self.tr("Review audio restart"))
        button.setAccessibleName(self.tr("Review audio restart"))
        button.clicked.connect(lambda: self.actionCenterRequested.emit("restart-audio-session", {}))
        layout.addWidget(button)
        return typing.cast(QGroupBox, card)

    def create_fingerprint_card(self: typing.Any) -> QGroupBox:
        """Offer a reviewed native fingerprint enrollment handoff."""
        card = self.create_card(self.tr("Fingerprint"))
        layout = QVBoxLayout(card)
        desc = QLabel(self.tr("Use the desktop's native enrollment flow for authentication."))
        desc.setWordWrap(True)
        layout.addWidget(desc)
        button = QPushButton(self.tr("Review enrollment"))
        button.setAccessibleName(self.tr("Review fingerprint enrollment"))
        button.clicked.connect(lambda: self.actionCenterRequested.emit("enroll-fingerprint", {}))
        layout.addWidget(button)
        return typing.cast(QGroupBox, card)

    def create_bluetooth_card(self: typing.Any) -> QGroupBox:
        """Show Bluetooth status and route changes through Action Center."""
        card = self.create_card(self.tr("Bluetooth"))
        layout = QVBoxLayout(card)
        self.lbl_bt_status = QLabel(self.tr("Bluetooth: detecting..."))
        self.lbl_bt_status.setObjectName("hwBtStatus")
        layout.addWidget(self.lbl_bt_status)
        self.lbl_bt_devices = QLabel(self.tr("Paired devices: —"))
        self.lbl_bt_devices.setObjectName("hwBtDevices")
        self.lbl_bt_devices.setWordWrap(True)
        layout.addWidget(self.lbl_bt_devices)

        buttons = QHBoxLayout()
        for label, action, accessible in (
            (self.tr("Review power on"), "power-on", self.tr("Review Bluetooth power on")),
            (self.tr("Review power off"), "power-off", self.tr("Review Bluetooth power off")),
        ):
            button = QPushButton(label)
            button.setAccessibleName(accessible)
            button.clicked.connect(
                lambda _checked=False, requested=action: self.actionCenterRequested.emit(
                    "control-bluetooth-device", {"action": requested, "target": "adapter"}
                )
            )
            buttons.addWidget(button)
        scan = QPushButton(self.tr("Review scan"))
        scan.setAccessibleName(self.tr("Review Bluetooth scan"))
        scan.clicked.connect(lambda: self.actionCenterRequested.emit("legacy-ui-manual-review", {}))
        buttons.addWidget(scan)
        layout.addLayout(buttons)
        QTimer.singleShot(0, self.refresh_status)
        return typing.cast(QGroupBox, card)

    def refresh_status(self: typing.Any) -> None:
        """Read Bluetooth status only; failures remain visible and non-fatal."""
        try:
            status = BluetoothManager.get_adapter_status()
            adapter_name = str(getattr(status, "adapter_name", "") or "")
            if not adapter_name:
                self.lbl_bt_status.setText(self.tr("Bluetooth: no adapter found"))
                self.lbl_bt_devices.setText(self.tr("Paired devices: —"))
                return
            powered = bool(getattr(status, "powered", False))
            state = self.tr("on") if powered else self.tr("off")
            self.lbl_bt_status.setText(self.tr("Bluetooth: {} | adapter: {}").format(state, adapter_name))
            devices = BluetoothManager.list_devices(paired_only=True)
            if devices:
                names = [
                    f"{getattr(device, 'name', '') or 'Unnamed'} ({'connected' if getattr(device, 'connected', False) else 'paired'})"
                    for device in devices[:5]
                ]
                self.lbl_bt_devices.setText(self.tr("Paired devices: {}").format(", ".join(names)))
            else:
                self.lbl_bt_devices.setText(self.tr("Paired devices: none"))
        except (AttributeError, OSError, RuntimeError, TypeError, ValueError) as exc:
            logger.debug("Failed to refresh Bluetooth status: %s", exc)
            self.lbl_bt_status.setText(self.tr("Bluetooth: status unavailable"))
            self.lbl_bt_devices.setText(self.tr("Paired devices: unavailable"))

    def show_toast(self: typing.Any, message: str) -> None:
        """Keep the legacy notification hook without introducing a new surface."""
        self.lbl_status.setText(str(message))
