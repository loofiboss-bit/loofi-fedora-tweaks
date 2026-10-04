"""Wayfinder state-backed control, filter, and favorite regression tests."""

import os
import unittest
from dataclasses import replace
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtCore import Qt
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QApplication, QBoxLayout, QCheckBox, QScrollArea

from core.tasks.tweaks import BY_ID, TweakState
from ui.components.settings import SettingRow
from ui.tweaks_page import TweaksPage
from utils.settings import AppSettings, SettingsManager, migrate_settings


def profile():
    return SimpleNamespace(is_fedora=True, desktop=SimpleNamespace(value="kde"), deployment_backend=SimpleNamespace(value="dnf5"))


class TestWayfinderTweaksUi(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    @patch("ui.tweaks_page.SettingsManager.instance")
    def setUp(self, instance):
        self.store = MagicMock()
        self.values = {"favorite_tweaks": []}
        self.store.get.side_effect = lambda key, default=None: self.values.get(key, default)
        self.store.set.side_effect = lambda key, value: self.values.__setitem__(key, value)
        self.store.save.return_value = True
        instance.return_value = self.store
        self.page = TweaksPage(profile())
        self.addCleanup(self.page.close)
        self.tweak = BY_ID["kde-dolphin-show-full-path"]
        self.state = TweakState(self.tweak, "ready", "false", self.tweak.choices)

    def test_independent_state_refresh_never_requests_mutation(self):
        changes = []
        self.page.changeRequested.connect(lambda *args: changes.append(args))
        self.page.set_states((self.state,))
        self.page.set_states((replace(self.state, value="true"),))
        self.assertEqual(changes, [])
        row, control = self.page._rows[self.tweak.id]
        self.assertEqual(control.currentData(), "true")
        self.assertIn("On", row.value_label.text())
        self.assertEqual(control.property("controlKind"), "switch")
        semantic = self.page._rows["kde-single-click"][1]
        semantic.clear()
        for value, label in BY_ID["kde-single-click"].choices:
            semantic.addItem(label, value)
        semantic.rebuild()
        self.assertEqual(semantic.property("controlKind"), "segmented")

    def test_filters_intersect_alias_category_and_view_then_clear(self):
        self.page.set_states((replace(self.state, value="true"),))
        self.page.search_input.setText("Dolphin")
        self.page.changed_only.setChecked(True)
        row = self.page._rows[self.tweak.id][0]
        self.assertFalse(row.isHidden())
        self.page.category_filter.setCurrentIndex(self.page.category_filter.findData("Appearance"))
        self.assertTrue(row.isHidden())
        self.assertFalse(self.page.empty_state.isHidden())
        self.page.clear_filters_button.click()
        self.assertFalse(row.isHidden())
        self.assertEqual(self.page.search_input.text(), "")
        self.assertTrue(self.page._view_buttons["all"].isChecked())
        self.page.set_states((replace(self.state, status="unavailable", message="Dolphin is missing"),))
        self.page._view_buttons["unavailable"].setChecked(True)
        self.assertFalse(row.isHidden())
        self.assertIn("Dolphin is missing", row.feedback_label.text())

    @patch("ui.tweaks_page.SettingsManager.instance")
    def test_favorite_survives_page_recreation(self, instance):
        self.page._favorite_buttons[self.tweak.id].click()
        instance.return_value = self.store
        recreated = TweaksPage(profile())
        self.addCleanup(recreated.close)
        self.assertTrue(recreated._favorite_buttons[self.tweak.id].isChecked())
        recreated._view_buttons["favorites"].setChecked(True)
        self.assertFalse(recreated._rows[self.tweak.id][0].isHidden())
        self.assertTrue(recreated._rows["kde-color"][0].isHidden())

    def test_favorite_save_failure_rolls_back_ui_and_memory(self):
        button = self.page._favorite_buttons[self.tweak.id]
        button.click()
        self.assertEqual(self.values["favorite_tweaks"], [self.tweak.id])
        self.store.save.return_value = False
        button.click()
        self.assertTrue(button.isChecked())
        self.assertEqual(self.values["favorite_tweaks"], [self.tweak.id])
        self.assertIn("Could not save", self.page.status_label.text())
        self.page._view_buttons["favorites"].setChecked(True)
        self.assertFalse(self.page._rows[self.tweak.id][0].isHidden())

    def test_busy_blocks_writes_but_keeps_search_and_favorites(self):
        self.page.set_states((self.state,))
        row, control = self.page._rows[self.tweak.id]
        changes = []
        self.page.changeRequested.connect(lambda *args: changes.append(args))
        self.page.set_busy(True)
        self.assertFalse(control.isEnabled())
        self.assertTrue(self.page.search_input.isEnabled())
        self.assertTrue(self.page.category_filter.isEnabled())
        self.page._favorite_buttons[self.tweak.id].click()
        self.assertIn(self.tweak.id, self.values["favorite_tweaks"])
        control.setCurrentIndex(control.findData("true"))
        control.activated.emit(0)
        self.assertEqual(changes, [])
        self.page.set_busy(False)
        control.activated.emit(0)
        self.assertEqual(changes, [(self.tweak.id, "true")])
        self.assertIn("Verified: Off", row.value_label.text())
        self.assertIn("Pending: On", row.value_label.text())
        self.page.restore_selection(self.tweak.id)
        self.assertEqual(control.currentData(), "false")
        self.assertNotIn("Pending", row.value_label.text())

    def test_custom_value_preserved_and_previous_label_readable(self):
        tweak = BY_ID["kde-double-click-interval"]
        self.page.set_states((TweakState(tweak, "ready", "525", tweak.choices, restore_run_id="old", restore_value="400"),))
        row, control = self.page._rows[tweak.id]
        self.assertEqual(control.currentData(), "525")
        self.assertEqual(control.property("controlKind"), "dropdown")
        self.assertIn("400 ms", self.page._restore_buttons[tweak.id].text())
        self.assertIn("525", row.value_label.text())

    def test_switch_keyboard_keeps_native_checked_semantics(self):
        self.page.set_states((self.state,))
        _row, control = self.page._rows[self.tweak.id]
        switch = control._editor
        self.assertIsInstance(switch, QCheckBox)
        changes = []
        self.page.changeRequested.connect(lambda *args: changes.append(args))
        QTest.keyClick(switch, Qt.Key.Key_Space)
        self.assertTrue(switch.isChecked())
        self.assertEqual(changes, [(self.tweak.id, "true")])
        self.page.restore_selection(self.tweak.id)
        self.assertFalse(switch.isChecked())
        self.assertEqual(len(changes), 1)

    def test_rendered_controls_and_actions_have_useful_width(self):
        states = tuple(TweakState(BY_ID[key], "ready", BY_ID[key].choices[0][0], BY_ID[key].choices)
                       for key in ("kde-single-click", "kde-double-click-interval", "kde-smooth-scroll"))
        self.page.set_states(states)
        viewport = QScrollArea()
        viewport.setWidgetResizable(True)
        viewport.setWidget(self.page)
        self.addCleanup(lambda: (viewport.takeWidget(), viewport.close()))
        viewport.show()
        for width in (900, 1280, 560):
            with self.subTest(width=width):
                viewport.resize(width, 650)
                for _iteration in range(5):
                    self.app.processEvents()
                for state in states:
                    row, control = self.page._rows[state.tweak.id]
                    self.assertGreater(row.control_panel.width(), 100)
                    self.assertGreater(control.width(), 100)
                    editors = control._buttons if control._buttons else [control._editor]
                    for editor in editors:
                        self.assertTrue(editor.isVisibleTo(self.page))
                        self.assertGreaterEqual(editor.width(), editor.minimumSizeHint().width())
                    favorite = self.page._favorite_buttons[state.tweak.id]
                    self.assertTrue(favorite.isVisibleTo(self.page))
                    self.assertGreater(favorite.width(), 0)
                    self.assertFalse(favorite.icon().isNull())

    def test_setting_row_adapts_to_available_width(self):
        row = SettingRow("Title", "Description", QCheckBox())
        self.addCleanup(row.close)
        row.resize(900, 140)
        row.show()
        self.app.processEvents()
        self.assertEqual(row.content_layout.direction(), QBoxLayout.Direction.LeftToRight)
        row.resize(450, 200)
        self.app.processEvents()
        self.assertEqual(row.content_layout.direction(), QBoxLayout.Direction.TopToBottom)


class TestFavoriteTweakSettings(unittest.TestCase):
    def test_defaults_and_normalization_are_unique(self):
        self.assertEqual(AppSettings().favorite_tweaks, [])
        values, _migrated = migrate_settings({"favorite_tweaks": ["kde-color", "kde-color", "", "gnome-clock"]})
        self.assertEqual(values["favorite_tweaks"], ["kde-color", "gnome-clock"])

    @patch("utils.settings.SettingsManager._load")
    @patch("utils.settings.Path.replace")
    @patch("utils.settings.Path.write_text")
    @patch("utils.settings.Path.mkdir")
    def test_save_uses_atomic_replace(self, mkdir, write, replace_path, load):
        manager = SettingsManager()
        manager.set("favorite_tweaks", ["kde-color", "kde-color"])
        self.assertTrue(manager.save())
        self.assertEqual(manager.get("favorite_tweaks"), ["kde-color"])
        self.assertIn('"favorite_tweaks"', write.call_args.args[0])
        replace_path.assert_called_once()
