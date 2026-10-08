"""Rootless regression coverage for KDE appearance discovery and command policy."""

import unittest
from types import SimpleNamespace
from unittest.mock import Mock, mock_open, patch

from core.actions.contracts import ActionRun
from core.tasks.tweak_history import restoration_for
from core.execution_policy import classify_command, execution_allowed
from core.executor.action_result import ActionResult
from core.executor.command_policy import validate_command_vector
from core.tasks.tweaks import BY_ID, _parse_themes, _plasma_style_label, command_for, default_for, read_cursor_config, read_tweak
from core.tweak_commands import CURSOR_NOTIFY, custom_numeric_tweak, kde_read_vector, valid_value

SCHEMA = b'''<kcfg><kcfgfile name="kcminputrc"/><group name="Mouse">
<entry name="cursorTheme" type="String"><default>installed_default</default></entry>
<entry name="cursorSize" type="Int"><default>24</default></entry></group></kcfg>'''


def profile(session="wayland"):
    return SimpleNamespace(is_fedora=True, deployment_backend=SimpleNamespace(value="dnf5"),
                           desktop=SimpleNamespace(value="kde"), session_type=SimpleNamespace(value=session))


class TestKDEAppearanceCatalog(unittest.TestCase):
    def test_cursor_names_are_distinct_from_identifiers(self):
        current, choices = _parse_themes("Header\n * Breeze Dark [breeze_cursors]\n * Custom [custom-id] (Current theme for this Plasma session)", cursor=True)
        self.assertEqual(current, "custom-id")
        self.assertEqual(choices, (("breeze_cursors", "Breeze Dark"), ("custom-id", "Custom")))

    def test_theme_lists_fail_closed(self):
        for bad in ("* Broken", "* Theme [../bad]", "* Theme [--flag]", "* A [same]\n* B [same]", "* A [good]\n* Broken"):
            with self.subTest(bad=bad):
                self.assertEqual(_parse_themes(bad, cursor=True), ("", ()))

    @patch("core.tasks.tweaks._plasma_style_label", return_value="Readable name")
    def test_plasma_style_identifiers_and_names(self, label):
        self.assertEqual(_parse_themes("* custom.desktop (current theme for this Plasma session)", cursor=False),
                         ("custom.desktop", (("custom.desktop", "Readable name"),)))
        self.assertEqual(_parse_themes("* ../bad", cursor=False), ("", ()))

    @patch("core.tasks.tweaks.shutil.which", return_value="/usr/bin/tool")
    @patch("pathlib.Path.open", new_callable=mock_open, read_data=SCHEMA)
    def test_missing_keys_use_installed_defaults(self, opened, which):
        reader = Mock(return_value=ActionResult(True, "read", stdout=""))
        values, error = read_cursor_config(profile(), reader)
        self.assertEqual(error, "")
        self.assertEqual(values, {"kde-cursor-size": "24", "kde-cursor-theme": "installed_default"})
        for call in reader.call_args_list:
            self.assertEqual(call.kwargs["timeout"], 8)
            self.assertNotIn("--default", call.args[0])

    @patch("core.tasks.tweaks.shutil.which", return_value="/usr/bin/tool")
    @patch("pathlib.Path.open", new_callable=mock_open, read_data=SCHEMA)
    def test_dynamic_cursor_choices_and_custom_size(self, opened, which):
        def reader(vector, **kwargs):
            output = "37" if "cursorSize" in vector else "custom" if "cursorTheme" in vector else "* My cursor [custom]"
            return ActionResult(True, "read", stdout=output)
        state = read_tweak(BY_ID["kde-cursor-theme"], profile(), reader)
        self.assertEqual((state.status, state.value, state.choices), ("ready", "custom", (("custom", "My cursor"),)))
        state = read_tweak(BY_ID["kde-cursor-size"], profile(), reader)
        self.assertEqual((state.status, state.value), ("ready", "37"))
        self.assertNotIn("37", dict(state.choices))

    @patch("core.tasks.tweaks.shutil.which", return_value="/usr/bin/tool")
    @patch("pathlib.Path.open", side_effect=OSError)
    def test_missing_schema_blocks_reads(self, opened, which):
        reader = Mock()
        values, error = read_cursor_config(profile(), reader)
        self.assertEqual(values, {})
        self.assertIn("schema", error)
        reader.assert_not_called()

    @patch("core.tasks.tweaks.shutil.which", return_value="/usr/bin/tool")
    @patch("pathlib.Path.open", new_callable=mock_open, read_data=SCHEMA.replace(b"<default>24</default>", b"<default>513</default>"))
    def test_invalid_schema_default_blocks_reads(self, opened, which):
        reader = Mock()
        _values, error = read_cursor_config(profile(), reader)
        self.assertIn("unsupported default", error)
        reader.assert_not_called()

    @patch("core.tasks.tweaks.shutil.which", return_value="/usr/bin/tool")
    @patch("pathlib.Path.open", new_callable=mock_open, read_data=b'<!DOCTYPE kcfg [<!ENTITY malicious "24">]><kcfg/>')
    def test_schema_entities_are_rejected(self, opened, which):
        reader = Mock()
        _values, error = read_cursor_config(profile(), reader)
        self.assertIn("safely", error)
        reader.assert_not_called()

    @patch("core.tasks.tweaks.shutil.which", return_value="/usr/bin/tool")
    @patch("pathlib.Path.open", new_callable=mock_open, read_data=SCHEMA)
    def test_failed_current_read_never_uses_default(self, opened, which):
        _values, error = read_cursor_config(profile(), Mock(return_value=ActionResult(False, "read failed")))
        self.assertEqual(error, "read failed")

    @patch("core.tasks.tweaks.shutil.which", return_value="/usr/bin/tool")
    @patch("core.tasks.tweaks._plasma_style_label", return_value="My style")
    def test_plasma_read_uses_saved_value_over_session_marker(self, label, which):
        reader = Mock(side_effect=[ActionResult(True, "listed", stdout="* custom (aktuellt tema för denna session)"),
                                   ActionResult(True, "read", stdout="default")])
        state = read_tweak(BY_ID["kde-plasma-style"], profile(), reader)
        self.assertEqual((state.status, state.value), ("ready", "default"))
        self.assertEqual(reader.call_args_list[1].args[0], kde_read_vector("kde-plasma-style"))

    @patch("core.tasks.tweaks.shutil.which", side_effect=lambda tool: None if tool in {"dbus-send", "plasma-apply-cursortheme"} else "/usr/bin/tool")
    @patch("pathlib.Path.open", new_callable=mock_open, read_data=SCHEMA)
    def test_notification_and_listing_tool_loss_preserves_saved_size_restore(self, opened, which):
        def reader(vector, **kwargs):
            return ActionResult(True, "read", stdout="32" if "cursorSize" in vector else "custom")
        values, error = read_cursor_config(profile(), reader)
        self.assertEqual(error, "")
        self.assertEqual(values["kde-cursor-size"], "32")
        state = read_tweak(BY_ID["kde-cursor-size"], profile(), reader)
        self.assertEqual(state.status, "ready")
        run = ActionRun("source", "plan", "set-kde-cursor-size", "correlation", parameters={"value": "32"}, state="succeeded",
                        execution_result={"success": True}, verification_result={"success": True, "data": {
                            "tweak_change": {"version": 1, "kind": "change", "tweak_id": "kde-cursor-size", "before": "37", "after": "32"}}})
        self.assertEqual(restoration_for(BY_ID["kde-cursor-size"], state, [run]).before, "37")
        theme_state = read_tweak(BY_ID["kde-cursor-theme"], profile(), reader)
        self.assertEqual(theme_state.status, "unavailable")
        self.assertIn("plasma-apply-cursortheme", theme_state.message)

    @patch("core.tasks.tweaks.shutil.which", side_effect=lambda tool: None if tool == "dbus-send" else "/usr/bin/tool")
    @patch("pathlib.Path.open", new_callable=mock_open, read_data=SCHEMA)
    def test_notification_tool_loss_keeps_theme_ready(self, opened, which):
        def reader(vector, **kwargs):
            output = "32" if "cursorSize" in vector else "custom" if "cursorTheme" in vector else "* My cursor [custom]"
            return ActionResult(True, "read", stdout=output)
        self.assertEqual(read_tweak(BY_ID["kde-cursor-theme"], profile(), reader).status, "ready")

    @patch("pathlib.Path.open", new_callable=mock_open, read_data=b"[" * 2000 + b"]" * 2000)
    @patch.dict("os.environ", {"XDG_DATA_HOME": "/home/test/data", "XDG_DATA_DIRS": ":".join("/data/" + str(index) for index in range(50))})
    def test_deep_metadata_falls_back_and_roots_are_bounded(self, opened):
        self.assertEqual(_plasma_style_label("custom"), "custom")
        self.assertEqual(opened.call_count, 16)

    @patch("core.tasks.tweaks._plasma_style_label", return_value="Theme")
    def test_theme_metadata_work_is_bounded(self, label):
        output = "\n".join("* theme" + str(index) for index in range(257))
        self.assertEqual(_parse_themes(output, cursor=False), ("", ()))
        self.assertEqual(label.call_count, 256)

    def test_x11_is_blocked_before_probes(self):
        reader = Mock()
        values, error = read_cursor_config(profile("x11"), reader)
        self.assertEqual(values, {})
        self.assertIn("System Settings", error)
        reader.assert_not_called()

    @patch("core.tasks.tweaks.shutil.which", return_value=None)
    def test_missing_tool_is_unavailable(self, which):
        state = read_tweak(BY_ID["kde-cursor-theme"], profile(), Mock())
        self.assertEqual(state.status, "unavailable")

    def test_exact_custom_sizes_require_restore_authority(self):
        for value in ("0", "37", "512"):
            vector = command_for(BY_ID["kde-cursor-size"], value, restoring=True)
            validate_command_vector(vector)
            self.assertEqual(custom_numeric_tweak(vector[0], vector[1:]), "kde-cursor-size")
            self.assertFalse(execution_allowed(vector[0], vector[1:], authority="action_center", action_id="set-kde-cursor-size"))
            self.assertTrue(execution_allowed(vector[0], vector[1:], authority="action_center", action_id="restore-kde-cursor-size"))
            with self.assertRaises(ValueError):
                command_for(BY_ID["kde-cursor-size"], value)
        for value in ("-1", "513", "37.0", "nan", "０"):
            self.assertFalse(valid_value("kde-cursor-size", value))

    def test_commands_are_exact_and_keys_independent(self):
        for item, value in (("kde-cursor-theme", "custom"), ("kde-cursor-size", "32"), ("kde-plasma-style", "custom.desktop")):
            vector = command_for(BY_ID[item], value)
            validate_command_vector(vector)
            self.assertEqual(classify_command(vector[0], vector[1:]), "session")
            validate_command_vector(kde_read_vector(item))
        self.assertEqual(command_for(BY_ID["kde-cursor-theme"], "custom")[-2:], ["cursorTheme", "custom"])
        self.assertEqual(command_for(BY_ID["kde-cursor-size"], "32")[-2:], ["cursorSize", "32"])
        validate_command_vector(CURSOR_NOTIFY)
        self.assertEqual(classify_command(CURSOR_NOTIFY[0], CURSOR_NOTIFY[1:]), "session")
        self.assertEqual(classify_command(CURSOR_NOTIFY[0], list(CURSOR_NOTIFY[1:-1]) + ["int32:1"]), "manual_only")
        self.assertEqual(default_for(BY_ID["kde-cursor-theme"]), "")
        self.assertEqual(default_for(BY_ID["kde-plasma-style"]), "")
        self.assertEqual(default_for(BY_ID["kde-cursor-size"]), "24")
