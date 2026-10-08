"""Rootless contracts for the manual KDE X11 cursor settings handoff."""

import os
import subprocess
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication

from core.catalog_models import NativeHandoffId
from core.platform.profile import DesktopEnvironment, SessionType
from core.tasks.tweaks import Tweak
from services.desktop.native_handoff import NativeHandoffService
from ui.tweaks_page import TweaksPage


CURSOR_TWEAKS = tuple(
    Tweak(tweak_id, title, "Choose a cursor setting.", "Appearance", "kde", "set-" + tweak_id, ())
    for tweak_id, title in (("kde-cursor-theme", "Cursor theme"), ("kde-cursor-size", "Cursor size"))
)


def profile(desktop=DesktopEnvironment.KDE, session=SessionType.X11):
    return SimpleNamespace(desktop=desktop, session_type=session, is_fedora=True)


class TestCursorNativeService(unittest.TestCase):
    def test_fixed_cursor_target_requires_exact_installed_module(self):
        runner = MagicMock(return_value=subprocess.CompletedProcess([], 0, "kcm_cursortheme - Cursors\n"))
        service = NativeHandoffService(which=MagicMock(return_value="/usr/bin/kcmshell6"), runner=runner)
        launch = service.prepare_launch(NativeHandoffId.CURSOR_SETTINGS, profile=profile())
        self.assertEqual(launch.arguments, ("kcm_cursortheme",))
        self.assertEqual(launch.program, "/usr/bin/kcmshell6")
        runner.return_value.stdout = "kcm_cursortheme-extra - Other\n"
        self.assertIsNone(service.prepare_launch(NativeHandoffId.CURSOR_SETTINGS, profile=profile()))

    def test_missing_tool_is_unavailable_without_probe(self):
        runner = MagicMock()
        service = NativeHandoffService(which=MagicMock(return_value=None), runner=runner)
        self.assertFalse(service.availability(NativeHandoffId.CURSOR_SETTINGS, profile=profile()).available)
        runner.assert_not_called()

    def test_gnome_has_no_cursor_kcm_handoff(self):
        which, runner = MagicMock(), MagicMock()
        service = NativeHandoffService(which=which, runner=runner)
        self.assertFalse(service.availability(NativeHandoffId.CURSOR_SETTINGS, profile=profile(DesktopEnvironment.GNOME)).available)
        which.assert_not_called()
        runner.assert_not_called()


@patch("ui.tweaks_page.visible_tweaks", return_value=CURSOR_TWEAKS)
@patch("ui.tweaks_page.SettingsManager.instance")
class TestCursorHandoffPresentation(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_x11_buttons_wait_for_async_result_and_emit_request(self, settings, _tweaks):
        settings.return_value.get.return_value = []
        page = TweaksPage(profile())
        self.addCleanup(page.close)
        self.assertEqual(set(page.cursor_settings_buttons), {"kde-cursor-theme", "kde-cursor-size"})
        requested = MagicMock()
        page.cursor_settings_requested.connect(requested)
        button = page.cursor_settings_buttons["kde-cursor-theme"]
        self.assertFalse(button.isEnabled())
        page.set_cursor_settings_availability(True, "Cursor Settings is available.")
        button.click()
        requested.assert_called_once_with()
        page.set_busy(True)
        self.assertFalse(button.isEnabled())
        page.set_busy(False)
        self.assertTrue(button.isEnabled())
        page.set_cursor_settings_availability(False, "kcmshell6 is missing.")
        self.assertFalse(button.isEnabled())
        self.assertEqual(page.cursor_settings_status["kde-cursor-size"].text(), "kcmshell6 is missing.")

    def test_handoff_absent_outside_kde_x11(self, settings, _tweaks):
        settings.return_value.get.return_value = []
        for host in (profile(session=SessionType.WAYLAND), profile(DesktopEnvironment.GNOME)):
            page = TweaksPage(host)
            self.addCleanup(page.close)
            self.assertEqual(page.cursor_settings_buttons, {})
            self.assertEqual(page.cursor_settings_status, {})


if __name__ == "__main__":
    unittest.main()
