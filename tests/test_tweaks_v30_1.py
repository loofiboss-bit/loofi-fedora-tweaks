"""State, policy, and presentation contracts for direct Fedora tweaks."""

from __future__ import annotations

import unittest
import os
from types import SimpleNamespace
from unittest.mock import Mock, patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from core.actions.catalog import ActionCatalog
from core.executor.action_result import ActionResult
from core.executor.command_policy import CommandValidationError, validate_command_vector
from core.execution_policy import classify_command, execution_allowed
from core.tasks.tweaks import BY_ID, TWEAKS, command_for, read_tweak, visible_tweaks
from PyQt6.QtCore import Qt
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QApplication, QMessageBox, QWidget
from ui.main_window_utility import MainWindowUtilityMixin
from ui.fix_workflow import FixWorkflowPage
from ui.tweaks_page import TweaksPage


def profile(desktop: str, backend: str = "dnf5") -> SimpleNamespace:
    return SimpleNamespace(
        is_fedora=True,
        desktop=SimpleNamespace(value=desktop),
        deployment_backend=SimpleNamespace(value=backend),
    )


READ_OUTPUTS = {
    "gnome-color": "'prefer-dark'\n",
    "gnome-animations": "true\n",
    "gnome-text-scale": "1.25\n",
    "gnome-battery": "false\n",
    "gnome-clock": "true\n",
    "kde-color": " * BreezeDark\n * CustomTheme (current color scheme)\n * BreezeLight\n",
    "kde-animation": "0.70710678\n",
    "power-profile": "balanced\n",
}


class FakeRuntime:
    def __init__(self, desktop: str, backend: str = "dnf5") -> None:
        self._profile = profile(desktop, backend)
        self.output = dict(READ_OUTPUTS)
        self.kde_color_current = "CustomTheme\n"
        self.fail = False
        self.calls: list[tuple[str, ...]] = []

    def platform_profile(self) -> object:
        return self._profile

    def execute_read_only(self, vector, *, action_id: str, timeout: int = 30) -> ActionResult:
        self.calls.append(tuple(vector))
        if self.fail:
            return ActionResult.fail("Tool missing", action_id=action_id)
        if tuple(vector) == ("powerprofilesctl", "list"):
            return ActionResult.ok("Listed", stdout="  performance:\n* balanced:\n  power-saver:\n", action_id=action_id)
        if tuple(vector) == ("kreadconfig6", "--file", "kdeglobals", "--group", "General", "--key", "ColorScheme"):
            return ActionResult.ok("Read", stdout=self.kde_color_current, action_id=action_id)
        tweak_id = action_id.removesuffix("-read")
        for tweak in TWEAKS:
            if tweak.action_id == tweak_id:
                return ActionResult.ok("Read", stdout=self.output[tweak.id], action_id=action_id)
        return ActionResult.fail("Unknown read", action_id=action_id)


class TestTweakCatalog(unittest.TestCase):
    def test_eight_controls_are_desktop_scoped_on_both_backends(self) -> None:
        self.assertEqual(len(TWEAKS), 8)
        for backend in ("dnf5", "rpm_ostree"):
            self.assertEqual(len(visible_tweaks(profile("gnome", backend))), 6)
            self.assertEqual(len(visible_tweaks(profile("kde", backend))), 3)
        self.assertEqual(visible_tweaks(profile("unknown")), ())
        self.assertEqual(visible_tweaks(profile("kde", "bootc")), ())

    def test_each_control_reads_and_accepts_only_curated_values(self) -> None:
        for desktop in ("gnome", "kde"):
            runtime = FakeRuntime(desktop)
            for tweak in visible_tweaks(runtime.platform_profile()):
                with self.subTest(tweak=tweak.id):
                    state = read_tweak(tweak, runtime.platform_profile(), runtime.execute_read_only)
                    self.assertEqual(state.status, "ready")
                    self.assertTrue(state.value)
                    self.assertTrue(state.choices)
                    for value, _label in state.choices:
                        validate_command_vector(command_for(tweak, value))
                    with self.assertRaises(ValueError):
                        command_for(tweak, "--not-a-value")

    def test_custom_kde_values_are_read_without_normalization_or_write(self) -> None:
        runtime = FakeRuntime("kde")
        scheme = read_tweak(BY_ID["kde-color"], runtime.platform_profile(), runtime.execute_read_only)
        speed = read_tweak(BY_ID["kde-animation"], runtime.platform_profile(), runtime.execute_read_only)
        self.assertEqual(scheme.value, "CustomTheme")
        self.assertIn(("CustomTheme", "CustomTheme"), scheme.choices)
        self.assertEqual(speed.value, "0.707107")
        self.assertNotIn((speed.value, "Custom"), speed.choices)
        self.assertTrue(all(call[0] != "kwriteconfig6" for call in runtime.calls))

    def test_uninstalled_kde_color_remains_visible_without_becoming_a_choice(self) -> None:
        runtime = FakeRuntime("kde")
        runtime.kde_color_current = "PrivateScheme\n"
        state = read_tweak(BY_ID["kde-color"], runtime.platform_profile(), runtime.execute_read_only)
        self.assertEqual(state.status, "ready")
        self.assertEqual(state.value, "PrivateScheme")
        self.assertNotIn(("PrivateScheme", "PrivateScheme"), state.choices)

    def test_installed_kde_scheme_with_spaces_is_selectable(self) -> None:
        runtime = FakeRuntime("kde")
        runtime.output["kde-color"] = " * BreezeDark\n * My Custom Theme (current color scheme)\n"
        runtime.kde_color_current = "My Custom Theme\n"
        state = read_tweak(BY_ID["kde-color"], runtime.platform_profile(), runtime.execute_read_only)
        self.assertIn(("My Custom Theme", "My Custom Theme"), state.choices)
        validate_command_vector(command_for(BY_ID["kde-color"], "My Custom Theme"))
        self.assertEqual(classify_command("plasma-apply-colorscheme", ["My Custom Theme"]), "session")

    def test_missing_tool_and_unknown_desktop_are_unavailable(self) -> None:
        runtime = FakeRuntime("gnome")
        runtime.fail = True
        state = read_tweak(BY_ID["gnome-color"], runtime.platform_profile(), runtime.execute_read_only)
        self.assertEqual(state.status, "unavailable")
        self.assertEqual(runtime.calls[0][0], "gsettings")
        other = read_tweak(BY_ID["kde-color"], runtime.platform_profile(), runtime.execute_read_only)
        self.assertEqual(other.status, "unavailable")
        self.assertEqual(len(runtime.calls), 1)

    def test_external_state_change_is_observed_and_preflight_detects_drift(self) -> None:
        runtime = FakeRuntime("gnome")
        tweak = BY_ID["gnome-animations"]
        first = read_tweak(tweak, runtime.platform_profile(), runtime.execute_read_only)
        runtime.output[tweak.id] = "false\n"
        second = read_tweak(tweak, runtime.platform_profile(), runtime.execute_read_only)
        self.assertNotEqual(first.value, second.value)
        definition = ActionCatalog().get(tweak.action_id)
        self.assertIsNotNone(definition)
        decision = definition.preflight_checker({"value": "true"}, runtime)
        self.assertTrue(decision.allowed)
        self.assertEqual(decision.facts["current"], "false")

    def test_verifier_requires_actual_readback(self) -> None:
        runtime = FakeRuntime("gnome")
        definition = ActionCatalog().get("set-gnome-battery")
        self.assertIsNotNone(definition)
        plan = SimpleNamespace(parameters={"value": "true"})
        failed = definition.verifier(SimpleNamespace(), plan, runtime)
        self.assertEqual(failed.state, "failed")
        runtime.output["gnome-battery"] = "true\n"
        success = definition.verifier(SimpleNamespace(), plan, runtime)
        self.assertEqual(success.state, "succeeded")

    def test_command_policy_rejects_unreviewed_settings_and_options(self) -> None:
        rejected = (
            ["gsettings", "set", "org.gnome.desktop.privacy", "remember-recent-files", "false"],
            ["gsettings", "set", "org.gnome.desktop.interface", "color-scheme", "unsafe"],
            ["kwriteconfig6", "--file", "kscreenlockerrc", "--group", "Daemon", "--key", "Autolock", "false"],
            ["plasma-apply-colorscheme", "--accent-color", "red"],
        )
        for vector in rejected:
            with self.subTest(vector=vector), self.assertRaises(CommandValidationError):
                validate_command_vector(vector)

    def test_exact_read_and_write_shapes_cross_execution_boundary(self) -> None:
        reads = (
            ["plasma-apply-colorscheme", "--list-schemes"],
            ["kreadconfig6", "--file", "kdeglobals", "--group", "KDE", "--key", "AnimationDurationFactor", "--default", "1"],
            ["kreadconfig6", "--file", "kdeglobals", "--group", "General", "--key", "ColorScheme"],
            ["powerprofilesctl", "get"],
            ["powerprofilesctl", "list"],
        )
        for vector in reads:
            with self.subTest(vector=vector):
                self.assertEqual(classify_command(vector[0], vector[1:]), "read_only")
                self.assertTrue(execution_allowed(vector[0], vector[1:]))
        for tweak in (BY_ID["kde-color"], BY_ID["kde-animation"]):
            vector = command_for(tweak, "BreezeDark" if tweak.id == "kde-color" else "0.5")
            self.assertEqual(classify_command(vector[0], vector[1:]), "session")
        animation = command_for(BY_ID["kde-animation"], "0.5")
        self.assertEqual(animation[:2], ["kwriteconfig6", "--notify"])
        validate_command_vector(animation)
        with self.assertRaises(CommandValidationError):
            validate_command_vector(animation[:1] + animation[2:])
        power = command_for(BY_ID["power-profile"], "balanced")
        self.assertFalse(execution_allowed(power[0], power[1:]))
        self.assertTrue(execution_allowed(power[0], power[1:], authority="action_center"))


class TestTweakPage(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def test_current_value_search_and_saved_feedback_require_refresh(self) -> None:
        page = TweaksPage(profile("gnome"))
        try:
            state = read_tweak(BY_ID["gnome-battery"], profile("gnome"), FakeRuntime("gnome").execute_read_only)
            page.set_states((state,))
            row, control = page._rows["gnome-battery"]
            self.assertEqual(control.currentData(), "false")
            page.set_outcome("gnome-battery", "true", SimpleNamespace(success=True, message="Verified"))
            self.assertNotEqual(row.feedback_label.property("feedbackKind"), "saved")
            page.set_states((SimpleNamespace(tweak=state.tweak, status="ready", value="true", choices=state.choices, message=""),))
            self.assertEqual(row.feedback_label.property("feedbackKind"), "saved")
            page.search_input.setText("battery")
            self.assertTrue(row.isVisibleTo(page))
            self.assertFalse(page._rows["gnome-clock"][0].isVisibleTo(page))
        finally:
            page.close()

    def test_failure_displays_actual_value_and_disables_uncertain_controls(self) -> None:
        page = TweaksPage(profile("gnome"))
        try:
            state = read_tweak(BY_ID["gnome-battery"], profile("gnome"), FakeRuntime("gnome").execute_read_only)
            page.set_states((state,))
            page.set_outcome("gnome-battery", "true", SimpleNamespace(success=False, message="Verification failed"))
            page.set_states((state,))
            row, control = page._rows["gnome-battery"]
            self.assertIn("Current value: false", row.feedback_label.text())
            page.set_error("Tool missing")
            self.assertFalse(control.isEnabled())
        finally:
            page.close()

    def test_search_and_refresh_are_keyboard_reachable(self) -> None:
        page = TweaksPage(profile("gnome"))
        try:
            page.show()
            self.app.processEvents()
            page.search_input.setFocus()
            QTest.keyClicks(page.search_input, "clock")
            self.assertFalse(page._rows["gnome-battery"][0].isVisibleTo(page))
            self.assertTrue(page._rows["gnome-clock"][0].isVisibleTo(page))
            QTest.keyClick(page.search_input, Qt.Key.Key_Tab)
            self.assertIs(self.app.focusWidget(), page.refresh_button)
        finally:
            page.close()

    def test_old_maintenance_task_ids_focus_health_actions(self) -> None:
        page = FixWorkflowPage()
        try:
            self.assertTrue(page.focus_task("tune:storage-trim"))
            self.assertTrue(page.focus_task("tune:package-cache"))
        finally:
            page.close()

    def test_health_requires_separate_no_rollback_acceptance(self) -> None:
        parent = QWidget()
        parent._run_reviewed_health_action = Mock()  # type: ignore[attr-defined]
        page = SimpleNamespace(set_health_notice=Mock())
        adapter = SimpleNamespace(stopped=SimpleNamespace(connect=Mock()))
        ticket = SimpleNamespace(
            blocked=False,
            plan=SimpleNamespace(action_id="journal-vacuum", risk_level="medium", rollback_supported=False, recovery_guidance="Review recovery guidance."),
            preview=("journalctl --vacuum-time=1d",),
        )
        try:
            with patch.object(QMessageBox, "exec", return_value=QMessageBox.StandardButton.Ok), patch.object(
                QMessageBox, "question", return_value=QMessageBox.StandardButton.No
            ) as question:
                MainWindowUtilityMixin._show_health_review(parent, page, ticket, adapter)
                question.assert_called_once()
                adapter.stopped.connect.assert_not_called()
            with patch.object(QMessageBox, "exec", return_value=QMessageBox.StandardButton.Ok), patch.object(
                QMessageBox, "question", return_value=QMessageBox.StandardButton.Yes
            ):
                MainWindowUtilityMixin._show_health_review(parent, page, ticket, adapter)
                callback = adapter.stopped.connect.call_args.args[0]
                callback()
                parent._run_reviewed_health_action.assert_called_once_with(page, ticket, True)  # type: ignore[attr-defined]
        finally:
            parent.close()


if __name__ == "__main__":
    unittest.main()
