"""Tests for the canonical v15 navigation mode manager."""

import os
import sys
import unittest
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "loofi-fedora-tweaks"))

from core.navigation.models import NavigationMode
from utils.navigation_mode import NavigationModeManager


class TestNavigationModeManager(unittest.TestCase):
    @patch("utils.navigation_mode.SettingsManager")
    def test_get_mode_ignores_retired_visibility_setting(self, mock_settings_cls):
        mgr = MagicMock()
        mgr.get.return_value = "advanced"
        mock_settings_cls.instance.return_value = mgr

        self.assertIs(NavigationModeManager.get_mode(), NavigationMode.ADVANCED)
        mgr.get.assert_not_called()

    @patch("utils.navigation_mode.SettingsManager")
    def test_set_mode_writes_only_canonical_mode(self, mock_settings_cls):
        mgr = MagicMock()
        mock_settings_cls.instance.return_value = mgr

        NavigationModeManager.set_mode(NavigationMode.STANDARD)

        mgr.set.assert_called_once_with("navigation_mode", "advanced")
        mgr.save.assert_called_once_with()

    @patch("utils.navigation_mode.SettingsManager")
    def test_set_advanced_never_changes_safety_settings(self, mock_settings_cls):
        mgr = MagicMock()
        mock_settings_cls.instance.return_value = mgr

        NavigationModeManager.set_mode(NavigationMode.ADVANCED)

        touched_keys = {call.args[0] for call in mgr.set.call_args_list}
        self.assertEqual(touched_keys, {"navigation_mode"})


if __name__ == "__main__":
    unittest.main()
