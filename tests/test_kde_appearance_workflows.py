"""Rootless integration of pointer profiles, notification, and durable restoration."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch
from xml.etree.ElementTree import fromstring

from core.actions.catalog import ActionCatalog
from core.actions.operation_controller import OperationController
from core.actions.orchestrator import ActionCenterOrchestrator
from core.actions.stores import ActionPlanStore, ActionRunStore
from core.actions.tweak_operations import notify_verified_cursor_change
from core.executor.action_result import ActionResult
from core.tasks.tweak_history import restoration_for
from core.tasks.tweak_profiles import TweakProfile, apply_profile, review_profile
from core.tasks.tweaks import BY_ID, _CURSOR_SCHEMA, read_tweak
from core.tweak_commands import CURSOR_NOTIFY, kde_read_vector


_SCHEMA = fromstring('<kcfg><group name="Mouse"><entry name="cursorTheme" type="String"><default>Breeze</default></entry>'
                     '<entry name="cursorSize" type="Int"><default>24</default></entry></group></kcfg>')


def _capability(_tweak_id, *, schema_cache=None):
    if schema_cache is not None:
        schema_cache[_CURSOR_SCHEMA] = (_SCHEMA, "")
    return ""


class AppearanceRuntime:
    def __init__(self, store):
        self.store = store
        self.values = {"kde-cursor-theme": "Breeze", "kde-cursor-size": "35", "kde-plasma-style": "breeze"}
        self.themes = {"Breeze", "CustomPointer"}
        self.notify_failure = False
        self.calls = []
        self.facade = Mock()
        self.facade.execute.side_effect = self.execute

    def platform_profile(self):
        return SimpleNamespace(is_fedora=True, desktop=SimpleNamespace(value="kde"), deployment_backend=SimpleNamespace(value="dnf5"),
                               session_type=SimpleNamespace(value="wayland"))

    def is_atomic(self):
        return False

    def fedora_version(self):
        return "44"

    def boot_id(self):
        return "appearance-test-boot"

    def package_manager(self):
        return "dnf5"

    def tweak_runs(self):
        return self.store.list_read_only(strict=True)

    def execute_read_only(self, vector, **kwargs):
        for tweak_id in ("kde-cursor-theme", "kde-cursor-size", "kde-plasma-style"):
            if list(vector) == kde_read_vector(tweak_id):
                return ActionResult.ok("Read", stdout=self.values[tweak_id], action_id=kwargs["action_id"])
        if list(vector) == ["plasma-apply-cursortheme", "--list-themes"]:
            output = "You have the following cursor themes on your system:\n" + "\n".join(f" * {theme} [{theme}]" for theme in sorted(self.themes))
            return ActionResult.ok("Listed", stdout=output, action_id=kwargs["action_id"])
        if list(vector) == ["plasma-apply-desktoptheme", "--list-themes"]:
            return ActionResult.ok("Listed", stdout="You have the following Plasma themes on your system:\n * breeze\n * custom\n")
        return ActionResult.fail("Unexpected read")

    def execute(self, command, **kwargs):
        self.calls.append((kwargs["action_id"], tuple(command)))
        if tuple(command) == CURSOR_NOTIFY:
            return ActionResult.fail("DBus unavailable", exit_code=1) if self.notify_failure else ActionResult.ok("Signal sent", exit_code=0)
        self.assert_authority(kwargs)
        key = kwargs["action_id"].removeprefix("set-").removeprefix("restore-")
        self.values[key] = command[-1]
        return ActionResult.ok("Saved", exit_code=0)

    @staticmethod
    def assert_authority(kwargs):
        if kwargs.get("authority") != "action_center":
            raise AssertionError("All writes must use Action Center authority")


@patch("core.tasks.tweaks.kde_capability_error", side_effect=_capability)
@patch("core.actions.tweaks.shutil.which", return_value="/usr/bin/dbus-send")
@patch("core.tasks.tweaks._plasma_style_label", side_effect=lambda identifier: identifier)
class TestAppearanceWorkflows(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        self.store = ActionRunStore(root / "runs.jsonl")
        self.runtime = AppearanceRuntime(self.store)
        orchestrator = ActionCenterOrchestrator(
            catalog=ActionCatalog(), runtime=self.runtime, facade=self.runtime.facade,
            plan_store=ActionPlanStore(root / "plans.json"), run_store=self.store, lease_path=root / "lease",
        )
        self.controller = OperationController(orchestrator=orchestrator, facade=self.runtime.facade)

    def apply(self, action_id, parameters):
        ticket = self.controller.prepare(action_id, parameters)
        self.assertFalse(ticket.blocked, ticket.plan.policy_decision.explanation)
        outcome = self.controller.confirm(ticket, confirmed=True)
        self.assertEqual(outcome.status, "prepared", outcome.message)
        outcome = self.controller.run(outcome)
        if outcome.status == "verifying":
            outcome = self.controller.verify(outcome)
        self.assertTrue(outcome.success, outcome.message)
        return outcome

    def offer(self, tweak_id):
        state = read_tweak(BY_ID[tweak_id], self.runtime.platform_profile(), self.runtime.execute_read_only)
        return restoration_for(state.tweak, state, self.store.list_read_only(strict=True))

    def test_profile_theme_then_size_preserves_approved_commands(self, *_mocks):
        self.check_profile(("kde-cursor-theme", "kde-cursor-size"))

    def test_profile_size_then_theme_preserves_approved_commands(self, *_mocks):
        self.check_profile(("kde-cursor-size", "kde-cursor-theme"))

    def check_profile(self, order):
        values = {"kde-cursor-theme": "CustomPointer", "kde-cursor-size": "48"}
        profile = TweakProfile("Appearance", "kde", tuple((key, values[key]) for key in order))
        review = review_profile(profile, self.controller)
        self.assertEqual([entry.status for entry in review.entries], ["ready", "ready"])
        result = apply_profile(review, self.controller, confirmed=True)
        self.assertTrue(result.success, result.message)
        self.assertEqual([entry.status for entry in result.entries], ["succeeded", "succeeded"])
        self.assertEqual(self.runtime.values["kde-cursor-theme"], "CustomPointer")
        self.assertEqual(self.runtime.values["kde-cursor-size"], "48")
        writes = [vector for action, vector in self.runtime.calls if action.startswith("set-")]
        self.assertEqual(writes, [entry.command for entry in review.entries])
        runs = self.store.list_read_only(strict=True)
        self.assertEqual(len(runs), 4)
        self.assertTrue(all(run.state == "succeeded" for run in runs))
        notifications = [run for run in runs if run.action_id == "notify-kde-cursor-change"]
        self.assertTrue(all(run.verification_result["data"]["notification_sent"] is True for run in notifications))
        self.assertTrue(all("session_verified" not in run.verification_result["data"] for run in notifications))

    def test_notification_failure_stops_profile_but_saved_write_is_restorable(self, *_mocks):
        self.runtime.notify_failure = True
        profile = TweakProfile("Appearance", "kde", (("kde-cursor-theme", "CustomPointer"), ("kde-cursor-size", "48")))
        result = apply_profile(review_profile(profile, self.controller), self.controller, confirmed=True)
        self.assertEqual(result.status, "failed")
        self.assertEqual(result.entries[1].status, "not_started")
        runs = self.store.list_read_only(strict=True)
        self.assertEqual([run.state for run in runs], ["succeeded", "failed"])
        self.assertTrue(self.offer("kde-cursor-theme").source_run_id)
        self.assertEqual(self.runtime.values["kde-cursor-size"], "35")

    def test_later_size_change_does_not_block_theme_restore(self, *_mocks):
        changed = self.apply("set-kde-cursor-theme", {"value": "CustomPointer"})
        self.assertTrue(notify_verified_cursor_change(self.controller, changed).notification_sent)
        size = self.apply("set-kde-cursor-size", {"value": "48"})
        self.assertTrue(notify_verified_cursor_change(self.controller, size).notification_sent)
        offer = self.offer("kde-cursor-theme")
        self.assertEqual(offer.source_run_id, changed.run_id)
        restored = self.apply("restore-kde-cursor-theme", {"source_run_id": offer.source_run_id})
        self.assertTrue(notify_verified_cursor_change(self.controller, restored).notification_sent)
        self.assertEqual(self.runtime.values["kde-cursor-theme"], "Breeze")
        self.assertEqual(self.runtime.values["kde-cursor-size"], "48")

    def test_custom_numeric_size_restores_exact_value_and_notifies(self, *_mocks):
        changed = self.apply("set-kde-cursor-size", {"value": "48"})
        self.assertTrue(notify_verified_cursor_change(self.controller, changed).notification_sent)
        offer = self.offer("kde-cursor-size")
        self.assertEqual(offer.before, "35")
        restored = self.apply("restore-kde-cursor-size", {"source_run_id": offer.source_run_id})
        self.assertTrue(notify_verified_cursor_change(self.controller, restored).notification_sent)
        self.assertEqual(self.runtime.values["kde-cursor-size"], "35")
        self.assertEqual(self.runtime.values["kde-cursor-theme"], "Breeze")

    def test_removed_previous_theme_blocks_restore_without_write(self, *_mocks):
        changed = self.apply("set-kde-cursor-theme", {"value": "CustomPointer"})
        self.runtime.themes.remove("Breeze")
        self.assertFalse(self.offer("kde-cursor-theme").source_run_id)
        before = len(self.runtime.calls)
        ticket = self.controller.prepare("restore-kde-cursor-theme", {"source_run_id": changed.run_id})
        self.assertTrue(ticket.blocked)
        self.assertEqual(len(self.runtime.calls), before)

    @patch("cli.commands.tweaks_commands.CommandFacade")
    @patch("cli.commands.tweaks_commands.ActionCenterOrchestrator")
    @patch("cli.commands.tweaks_commands.OperationController")
    @patch("cli.commands.tweaks_commands.SystemActionRuntime")
    @patch("cli.commands.tweaks_commands.detect_platform_profile")
    def test_cli_set_and_restore_emit_notification_evidence(self, detected, runtime_class, controller_class, *_mocks):
        from cli.commands.tweaks_commands import handle_tweaks

        detected.return_value = self.runtime.platform_profile()
        runtime_class.return_value = self.runtime
        controller_class.return_value = self.controller
        payloads = []
        printer = Mock()
        for action in ("set", "restore"):
            args = SimpleNamespace(tweaks_action=action, tweak_id="kde-cursor-size", value="48", yes=True)
            self.assertEqual(handle_tweaks(args, True, payloads.append, printer), 0)
            self.assertTrue(payloads[-1]["saved_verified"])
            self.assertTrue(payloads[-1]["notification_sent"])
            self.assertNotIn("session_verified", payloads[-1])
            self.assertIn("Visual effect is unverified", payloads[-1]["message"])
        self.assertEqual(self.runtime.values["kde-cursor-size"], "35")

    @patch("cli.commands.tweaks_commands.CommandFacade")
    @patch("cli.commands.tweaks_commands.ActionCenterOrchestrator")
    @patch("cli.commands.tweaks_commands.OperationController")
    @patch("cli.commands.tweaks_commands.SystemActionRuntime")
    @patch("cli.commands.tweaks_commands.detect_platform_profile")
    def test_cli_notification_failure_reports_saved_verified_with_nonzero_exit(self, detected, runtime_class, controller_class, *_mocks):
        from cli.commands.tweaks_commands import handle_tweaks

        detected.return_value = self.runtime.platform_profile()
        runtime_class.return_value = self.runtime
        controller_class.return_value = self.controller
        self.runtime.notify_failure = True
        payloads = []
        args = SimpleNamespace(tweaks_action="set", tweak_id="kde-cursor-theme", value="CustomPointer", yes=True)
        self.assertEqual(handle_tweaks(args, True, payloads.append, Mock()), 1)
        self.assertTrue(payloads[-1]["saved_verified"])
        self.assertFalse(payloads[-1]["notification_sent"])
        self.assertTrue(self.offer("kde-cursor-theme").source_run_id)
