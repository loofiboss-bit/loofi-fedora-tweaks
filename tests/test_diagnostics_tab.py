"""Contract tests for the read-only diagnostics journey."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

from PyQt6.QtWidgets import QApplication, QPushButton

from services.security.secureboot import SecureBootStatus
from utils.boot_analyzer import BootStats
from utils.zram import ZramConfig
from ui.diagnostics_tab import _BootSubTab, _WatchtowerSubTab


_APP = QApplication.instance() or QApplication([])


def _boot_tab() -> _BootSubTab:
    with patch("ui.diagnostics_tab.KernelManager.get_current_params", return_value=["root=/dev/test"]), patch(
        "ui.diagnostics_tab.ZramManager.get_current_config",
        return_value=ZramConfig(True, 1024, 100, "zstd", 4096),
    ), patch("ui.diagnostics_tab.ZramManager.get_current_usage", return_value=(128, 1024)), patch(
        "ui.diagnostics_tab.SecureBootManager.get_status",
        return_value=SecureBootStatus(False, False, False, "unavailable"),
    ), patch("ui.diagnostics_tab.SecureBootManager.has_keys", return_value=False):
        return _BootSubTab()


def test_boot_diagnostics_has_no_kernel_or_grub_mutation_controls() -> None:
    tab = _boot_tab()
    assert "root=/dev/test" in tab.current_params_label.text()
    assert not hasattr(tab, "param_checkboxes")
    assert not hasattr(tab, "custom_param_input")
    assert not hasattr(tab, "zram_slider")
    assert not hasattr(tab, "zram_algo_combo")
    assert not hasattr(tab, "backup_grub")
    assert not hasattr(tab, "restore_grub")
    tab.deleteLater()


def test_secure_boot_buttons_route_to_action_center() -> None:
    tab = _boot_tab()
    requests: list[tuple[str, object]] = []
    tab.actionCenterRequested.connect(lambda action, params: requests.append((action, params)))
    for button in tab.findChildren(QPushButton):
        if button.text() == "Generate MOK Key":
            button.click()
    assert requests == [("generate-mok-key", {})]
    tab.deleteLater()


def test_watchtower_service_review_does_not_execute_directly() -> None:
    service = SimpleNamespace(name="example.service", state="failed", scope="system", description="")
    with patch("ui.diagnostics_tab.ServiceManager.list_units", return_value=[]), patch(
        "ui.diagnostics_tab.BootAnalyzer.get_boot_stats", return_value=BootStats()
    ), patch("ui.diagnostics_tab.BootAnalyzer.get_slow_services", return_value=[]), patch(
        "ui.diagnostics_tab.BootAnalyzer.get_optimization_suggestions", return_value=[]
    ), patch("ui.diagnostics_tab.JournalManager.get_quick_diagnostic", return_value={"error_count": 0, "failed_services": []}), patch(
        "ui.diagnostics_tab.JournalManager.get_boot_errors", return_value=""
    ):
        tab = _WatchtowerSubTab()
    requests: list[tuple[str, object]] = []
    tab.actionCenterRequested.connect(lambda action, params: requests.append((action, params)))
    tab._service_action("review", service)
    assert requests == [("legacy-ui-manual-review", {"service": "example.service", "action": "review", "scope": "system"})]
    tab.deleteLater()
