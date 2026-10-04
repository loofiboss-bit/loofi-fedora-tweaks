"""Contracts for GNOME Files, Dolphin, and KWin setting controls."""

from __future__ import annotations

import os
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication

from core.actions.catalog import ActionCatalog
from core.executor.action_result import ActionResult
from core.executor.command_policy import validate_command_vector
from core.tasks.tweaks import BY_ID, TweakState, command_for, default_for, read_tweak
from core.tweak_commands import gnome_schema, tweak_command_class, valid_value
from ui.tweaks_page import TweaksPage


def _profile(desktop: str) -> SimpleNamespace:
    return SimpleNamespace(
        is_fedora=True,
        is_atomic=False,
        desktop=SimpleNamespace(value=desktop),
        deployment_backend=SimpleNamespace(value="dnf5"),
    )


@patch("core.tasks.tweaks.kde_capability_error", return_value="")
class TestFileAndWindowTweakContracts(unittest.TestCase):
    EXPECTED = {
        "gnome-files-click-policy": {
            "default": "double",
            "values": {"single", "double"},
            "schema": "org.gnome.nautilus.preferences",
            "key": "click-policy",
            "desktop": "gnome",
        },
        "gnome-files-default-folder-view": {
            "default": "icon-view",
            "values": {"icon-view", "list-view"},
            "schema": "org.gnome.nautilus.preferences",
            "key": "default-folder-viewer",
            "desktop": "gnome",
        },
        "kde-dolphin-show-full-path": {
            "default": "false",
            "values": {"true", "false"},
            "read": ["kreadconfig6", "--file", "dolphinrc", "--group", "General", "--key", "ShowFullPath", "--default", "false"],
            "write": ["kwriteconfig6", "--notify", "--file", "dolphinrc", "--group", "General", "--key", "ShowFullPath", "true"],
            "desktop": "kde",
        },
        "kde-borderless-maximized-windows": {
            "default": "false",
            "values": {"true", "false"},
            "read": ["kreadconfig6", "--file", "kwinrc", "--group", "Windows", "--key", "BorderlessMaximizedWindows", "--default", "false"],
            "write": ["kwriteconfig6", "--notify", "--file", "kwinrc", "--group", "Windows", "--key", "BorderlessMaximizedWindows", "true"],
            "desktop": "kde",
        },
    }

    def test_catalog_defaults_values_commands_and_action_registration(self, _capability) -> None:
        catalog = ActionCatalog()
        for tweak_id, expected in self.EXPECTED.items():
            tweak = BY_ID[tweak_id]
            with self.subTest(tweak=tweak_id):
                self.assertEqual(tweak.desktop, expected["desktop"])
                self.assertEqual(default_for(tweak), expected["default"])
                self.assertEqual({value for value, _label in tweak.choices}, expected["values"])
                self.assertEqual(catalog.get(tweak.action_id).id, tweak.action_id)
                self.assertEqual(catalog.get(f"restore-{tweak.id}").id, f"restore-{tweak.id}")

                for value in expected["values"]:
                    self.assertTrue(valid_value(tweak_id, value))
                    vector = command_for(tweak, value)
                    validate_command_vector(vector)
                    self.assertEqual(tweak_command_class(vector[0], vector[1:]), "session")

                for value in ("", "true; touch /tmp/nope", "undefined", "single-click"):
                    if value in expected["values"]:
                        continue
                    self.assertFalse(valid_value(tweak_id, value))
                    with self.assertRaises(ValueError):
                        command_for(tweak, value)

                if tweak_id.startswith("gnome-"):
                    self.assertEqual(gnome_schema(tweak_id), expected["schema"])
                    for value in expected["values"]:
                        self.assertEqual(command_for(tweak, value), ["gsettings", "set", expected["schema"], expected["key"], value])
                else:
                    self.assertEqual(command_for(tweak, "true"), expected["write"])
                    from core.tasks.tweaks import _read_vector

                    self.assertEqual(_read_vector(tweak), expected["read"])
                    validate_command_vector(_read_vector(tweak))
                    self.assertEqual(tweak_command_class(expected["read"][0], expected["read"][1:]), "read_only")

    def test_missing_files_schema_is_unavailable_and_each_read_is_fresh(self, _capability) -> None:
        tweak = BY_ID["gnome-files-click-policy"]
        missing = read_tweak(
            tweak,
            _profile("gnome"),
            lambda vector, **kwargs: ActionResult.fail("No such schema", action_id=kwargs["action_id"]),
        )
        self.assertEqual(missing.status, "unavailable")

        outputs = iter(("'single'\n", "'double'\n"))
        calls: list[list[str]] = []

        def reader(vector, **kwargs):
            calls.append(list(vector))
            return ActionResult.ok("Read", stdout=next(outputs), action_id=kwargs["action_id"])

        first = read_tweak(tweak, _profile("gnome"), reader)
        second = read_tweak(tweak, _profile("gnome"), reader)
        self.assertEqual((first.value, second.value), ("single", "double"))
        self.assertEqual(calls, [
            ["gsettings", "get", "org.gnome.nautilus.preferences", "click-policy"],
            ["gsettings", "get", "org.gnome.nautilus.preferences", "click-policy"],
        ])

    @patch("core.tasks.tweaks.shutil.which", return_value=None)
    def test_dolphin_setting_is_unavailable_when_dolphin_is_missing(self, _which, _capability) -> None:
        reader = Mock()
        state = read_tweak(BY_ID["kde-dolphin-show-full-path"], _profile("kde"), reader)
        self.assertEqual(state.status, "unavailable")
        self.assertIn("Dolphin is not installed", state.message)
        reader.assert_not_called()

    @patch("core.tasks.tweaks.shutil.which", return_value="/usr/bin/dolphin")
    def test_installed_dolphin_and_kwin_settings_read_as_ready(self, _which, _capability) -> None:
        for tweak_id in ("kde-dolphin-show-full-path", "kde-borderless-maximized-windows"):
            state = read_tweak(
                BY_ID[tweak_id],
                _profile("kde"),
                lambda vector, **kwargs: ActionResult.ok("Read", stdout="false\n", action_id=kwargs["action_id"]),
            )
            with self.subTest(tweak=tweak_id):
                self.assertEqual(state.status, "ready")
                self.assertEqual(state.value, "false")


@patch("core.tasks.tweaks.kde_capability_error", return_value="")
class TestFileAndWindowTweakUi(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def test_gnome_files_row_search_changed_filter_and_reset(self, _capability) -> None:
        tweak = BY_ID["gnome-files-click-policy"]
        page = TweaksPage(_profile("gnome"))
        changes: list[tuple[str, str]] = []
        page.changeRequested.connect(lambda tweak_id, value: changes.append((tweak_id, value)))
        try:
            self.assertIn("gnome-files-default-folder-view", page._rows)
            page.set_states((TweakState(tweak, "ready", "single", tweak.choices),))
            row, _control = page._rows[tweak.id]
            self.assertFalse(page._reset_buttons[tweak.id].isHidden())
            page.search_input.setText("single")
            self.assertFalse(row.isHidden())
            page.changed_only.setChecked(True)
            self.assertFalse(row.isHidden())
            page._reset_buttons[tweak.id].click()
            self.assertEqual(changes, [(tweak.id, "double")])
        finally:
            page.close()

    def test_kde_files_row_and_previous_value_restore_control(self, _capability) -> None:
        tweak = BY_ID["kde-dolphin-show-full-path"]
        state = TweakState(tweak, "ready", "true", tweak.choices, restore_run_id="run-123", restore_value="false")
        page = TweaksPage(_profile("kde"))
        restored: list[tuple[str, str]] = []
        page.restoreRequested.connect(lambda tweak_id, source_id: restored.append((tweak_id, source_id)))
        try:
            self.assertIn("kde-borderless-maximized-windows", page._rows)
            page.set_states((state,))
            row, _control = page._rows[tweak.id]
            self.assertFalse(row.isHidden())
            self.assertFalse(page._reset_buttons[tweak.id].isHidden())
            button = page._restore_buttons[tweak.id]
            self.assertTrue(button.isEnabled())
            button.click()
            self.assertEqual(restored, [(tweak.id, "run-123")])
            page.search_input.setText("full path")
            self.assertFalse(row.isHidden())
            page.changed_only.setChecked(True)
            self.assertFalse(row.isHidden())
        finally:
            page.close()


if __name__ == "__main__":
    unittest.main()
