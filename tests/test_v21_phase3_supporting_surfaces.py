"""Resolve Phase 3 Specialist Tools and Settings presentation contracts."""

from __future__ import annotations

import os
import sys
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(
    0,
    os.path.join(os.path.dirname(__file__), "..", "loofi-fedora-tweaks"),
)

from PyQt6.QtWidgets import QApplication, QCheckBox

from ui.components.settings import SettingRow



class TestSettingRows(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    @staticmethod
    def _manager(*, save_result: bool = True) -> MagicMock:
        manager = MagicMock()
        values = {
            "theme": "dark",
            "follow_system_theme": True,
            "start_minimized": False,
            "show_notifications": True,
            "confirm_dangerous_actions": True,
            "restore_last_tab": False,
            "log_level": "INFO",
            "check_updates_on_start": True,
        }
        manager.get.side_effect = lambda key, default=None: values.get(key, default)
        manager.save.return_value = save_result
        return manager

    def test_row_feedback_never_relies_on_color_alone(self) -> None:
        row = SettingRow("Notifications", "Desktop feedback", QCheckBox())

        row.set_feedback("The change is stored.", kind="saved")
        self.assertTrue(row.feedback_label.text().startswith("Saved —"))
        self.assertTrue(row.feedback_label.accessibleDescription())

        row.set_feedback("The file is read-only.", kind="error")
        self.assertTrue(row.feedback_label.text().startswith("Error —"))
        row.deleteLater()

    @patch("ui.settings_tab.SettingsManager.instance")
    def test_theme_dependency_is_visible_and_named(self, mock_instance) -> None:
        from ui.settings_tab import SettingsTab

        mock_instance.return_value = self._manager()
        tab = SettingsTab()
        row = tab._setting_rows["theme"]

        self.assertFalse(tab.theme_combo.isEnabled())
        self.assertTrue(row.feedback_label.text().startswith("Unavailable —"))
        self.assertTrue(row.accessibleName())
        tab.deleteLater()

    @patch("ui.settings_tab.SettingsManager.instance")
    def test_success_and_failure_are_reported_beside_the_setting(
        self,
        mock_instance,
    ) -> None:
        from ui.settings_tab import SettingsTab

        manager = self._manager()
        mock_instance.return_value = manager
        tab = SettingsTab()

        tab._toggle_setting("show_notifications", False)
        self.assertTrue(
            tab._setting_rows["show_notifications"].feedback_label.text().startswith("Saved —")
        )

        manager.save.return_value = False
        tab._toggle_setting("start_minimized", True)
        self.assertTrue(
            tab._setting_rows["start_minimized"].feedback_label.text().startswith("Error —")
        )
        tab.deleteLater()

    @patch("ui.settings_tab.SettingsManager.instance")
    def test_settings_context_keeps_specialist_dependency_feedback(
        self,
        mock_instance,
    ) -> None:
        from ui.settings_tab import SettingsTab

        mock_instance.return_value = self._manager()
        tab = SettingsTab()
        tab.set_context(
            {
                "main_window": SimpleNamespace(
                    _navigation_context=SimpleNamespace(
                        installed_components=frozenset({"core"})
                    )
                )
            }
        )

        self.assertIn("does not include specialist tools", tab._component_status.text())
        tab.deleteLater()

    @patch("ui.settings_tab.SettingsManager.instance")
    def test_reset_failure_is_reported_for_every_affected_row(
        self,
        mock_instance,
    ) -> None:
        from ui.settings_tab import SettingsTab

        manager = self._manager()
        manager.reset_group.return_value = False
        mock_instance.return_value = manager
        tab = SettingsTab()

        tab._reset_behavior()

        for key in (
            "start_minimized",
            "show_notifications",
            "confirm_dangerous_actions",
            "restore_last_tab",
        ):
            self.assertTrue(
                tab._setting_rows[key].feedback_label.text().startswith("Error —")
            )
        tab.deleteLater()


if __name__ == "__main__":
    unittest.main()
