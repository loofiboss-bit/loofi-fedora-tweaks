"""Wayfinder symptom selection and history disclosure regression contracts."""

import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from PyQt6.QtCore import Qt
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QApplication

from ui.activity_recovery_tab import ActivityRecoveryTab
from ui.fix_workflow import FixWorkflowPage
from ui.troubleshoot_widget import TroubleshootWidget


class TestWayfinderHealthHistory(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_keyboard_card_selection_previews_without_collecting(self):
        factory = MagicMock()
        widget = TroubleshootWidget(worker_factory=factory, history=SimpleNamespace(latest=lambda: (None, "")))
        self.addCleanup(widget.deleteLater)
        card = widget.symptom_cards["app_wont_start"]
        QTest.keyClick(card, Qt.Key.Key_Space)
        self.assertEqual(widget.selected_profile_id(), "application_failed")
        self.assertTrue(card.property("selected"))
        self.assertFalse(widget.symptom_cards["no_internet"].property("selected"))
        self.assertFalse(widget.application_input.isHidden())
        factory.assert_not_called()

    def test_route_selection_updates_and_focuses_visible_card(self):
        widget = FixWorkflowPage(history=SimpleNamespace(latest=lambda: (None, "")))
        self.addCleanup(widget.deleteLater)
        widget.show()
        widget.activateWindow()
        self.app.processEvents()
        self.assertTrue(widget.focus_task("fix:storage-pressure"))
        self.assertTrue(widget.symptom_cards["storage_full"].property("selected"))
        self.assertEqual(QApplication.focusWidget(), widget.symptom_cards["storage_full"])
        self.assertTrue(widget.profile_selector.isHidden())

    def test_narrow_health_layout_stacks_cards(self):
        widget = TroubleshootWidget(history=SimpleNamespace(latest=lambda: (None, "")))
        self.addCleanup(widget.deleteLater)
        widget.resize(500, 650)
        widget.show()
        self.app.processEvents()
        for index in range(len(widget.symptom_cards)):
            item_index = widget.symptom_grid.indexOf(list(widget.symptom_cards.values())[index])
            row, column, _rows, _columns = widget.symptom_grid.getItemPosition(item_index)
            self.assertEqual((row, column), (index, 0))

    @patch("ui.settings_tab.SettingsManager.instance")
    def test_settings_keyboard_sections_remain_accessible_without_shell(self, instance):
        from ui.settings_tab import SettingsTab

        instance.return_value.get.side_effect = lambda key, default=None: {"theme": "dark", "log_level": "INFO"}.get(key, False)
        widget = SettingsTab()
        self.addCleanup(widget.deleteLater)
        self.assertEqual(widget.section_selector.count(), 5)
        QTest.keyClick(widget.section_selector, Qt.Key.Key_Right)
        self.assertEqual(widget.settings_tabs.currentIndex(), 1)
        self.assertEqual(widget.section_selector.currentIndex(), 1)

    @patch("ui.settings_tab.SettingsManager.instance")
    def test_shell_routes_emit_once_and_programmatic_activation_is_quiet(self, instance):
        from ui.settings_tab import SettingsTab

        instance.return_value.get.side_effect = lambda key, default=None: {"theme": "dark", "log_level": "INFO"}.get(key, False)
        widget = SettingsTab()
        self.addCleanup(widget.deleteLater)
        navigate = MagicMock(return_value=True)
        widget._main_window = SimpleNamespace(switch_to_route=navigate)
        widget.section_selector.setCurrentIndex(2)
        navigate.assert_called_once_with("settings:application")
        self.assertEqual(widget.settings_tabs.currentIndex(), 2)
        widget.activate_route("settings:about")
        self.assertEqual(widget.section_selector.currentIndex(), 4)
        self.assertEqual(navigate.call_count, 1)
        navigate.return_value = False
        widget.section_selector.setCurrentIndex(0)
        self.assertEqual(widget.section_selector.currentIndex(), 4)
        self.assertEqual(widget.settings_tabs.currentIndex(), 4)

    def test_history_records_are_collapsed_and_loading_is_explicit(self):
        service = SimpleNamespace(snapshot=MagicMock())
        widget = ActivityRecoveryTab(journal_service=service)
        self.addCleanup(widget.deleteLater)
        self.assertFalse(widget.history_details.toggle_button.isChecked())
        self.assertTrue(widget.review_button.isHidden())
        service.snapshot.assert_not_called()


if __name__ == "__main__":
    unittest.main()
