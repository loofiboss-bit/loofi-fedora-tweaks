"""v20 unified navigation contracts."""

from __future__ import annotations

import unittest
from unittest.mock import patch

from core.navigation.models import NavigationMode
from utils.navigation_mode import NavigationModeManager


class TestUnifiedNavigation(unittest.TestCase):
    @patch("utils.navigation_mode.SettingsManager")
    def test_persisted_legacy_mode_does_not_hide_specialist_tools(self, settings):
        settings.instance.return_value.get.return_value = "standard"

        self.assertIs(NavigationModeManager.get_mode(), NavigationMode.ADVANCED)
        settings.instance.return_value.get.assert_not_called()

    @patch("utils.navigation_mode.SettingsManager")
    def test_compatibility_setter_normalizes_to_unified_mode(self, settings):
        NavigationModeManager.set_mode(NavigationMode.STANDARD)

        settings.instance.return_value.set.assert_called_once_with(
            "navigation_mode", "advanced"
        )

    def test_settings_source_has_no_global_mode_selector(self):
        from pathlib import Path

        source = (
            Path(__file__).parents[1]
            / "loofi-fedora-tweaks"
            / "ui"
            / "settings_tab.py"
        ).read_text(encoding="utf-8")
        self.assertNotIn("self.mode_combo", source)
        self.assertIn("Specialist tools are always available", source)
