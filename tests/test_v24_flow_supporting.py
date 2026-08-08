"""V24 Flow contracts for System, Network, Settings, and module decomposition."""

from __future__ import annotations

import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from PyQt6.QtWidgets import QApplication, QCheckBox

from ui.components.settings import SettingRow
from ui.network_tab import NetworkTab
from ui.system_info_tab import SystemInfoTab


class TestV24SupportingSurfaces(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    @patch("ui.network_tab.QMessageBox")
    @patch("ui.network_tab.QTimer.singleShot")
    @patch("ui.network_tab.NetworkUtils")
    def test_network_review_feedback_never_claims_a_change_already_ran(
        self,
        network_utils: MagicMock,
        _single_shot: MagicMock,
        message_box: MagicMock,
    ) -> None:
        network_utils.get_active_connection.return_value = "WiFi Home"
        tab = NetworkTab()
        self.addCleanup(tab.deleteLater)
        requests: list[tuple[str, object]] = []
        tab.actionCenterRequested.connect(lambda action_id, parameters: requests.append((action_id, parameters)))

        tab._toggle_hostname_privacy(True)

        self.assertEqual(requests, [("configure-hostname-privacy", {"connection": "WiFi Home", "hidden": True})])
        self.assertIn("No setting has changed yet", tab.network_feedback.message_label.text())
        self.assertEqual(message_box.information.call_args.args[1], "Review required")
        network_utils.set_hostname_privacy.assert_not_called()

    @patch("ui.system_info_tab.system_info_utils")
    def test_system_information_reports_complete_and_partial_reads(self, info_utils: MagicMock) -> None:
        for getter_name in (
            "get_hostname",
            "get_kernel_version",
            "get_fedora_release",
            "get_cpu_model",
            "get_ram_usage",
            "get_disk_usage",
            "get_uptime",
            "get_battery_status",
        ):
            getattr(info_utils, getter_name).return_value = "available"
        tab = SystemInfoTab()
        self.addCleanup(tab.deleteLater)

        tab.refresh_info()
        self.assertEqual(tab.info_feedback.property("resultKind"), "success")
        info_utils.get_cpu_model.side_effect = OSError("unavailable")
        tab.refresh_info()
        self.assertEqual(tab.info_feedback.property("resultKind"), "warning")

    def test_setting_feedback_names_changed_saved_error_and_restart(self) -> None:
        row = SettingRow("Startup", "Application startup behavior", QCheckBox())
        self.addCleanup(row.deleteLater)
        expected = {
            "changed": "Changed",
            "saved": "Saved",
            "error": "Error",
            "restart": "Restart required",
        }
        for kind, prefix in expected.items():
            with self.subTest(kind=kind):
                row.set_feedback("Visible feedback", kind=kind)
                self.assertTrue(row.feedback_label.text().startswith(prefix))
                self.assertTrue(row.feedback_label.accessibleDescription())

    @patch("ui.settings_tab.SettingsManager.instance")
    def test_closed_setting_validation_fails_before_persistence(self, manager_instance: MagicMock) -> None:
        from ui.settings_tab import SettingsTab

        manager = MagicMock()
        values = {
            "theme": "dark",
            "follow_system_theme": True,
            "start_minimized": False,
            "show_notifications": True,
            "confirm_dangerous_actions": True,
            "restore_last_tab": True,
            "log_level": "INFO",
            "check_updates_on_start": True,
        }
        manager.get.side_effect = lambda key, default=None: values.get(key, default)
        manager_instance.return_value = manager
        tab = SettingsTab()
        self.addCleanup(tab.deleteLater)

        self.assertFalse(tab._save_setting("log_level", "VERBOSE"))

        manager.set.assert_not_called()
        self.assertTrue(tab._setting_rows["log_level"].feedback_label.text().startswith("Error —"))

    def test_touched_large_views_are_split_below_900_lines(self) -> None:
        root = Path(__file__).resolve().parents[1] / "loofi-fedora-tweaks" / "ui"
        self.assertLess(len((root / "troubleshoot_widget.py").read_text(encoding="utf-8").splitlines()), 900)
        self.assertLess(len((root / "maintenance_action_center.py").read_text(encoding="utf-8").splitlines()), 900)
        self.assertTrue((root / "troubleshoot_presentation.py").is_file())
        self.assertTrue((root / "action_center_views.py").is_file())


if __name__ == "__main__":
    unittest.main()
