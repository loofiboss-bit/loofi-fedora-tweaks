"""Contracts for curated preset values and focused setting inspection."""
from __future__ import annotations

import os
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication, QToolButton
from core.executor.action_result import ActionResult
from core.tasks.tweak_presets import list_presets, profile_for_preset
from core.tasks.tweaks import BY_ID, TweakState, inspect_one, snapshot
from test_tweaks_v30_1 import profile
from ui.tweaks_page import TweaksPage


class TweakPresetTests(unittest.TestCase):
    def test_presets_resolve_to_supported_desktop_profile_values(self):
        self.assertEqual(
            dict(profile_for_preset("reduced-motion", profile("gnome")).settings),
            {"gnome-animations": "false"},
        )
        self.assertEqual(
            dict(profile_for_preset("reduced-motion", profile("kde")).settings),
            {"kde-animation": "0", "kde-wobbly-windows": "false"},
        )
        self.assertEqual(
            dict(profile_for_preset("file-navigation", profile("kde")).settings),
            {"kde-single-click": "false", "kde-dolphin-editable-location": "true",
             "kde-dolphin-show-full-path": "true"},
        )
        self.assertEqual({item.id for item in list_presets()}, {"reduced-motion", "file-navigation"})
        with self.assertRaises(TypeError):
            list_presets()[0].settings["gnome"]["gnome-animations"] = "true"

    def test_unknown_and_unsupported_desktops_fail_closed(self):
        with self.assertRaisesRegex(ValueError, "Unknown tweak preset"):
            profile_for_preset("custom", profile("gnome"))
        with self.assertRaisesRegex(ValueError, "unavailable"):
            profile_for_preset("file-navigation", profile("xfce"))


class FocusedInspectionTests(unittest.TestCase):
    @patch("core.tasks.tweaks.kde_capability_error", return_value="")
    def test_inspects_only_the_requested_setting_with_bounded_timeout(self, _capability):
        runtime = Mock()
        runtime.tweak_runs.return_value = ()
        runtime.execute_read_only.return_value = ActionResult.ok("Read", stdout="true\n")

        result = inspect_one("gnome-battery", profile("gnome"), runtime)

        self.assertEqual(result.status, "ready")
        self.assertEqual(result.value, "true")
        runtime.execute_read_only.assert_called_once()
        self.assertLessEqual(runtime.execute_read_only.call_args.kwargs["timeout"], 8.0)

    @patch("core.tasks.tweaks.kde_capability_error", return_value="")
    def test_snapshot_can_recheck_only_selected_profile_rows(self, _capability):
        runtime = Mock()
        runtime.tweak_runs.return_value = ()
        runtime.execute_read_only.return_value = ActionResult.ok("Read", stdout="true\n")

        result = snapshot(profile("gnome"), runtime, tweak_ids=("gnome-battery",))

        self.assertEqual([state.tweak.id for state in result], ["gnome-battery"])
        runtime.execute_read_only.assert_called_once()

    def test_selected_snapshot_rejects_settings_outside_the_desktop(self):
        runtime = Mock()
        with self.assertRaisesRegex(ValueError, "unavailable"):
            snapshot(profile("gnome"), runtime, tweak_ids=("kde-single-click",))
        runtime.execute_read_only.assert_not_called()

    @patch("core.tasks.tweaks.kde_capability_error", return_value="")
    def test_timeout_and_cancellation_do_not_read_or_report_a_current_value(self, _capability):
        runtime = Mock()
        runtime.tweak_runs.return_value = ()
        times = iter((1.0, 10.0))
        timed_out = inspect_one("gnome-battery", profile("gnome"), runtime, clock=lambda: next(times))
        self.assertEqual(timed_out.status, "unavailable")
        self.assertIn("time limit", timed_out.message)
        runtime.execute_read_only.assert_not_called()

        cancelled = inspect_one("gnome-battery", profile("gnome"), runtime, is_cancelled=lambda: True)
        self.assertEqual(cancelled.status, "unavailable")
        self.assertIn("cancelled", cancelled.message)
        runtime.execute_read_only.assert_not_called()

    @patch("core.tasks.tweaks.kde_capability_error", return_value="")
    def test_read_timeout_and_cancellation_during_read_mark_value_unavailable(self, _capability):
        runtime = Mock()
        runtime.tweak_runs.return_value = ()
        runtime.execute_read_only.return_value = ActionResult.fail("The setting read timed out.")
        timed_out = inspect_one("gnome-battery", profile("gnome"), runtime)
        self.assertEqual(timed_out.status, "unavailable")
        self.assertEqual(timed_out.value, "")
        self.assertIn("timed out", timed_out.message)
        self.assertLessEqual(runtime.execute_read_only.call_args.kwargs["timeout"], 8.0)

        cancelled = {"value": False}

        def finish_read(*_args, **_kwargs):
            cancelled["value"] = True
            return ActionResult.ok("Read", stdout="true\n")

        runtime.execute_read_only.side_effect = finish_read
        result = inspect_one("gnome-battery", profile("gnome"), runtime, is_cancelled=lambda: cancelled["value"])
        self.assertEqual(result.status, "unavailable")
        self.assertEqual(result.value, "")
        self.assertIn("cancelled", result.message)


class FocusedInspectionUiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_row_check_action_and_partial_read_preserve_other_rows_and_search(self):
        first = BY_ID["gnome-battery"]
        other = BY_ID["gnome-hot-corners"]
        page = TweaksPage(profile("gnome"))
        requested = []
        page.inspectRequested.connect(requested.append)
        try:
            page.set_states((
                TweakState(first, "ready", value="true", choices=first.choices),
                TweakState(other, "ready", value="false", choices=other.choices),
            ))
            button = page._rows[first.id][0].findChild(QToolButton, "tweakRowActions")
            button.menu().actions()[0].trigger()
            self.assertEqual(requested, [first.id])

            other_value = page._rows[other.id][0].value_label.text()
            favorites = set(page._favorites)
            page.search_input.setText("Hot corners")
            page.set_states((TweakState(first, "ready", value="false", choices=first.choices),))
            self.assertEqual(page.search_input.text(), "Hot corners")
            self.assertEqual(page._rows[other.id][0].value_label.text(), other_value)
            self.assertEqual(page._favorites, favorites)
            self.assertEqual(page._rows[first.id][0].value_label.text(), "Verified: Off")
        finally:
            page.close()

    @patch("ui.tweak_profiles.QMessageBox")
    def test_cancelled_profile_recheck_invalidates_only_selected_rows(self, message_box):
        from types import SimpleNamespace
        from PyQt6.QtWidgets import QWidget
        from ui.tweak_profiles import TweakProfilesMixin

        class Signal:
            def __init__(self):
                self.callback = None

            def connect(self, callback):
                self.callback = callback

        first = BY_ID["gnome-battery"]
        other = BY_ID["gnome-hot-corners"]
        page = TweaksPage(profile("gnome"))
        page.set_states((
            TweakState(first, "ready", value="true", choices=first.choices),
            TweakState(other, "ready", value="false", choices=other.choices),
        ))
        other_value = page._rows[other.id][0].value_label.text()
        adapter = SimpleNamespace(finished=Signal(), failed=Signal(), cancelled=Signal(), start=Mock(return_value=True))
        controller = SimpleNamespace(orchestrator=SimpleNamespace(runtime=Mock()))
        owner = QWidget()
        owner._profile_controller = Mock(return_value=controller)
        owner._new_utility_operation_adapter = Mock(return_value=adapter)
        result = SimpleNamespace(
            success=True,
            message="Profile change completed.",
            entries=(SimpleNamespace(id=first.id, status="succeeded", message="Verified"),
                     SimpleNamespace(id=other.id, status="skipped", message="Not selected")),
        )
        try:
            TweakProfilesMixin._finish_tweak_profile(owner, page, result)
            adapter.cancelled.callback()
            self.assertEqual(page._rows[first.id][0].value_label.text(), "Current value unavailable")
            self.assertFalse(page._rows[first.id][1].isEnabled())
            self.assertEqual(page._rows[other.id][0].value_label.text(), other_value)
            self.assertTrue(page._rows[other.id][1].isEnabled())
        finally:
            owner.close()
            page.close()


class PresetCliTests(unittest.TestCase):
    def test_preset_parser_requires_explicit_confirmation_for_apply(self):
        from cli.parser import build_parser

        args = build_parser().parse_args(["tweaks", "preset", "apply", "reduced-motion"])
        self.assertEqual((args.preset_action, args.preset_id, args.yes), ("apply", "reduced-motion", False))
        args = build_parser().parse_args(["tweaks", "preset", "apply", "file-navigation", "--ids", "kde-single-click", "--yes", "--json"])
        self.assertEqual(args.ids, ["kde-single-click"])
        self.assertTrue(args.yes)
        self.assertTrue(args.json)

    @patch("cli.commands.tweaks_commands.detect_platform_profile", return_value=profile("gnome"))
    @patch("cli.commands.tweaks_commands.SystemActionRuntime")
    def test_unknown_preset_keeps_json_output_structured(self, _runtime_factory, _profile):
        from cli.commands.tweaks_commands import handle_tweaks

        args = SimpleNamespace(tweaks_action="preset", preset_action="preview", preset_id="unknown")
        payloads = []
        self.assertEqual(handle_tweaks(args, True, payloads.append, Mock()), 1)
        self.assertEqual(payloads[0]["schema"], "loofi.tweak-profile-result/v1")
        self.assertEqual(payloads[0]["status"], "failed")

    def test_apps_permissions_parser_requires_exact_installation(self):
        from cli.parser import build_parser

        args = build_parser().parse_args([
            "apps", "permissions", "app/org.example.App/x86_64/stable", "--installation", "work", "--json",
        ])
        self.assertEqual((args.apps_action, args.ref, args.installation),
                         ("permissions", "app/org.example.App/x86_64/stable", "work"))
        self.assertTrue(args.json)

    @patch("cli.commands.tweaks_commands.detect_platform_profile", return_value=profile("gnome"))
    @patch("cli.commands.tweaks_commands.SystemActionRuntime")
    @patch("core.tasks.tweak_profiles.review_profile")
    @patch("core.tasks.tweak_profiles.apply_profile")
    def test_preset_apply_without_yes_only_reviews(self, apply, review, runtime_factory, _profile):
        from cli.commands.tweaks_commands import handle_tweaks

        runtime = runtime_factory.return_value
        review.return_value = SimpleNamespace(entries=(), to_dict=lambda: {})
        args = SimpleNamespace(tweaks_action="preset", preset_action="apply", preset_id="reduced-motion", yes=False)
        self.assertEqual(handle_tweaks(args, False, Mock(), Mock()), 0)
        review.assert_called_once()
        apply.assert_not_called()
        self.assertTrue(runtime_factory.called)

    @patch("cli.commands.tweaks_commands.detect_platform_profile", return_value=profile("gnome"))
    @patch("cli.commands.tweaks_commands.SystemActionRuntime")
    @patch("cli.commands.tweaks_commands.inspect_one")
    def test_get_reuses_the_single_setting_inspection(self, inspect, runtime_factory, _profile):
        from cli.commands.tweaks_commands import handle_tweaks

        runtime = runtime_factory.return_value
        inspect.return_value = TweakState(BY_ID["gnome-battery"], "ready", value="true")
        args = SimpleNamespace(tweaks_action="get", tweak_id="gnome-battery")
        handle_tweaks(args, True, Mock(), Mock())

        inspect.assert_called_once_with("gnome-battery", profile("gnome"), runtime)


if __name__ == "__main__":
    unittest.main()
