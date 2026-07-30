"""Tests for the unified Specialist Tools settings presentation."""

import os
import sys
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from PyQt6.QtWidgets import QApplication, QLabel

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "loofi-fedora-tweaks"))

from core.navigation.models import NavigationMode


def _bare_tab():
    from ui.settings_tab import SettingsTab

    tab = SettingsTab.__new__(SettingsTab)
    tab._main_window = None
    tab._mgr = MagicMock()
    tab._ui_initialized = False
    tab.tr = lambda value: value
    tab._mode_desc = MagicMock()
    tab._component_status = MagicMock()
    return tab


class TestSettingsNavigationMode(unittest.TestCase):
    def test_component_status_never_claims_automatic_install(self):
        tab = _bare_tab()
        tab._main_window = SimpleNamespace(
            _navigation_context=SimpleNamespace(installed_components=frozenset({"core", "specialist"}))
        )
        tab._update_component_status()
        text = tab._component_status.setText.call_args.args[0]
        self.assertIn("never installs packages", text)

    def test_missing_specialist_component_has_guidance(self):
        tab = _bare_tab()
        tab._main_window = SimpleNamespace(
            _navigation_context=SimpleNamespace(installed_components=frozenset({"core"}))
        )
        tab._update_component_status()
        text = tab._component_status.setText.call_args.args[0]
        self.assertIn("does not include specialist tools", text)


class TestPhase7SettingsPresentation(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    @staticmethod
    def _manager() -> MagicMock:
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
        return manager

    @patch("ui.settings_tab.SettingsManager.instance")
    def test_settings_has_unified_specialist_tools_and_phase7_pages(self, mock_instance):
        from ui.settings_tab import SettingsTab

        mock_instance.return_value = self._manager()
        tab = SettingsTab()

        labels = [
            tab.settings_tabs.widget(index).widget().accessibleName()
            for index in range(tab.settings_tabs.count())
        ]
        self.assertEqual(labels, ["Appearance", "Behavior", "Specialist Tools", "Repair Loofi", "About"])
        self.assertFalse(hasattr(tab, "mode_combo"))
        self.assertIn("always available", tab._mode_desc.text())
        self.assertTrue(tab.follow_system_cb.isChecked())
        self.assertFalse(tab.theme_combo.isEnabled())

    @patch("utils.navigation_mode.NavigationModeManager.get_mode", return_value=NavigationMode.STANDARD)
    @patch("ui.settings_tab.SettingsManager.instance")
    def test_stable_settings_routes_activate_new_pages(self, mock_instance, mock_get_mode):
        from ui.settings_tab import SettingsTab

        mock_instance.return_value = self._manager()
        tab = SettingsTab()

        self.assertTrue(tab.activate_route(SimpleNamespace(id="settings:repair")))
        self.assertEqual(tab.settings_tabs.currentIndex(), 3)
        self.assertTrue(tab.activate_route(SimpleNamespace(id="settings:about")))
        self.assertEqual(tab.settings_tabs.currentIndex(), 4)

    @patch("utils.navigation_mode.NavigationModeManager.get_mode", return_value=NavigationMode.STANDARD)
    @patch("ui.settings_tab.SettingsManager.instance")
    def test_about_contains_static_identity_runtime_and_support(self, mock_instance, mock_get_mode):
        from ui.settings_tab import SettingsTab
        from version import __version__, __version_codename__

        mock_instance.return_value = self._manager()
        tab = SettingsTab()
        text = " ".join(label.text() for label in tab.findChildren(QLabel))

        self.assertIn(__version__, text)
        self.assertIn(__version_codename__, text)
        self.assertIn("Fedora 44", text)
        self.assertIn("Fedora 45", text)

    @patch("core.state.StateDoctor")
    @patch("utils.navigation_mode.NavigationModeManager.get_mode", return_value=NavigationMode.STANDARD)
    @patch("ui.settings_tab.SettingsManager.instance")
    def test_repair_loofi_reuses_state_doctor_service(
        self,
        mock_instance,
        mock_get_mode,
        mock_doctor,
    ):
        from ui.settings_tab import SettingsTab

        mock_instance.return_value = self._manager()
        mock_doctor.return_value.run.return_value = {
            "status": "healthy",
            "domains": ["settings"],
            "findings": [],
        }
        tab = SettingsTab()

        tab._run_state_doctor()

        mock_doctor.return_value.run.assert_called_once_with()
        self.assertIn("No state integrity problems found", tab.state_status.toPlainText())


if __name__ == "__main__":
    unittest.main()
