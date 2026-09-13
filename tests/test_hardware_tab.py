"""Contract tests for the V27 hardware-status page."""

from __future__ import annotations

from unittest.mock import patch

from PyQt6.QtWidgets import QApplication, QPushButton

from services.hardware import BluetoothDevice, BluetoothStatus
from ui.hardware_tab import HardwareTab


_APP = QApplication.instance() or QApplication([])


def _tab() -> HardwareTab:
    with patch("ui.hardware_tab.BluetoothManager.get_adapter_status", return_value=BluetoothStatus()):
        with patch("ui.hardware_tab.BluetoothManager.list_devices", return_value=[]):
            return HardwareTab()


def test_page_exposes_status_and_supported_review_cards() -> None:
    tab = _tab()
    assert tab.metadata().id == "hardware"
    assert tab.metadata().name == "Hardware"
    assert tab.findChild(type(tab.lbl_platform), "hwPlatformSummary") is not None
    assert not hasattr(tab, "combo_governor")
    assert not hasattr(tab, "slider_fan")
    assert not hasattr(tab, "boot_timeout_spin")
    tab.deleteLater()


def test_bluetooth_status_is_read_only_probe() -> None:
    tab = _tab()
    device = BluetoothDevice("AA:BB:CC:DD:EE:FF", "Keyboard", paired=True)
    with patch(
        "ui.hardware_tab.BluetoothManager.get_adapter_status",
        return_value=BluetoothStatus(powered=True, adapter_name="hci0"),
    ), patch("ui.hardware_tab.BluetoothManager.list_devices", return_value=[device]):
        tab.refresh_status()
    assert "hci0" in tab.lbl_bt_status.text()
    assert "Keyboard" in tab.lbl_bt_devices.text()
    tab.deleteLater()


def test_bluetooth_status_failures_are_visible() -> None:
    tab = _tab()
    with patch(
        "ui.hardware_tab.BluetoothManager.get_adapter_status",
        side_effect=OSError("missing bluetoothctl"),
    ):
        tab.refresh_status()
    assert "unavailable" in tab.lbl_bt_status.text()
    tab.deleteLater()


def test_mutating_requests_are_emitted_for_action_center_review() -> None:
    tab = _tab()
    requests: list[tuple[str, object]] = []
    tab.actionCenterRequested.connect(lambda action, params: requests.append((action, params)))
    for button in tab.findChildren(QPushButton):
        if button.text() in {"Review audio restart", "Review enrollment"}:
            button.click()
    assert [action for action, _params in requests] == [
        "restart-audio-session",
        "enroll-fingerprint",
    ]
    tab.deleteLater()
