"""Appearance discovery, favorites and asynchronous native launch contracts."""

import os
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication

from core.tasks.tweaks import BY_ID, TweakState
from ui.kde_appearance import CursorSettingsMixin
from ui.tweaks_page import TweaksPage


class TestAppearancePresentation(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    @patch("ui.tweaks_page.SettingsManager.instance")
    def test_dynamic_names_custom_size_search_and_favorites(self, settings):
        values = {"favorite_tweaks": []}
        settings.return_value.get.side_effect = lambda key, default=None: values.get(key, default)
        settings.return_value.set.side_effect = lambda key, value: values.__setitem__(key, value)
        settings.return_value.save.return_value = True
        profile = SimpleNamespace(is_fedora=True, deployment_backend=SimpleNamespace(value="dnf5"),
                                  desktop=SimpleNamespace(value="kde"), session_type=SimpleNamespace(value="wayland"))
        page = TweaksPage(profile)
        self.addCleanup(page.close)
        changes = []
        page.changeRequested.connect(lambda *args: changes.append(args))
        theme = BY_ID["kde-cursor-theme"]
        size = BY_ID["kde-cursor-size"]
        page.set_states((TweakState(theme, "ready", "custom-pointer", (("custom-pointer", "Readable pointer name"),)),
                         TweakState(size, "ready", "37", size.choices)))
        self.assertEqual(changes, [])
        self.assertEqual(page._rows[theme.id][1].currentText(), "Readable pointer name")
        self.assertIn("Readable pointer name", page._rows[theme.id][0].value_label.text())
        self.assertEqual(page._rows[size.id][1].currentData(), "37")
        page.search_input.setText("Pointer theme")
        self.assertFalse(page._rows[theme.id][0].isHidden())
        self.assertTrue(page._rows[size.id][0].isHidden())
        page.search_input.clear()
        page._favorite_buttons[theme.id].click()
        page._view_buttons["favorites"].setChecked(True)
        self.assertFalse(page._rows[theme.id][0].isHidden())
        self.assertTrue(page._rows[size.id][0].isHidden())
        self.assertIn(theme.id, values["favorite_tweaks"])


class TestNativeCursorOwner(unittest.TestCase):
    def setUp(self):
        self.adapter = MagicMock()
        self.adapter.start.return_value = True
        self.owner = SimpleNamespace(_utility_operation_adapter=None,
                                     _new_utility_operation_adapter=MagicMock(return_value=self.adapter), tr=lambda text: text)
        self.page = MagicMock(cursor_settings_buttons={"kde-cursor-theme": MagicMock()}, profile=object())

    @patch("services.desktop.native_handoff.NativeHandoffService")
    def test_discovery_runs_only_in_worker_and_projects_unavailable(self, service):
        availability = SimpleNamespace(available=False, detail="Cursor Settings is missing")
        service.return_value.availability.return_value = availability
        self.assertTrue(CursorSettingsMixin._refresh_cursor_settings_handoff(self.owner, self.page))
        service.assert_not_called()
        result = self.adapter.start.call_args.args[0]()
        self.adapter.finished.connect.call_args.args[0](result)
        self.page.set_cursor_settings_availability.assert_called_once_with(False, availability.detail)

    @patch("PyQt6.QtCore.QProcess.startDetached", return_value=(True, 42))
    @patch("services.desktop.native_handoff.NativeHandoffService")
    def test_launch_waits_for_worker_revalidation(self, service, detached):
        service.return_value.prepare_launch.return_value = SimpleNamespace(program="/usr/bin/kcmshell6", arguments=("kcm_cursortheme",))
        self.assertTrue(CursorSettingsMixin._open_cursor_settings(self.owner, self.page))
        service.assert_not_called()
        detached.assert_not_called()
        result = self.adapter.start.call_args.args[0]()
        detached.assert_not_called()
        self.adapter.finished.connect.call_args.args[0](result)
        detached.assert_called_once_with("/usr/bin/kcmshell6", ["kcm_cursortheme"])

    @patch("PyQt6.QtCore.QProcess.startDetached")
    @patch("services.desktop.native_handoff.NativeHandoffService")
    def test_missing_native_tool_never_launches(self, service, detached):
        service.return_value.prepare_launch.return_value = None
        self.assertTrue(CursorSettingsMixin._open_cursor_settings(self.owner, self.page))
        result = self.adapter.start.call_args.args[0]()
        self.adapter.finished.connect.call_args.args[0](result)
        detached.assert_not_called()
        self.assertFalse(self.page.set_cursor_settings_availability.call_args.args[0])

    def test_active_reader_blocks_native_handoff(self):
        self.owner._utility_operation_adapter = object()
        self.assertFalse(CursorSettingsMixin._open_cursor_settings(self.owner, self.page))
        self.assertFalse(CursorSettingsMixin._refresh_cursor_settings_handoff(self.owner, self.page))
        self.adapter.start.assert_not_called()

    @patch("PyQt6.QtCore.QProcess.startDetached")
    @patch("services.desktop.native_handoff.NativeHandoffService")
    def test_shutdown_during_native_probe_suppresses_late_launch(self, service, detached):
        service.return_value.prepare_launch.return_value = SimpleNamespace(program="/usr/bin/kcmshell6", arguments=("kcm_cursortheme",))
        self.assertTrue(CursorSettingsMixin._open_cursor_settings(self.owner, self.page))
        result = self.adapter.start.call_args.args[0]()
        self.owner._pending_runtime_shutdown = "close"
        self.adapter.finished.connect.call_args.args[0](result)
        detached.assert_not_called()

    def test_shutdown_never_starts_another_reader_or_launch(self):
        for attribute, value in (("_pending_runtime_shutdown", "close"), ("_runtime_cleaned", True)):
            setattr(self.owner, attribute, value)
            self.assertFalse(CursorSettingsMixin._refresh_cursor_settings_handoff(self.owner, self.page))
            self.assertFalse(CursorSettingsMixin._open_cursor_settings(self.owner, self.page))
            delattr(self.owner, attribute)
        self.adapter.start.assert_not_called()
