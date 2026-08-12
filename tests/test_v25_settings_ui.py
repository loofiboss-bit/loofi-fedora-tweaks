"""v25 Safety & Execution settings UI contract."""

from __future__ import annotations

import unittest
from unittest.mock import patch

from PyQt6.QtWidgets import QApplication, QCheckBox, QComboBox, QGroupBox

from core.settings.execution import ExecutionSettings
from ui.settings_tab import SettingsTab


class TestV25SettingsUi(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    @patch("ui.settings_tab.ExecutionSettingsStore")
    def test_safety_controls_live_inside_existing_behavior_route(self, store_cls):
        store_cls.return_value.load.return_value = ExecutionSettings()
        tab = SettingsTab()
        self.assertEqual(len(tab.findChildren(QGroupBox, "safetyExecutionGroup")), 1)
        self.assertEqual(tab.execution_mode_combo.currentData(), "direct")
        self.assertTrue(tab.findChild(QCheckBox, "confirmMediumRisk").isChecked())
        self.assertIsInstance(tab.findChild(QComboBox, "executionModeCombo"), QComboBox)
        tab.close()


if __name__ == "__main__":
    unittest.main()
