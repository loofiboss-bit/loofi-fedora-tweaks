"""Portable profile validation and Action Center lifecycle regression tests."""
from __future__ import annotations

import json
import tempfile
import unittest
from types import SimpleNamespace
from dataclasses import FrozenInstanceError, replace
from pathlib import Path
from unittest.mock import Mock, patch

from core.actions.catalog import ActionCatalog
from core.actions.operation_controller import OperationController
from core.actions.orchestrator import ActionCenterOrchestrator
from core.actions.stores import ActionPlanStore, ActionRunStore
from core.executor.action_result import ActionResult
from core.executor.command_policy import validate_command_vector
from core.tasks.tweak_profiles import MAX_BYTES, TweakProfile, apply_profile, export_profile, load_profile, parse_profile, review_profile, save_profile
from core.tasks.tweaks import BY_ID, command_for, read_tweak
from core.tasks.tweak_history import restoration_for
from core.tweak_commands import gnome_schema
from test_tweaks_v30_2 import HistoryRuntime


class TestProfileFormat(unittest.TestCase):
    def setUp(self):
        self.profile = TweakProfile("Work settings", "gnome", (("gnome-battery", "true"),))

    def test_roundtrip_and_frozen_payload(self):
        self.assertEqual(parse_profile(json.dumps(self.profile.to_dict()).encode()), self.profile)
        with self.assertRaises(FrozenInstanceError):
            self.profile.desktop = "kde"

    def test_rejects_future_schema_duplicate_keys_ids_extra_fields_and_invalid_types(self):
        original = self.profile.to_dict()
        malformed = [
            {**original, "schema": "loofi.tweak-profile/v2"},
            {**original, "desktop": "unknown"},
            {**original, "name": "\nsecret"},
            {**original, "command": "echo hi"},
            {**original, "settings": original["settings"] * 2},
            {**original, "settings": [{"id": "gnome-battery", "value": True}]},
            {**original, "settings": [{"id": "gnome-battery", "value": "true", "before": "false"}]},
            {**original, "settings": [{"id": "../config", "value": "true"}]},
            {**original, "settings": {}},
        ]
        for payload in malformed:
            with self.subTest(payload=payload), self.assertRaises(ValueError):
                parse_profile(json.dumps(payload).encode())
        with self.assertRaises(ValueError):
            parse_profile(b'{"schema":"a","schema":"b"}')
        with self.assertRaises(ValueError):
            parse_profile(b" " * (MAX_BYTES + 1))
        with self.assertRaises(ValueError):
            parse_profile(b'\xff')

    @patch("core.tasks.tweak_profiles.atomic_write_json")
    def test_save_uses_atomic_writer_without_profile_backups(self, writer):
        path = Path("/profile.json")
        save_profile(path, self.profile)
        writer.assert_called_once_with(path, self.profile.to_dict(), keep_backup=False)

    @patch("pathlib.Path.open")
    def test_load_is_bounded(self, opening):
        opening.return_value.__enter__.return_value.read.return_value = json.dumps(self.profile.to_dict()).encode()
        self.assertEqual(load_profile(Path("/profile.json")), self.profile)
        opening.return_value.__enter__.return_value.read.assert_called_once_with(MAX_BYTES + 1)


@patch("core.tasks.tweaks.kde_capability_error", return_value="")
class TestProfileLifecycle(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        self.store = ActionRunStore(root / "runs.jsonl")
        self.runtime = HistoryRuntime(store=self.store)
        self.facade = Mock()
        self.facade.execute.side_effect = self.execute
        self.orchestrator = ActionCenterOrchestrator(
            catalog=ActionCatalog(), runtime=self.runtime, facade=self.facade,
            plan_store=ActionPlanStore(root / "plans.json"), run_store=self.store, lease_path=root / "lease")
        self.controller = OperationController(orchestrator=self.orchestrator, facade=self.facade)
        self.profile = TweakProfile("Daily", "gnome", (("gnome-battery", "true"), ("gnome-keyboard-repeat", "false")))

    def execute(self, command, **kwargs):
        self.assertEqual(kwargs["authority"], "action_center")
        tweak = next(t for t in BY_ID.values() if t.action_id == kwargs["action_id"] or f"restore-{t.id}" == kwargs["action_id"])
        self.runtime.output[tweak.id] = command[-1]
        return ActionResult.ok("Saved", exit_code=0)

    def test_review_is_read_only_and_immutable(self, _capability):
        review = review_profile(self.profile, self.controller)
        self.assertEqual([e.status for e in review.entries], ["ready", "ready"])
        self.assertEqual(self.orchestrator.plan_store.list_read_only(), [])
        self.facade.execute.assert_not_called()
        with self.assertRaises(FrozenInstanceError):
            review.name = "Other"

    def test_changed_rows_run_and_verify_sequentially_and_keep_restore_history(self, _capability):
        review = review_profile(self.profile, self.controller)
        result = apply_profile(review, self.controller, confirmed=True)
        self.assertTrue(result.success, result.message)
        self.assertEqual(self.facade.execute.call_count, 2)
        self.assertEqual(len(self.orchestrator.plan_store.list_read_only()), 2)
        runs = self.store.list_read_only(strict=True)
        self.assertTrue(all(run.state == "succeeded" for run in runs))
        state = read_tweak(BY_ID["gnome-battery"], self.runtime.platform_profile(), self.runtime.execute_read_only)
        offer = restoration_for(state.tweak, state, runs)
        self.assertEqual(offer.before, "false")
        ticket = self.controller.prepare("restore-gnome-battery", {"source_run_id": offer.source_run_id})
        outcome = self.controller.run(self.controller.confirm(ticket, confirmed=True))
        outcome = self.controller.verify(outcome)
        self.assertTrue(outcome.success)
        self.assertEqual(self.runtime.output["gnome-battery"], "false")

    def test_no_confirmation_no_plans_and_no_mutations(self, _capability):
        result = apply_profile(review_profile(self.profile, self.controller), self.controller, confirmed=False)
        self.assertEqual(result.status, "confirmation_required")
        self.facade.execute.assert_not_called()
        self.assertEqual(self.orchestrator.plan_store.list_read_only(), [])

    def test_current_value_drift_blocks_before_plan(self, _capability):
        review = review_profile(self.profile, self.controller)
        self.runtime.output["gnome-battery"] = "true"
        result = apply_profile(review, self.controller, confirmed=True)
        self.assertEqual(result.status, "blocked")
        self.assertEqual(result.entries[1].status, "not_started")
        self.facade.execute.assert_not_called()

    def test_second_setting_drift_stops_remaining_changes(self, _capability):
        review = review_profile(self.profile, self.controller)
        def run_and_drift(command, **kwargs):
            result = self.execute(command, **kwargs)
            self.runtime.output["gnome-keyboard-repeat"] = "false"
            return result
        self.facade.execute.side_effect = run_and_drift
        result = apply_profile(review, self.controller, confirmed=True)
        self.assertEqual(result.status, "blocked")
        self.assertEqual(result.entries[0].status, "succeeded")
        self.assertEqual(self.facade.execute.call_count, 1)

    def test_expiry_and_cancel_stop_before_execution(self, _capability):
        review = review_profile(self.profile, self.controller, clock=lambda: 0)
        self.assertEqual(apply_profile(review, self.controller, confirmed=True, clock=lambda: 1800).status, "blocked")
        review = review_profile(self.profile, self.controller)
        self.assertEqual(apply_profile(review, self.controller, confirmed=True, is_cancelled=lambda: True).status, "cancelled")
        self.facade.execute.assert_not_called()

    def test_action_definition_drift_blocks(self, _capability):
        review = review_profile(self.profile, self.controller)
        original = self.orchestrator.catalog.get("set-gnome-battery")
        self.orchestrator.catalog = ActionCatalog([replace(original, recovery_guidance="Changed policy")])
        result = apply_profile(review, self.controller, confirmed=True)
        self.assertEqual(result.status, "blocked")
        self.facade.execute.assert_not_called()

    @patch("core.tasks.tweak_profiles.activation_parameters", return_value={"source_run_id": "saved"})
    @patch("core.tasks.tweak_profiles.activate_verified_tweak")
    def test_session_verification_failure_marks_row_and_stops(self, activate, _parameters, _capability):
        activate.return_value = SimpleNamespace(session_verified=False, message="Session verification failed")
        result = apply_profile(review_profile(self.profile, self.controller), self.controller, confirmed=True)
        self.assertEqual(result.status, "verification_failed")
        self.assertEqual(result.entries[0].status, "verification_failed")
        self.assertEqual(result.entries[1].status, "not_started")
        self.assertEqual(self.facade.execute.call_count, 1)

    def test_verification_failure_stops_second_row(self, _capability):
        review = review_profile(self.profile, self.controller)
        self.facade.execute.side_effect = None
        self.facade.execute.return_value = ActionResult.ok("Reported success", exit_code=0)
        result = apply_profile(review, self.controller, confirmed=True)
        self.assertEqual(result.status, "verification_failed")
        self.assertEqual(self.facade.execute.call_count, 1)

    def test_wrong_desktop_and_invalid_unavailable_unchanged_targets(self, _capability):
        with self.assertRaises(ValueError):
            review_profile(TweakProfile("Other", "kde", (("kde-single-click", "true"),)), self.controller)
        data = TweakProfile("Mixed", "gnome", (("unknown-id", "x"), ("gnome-battery", "false"), ("gnome-animations", "garbage"), ("power-profile", "performance")))
        review = review_profile(data, self.controller)
        self.assertEqual([e.status for e in review.entries], ["unavailable", "unchanged", "invalid", "unavailable"])
        result = apply_profile(review, self.controller, confirmed=True)
        self.assertTrue(result.success)
        self.facade.execute.assert_not_called()
        self.assertEqual(apply_profile(review, self.controller, confirmed=True, selected_ids=["unknown-id"]).status, "blocked")

    def test_export_omits_custom_unavailable_and_system_settings(self, _capability):
        self.runtime.output["gnome-text-scale"] = "1.23456789"
        exported = export_profile("Portable", self.runtime.platform_profile(), self.runtime, ["gnome-battery", "gnome-text-scale", "power-profile", "unknown-id"])
        self.assertEqual(exported.profile.settings, (("gnome-battery", "false"),))
        self.assertEqual({key for key, _reason in exported.omitted}, {"gnome-text-scale", "power-profile", "unknown-id"})
        self.facade.execute.assert_not_called()

    def test_atomic_fedora_uses_same_user_setting_authority(self, _capability):
        self.runtime._profile.deployment_backend.value = "rpm_ostree"
        result = apply_profile(review_profile(self.profile, self.controller), self.controller, confirmed=True)
        self.assertTrue(result.success, result.message)
        self.assertEqual(self.facade.execute.call_count, 2)

    def test_cancellation_between_settings_preserves_completed_history(self, _capability):
        cancelled = []
        review = review_profile(self.profile, self.controller)
        def execute_and_cancel(command, **kwargs):
            result = self.execute(command, **kwargs)
            cancelled.append(True)
            return result
        self.facade.execute.side_effect = execute_and_cancel
        result = apply_profile(review, self.controller, confirmed=True, is_cancelled=lambda: bool(cancelled))
        self.assertEqual(result.status, "cancelled")
        self.assertEqual(result.entries[0].status, "succeeded")
        self.assertEqual(self.facade.execute.call_count, 1)
        self.assertEqual(self.store.list_read_only(strict=True)[0].state, "succeeded")

    @patch("core.actions.operation_controller.OperationController.prepare")
    def test_drift_during_plan_preparation_does_not_execute(self, prepare, _capability):
        from core.actions.operation_controller import OperationTicket
        from core.actions.contracts import PolicyDecision
        review = review_profile(self.profile, self.controller)
        ticket = Mock(spec=OperationTicket)
        ticket.blocked = False
        ticket.plan = Mock()
        ticket.plan.preview = list(review.entries[0].command)
        ticket.plan.policy_decision = PolicyDecision(True, "ready", "Ready", facts={"current": "true", "requested": "true"})
        prepare.return_value = ticket
        result = apply_profile(review, self.controller, confirmed=True)
        self.assertEqual(result.status, "blocked")
        self.facade.execute.assert_not_called()

    def test_new_controls_use_closed_gnome_vectors(self, _capability):
        for key, schema in (("gnome-mouse-left-handed", "org.gnome.desktop.peripherals.mouse"), ("gnome-mouse-acceleration", "org.gnome.desktop.peripherals.mouse"), ("gnome-keyboard-repeat", "org.gnome.desktop.peripherals.keyboard")):
            self.assertEqual(gnome_schema(key), schema)
            for value, _label in BY_ID[key].choices:
                validate_command_vector(command_for(BY_ID[key], value))
            with self.assertRaises(ValueError):
                command_for(BY_ID[key], "unsupported")


class TestProfileInterfaces(unittest.TestCase):
    def test_cli_profile_parser_exposes_file_selection_and_explicit_confirmation(self):
        import argparse
        from cli.parser_domains.tweaks import register_tweaks_command
        parser = argparse.ArgumentParser()
        register_tweaks_command(parser.add_subparsers(dest="command"))
        args = parser.parse_args(["tweaks", "profile", "apply", "settings.json", "--ids", "gnome-battery", "--yes", "--json"])
        self.assertEqual(args.profile_action, "apply")
        self.assertTrue(args.yes)
        self.assertTrue(args.json)
        self.assertEqual(args.ids, ["gnome-battery"])
        args = parser.parse_args(["tweaks", "profile", "apply", "settings.json"])
        self.assertFalse(args.yes)

    @patch("core.tasks.tweak_profiles.load_profile")
    @patch("core.tasks.tweak_profiles.review_profile")
    @patch("core.tasks.tweak_profiles.apply_profile")
    @patch("cli.commands.tweaks_commands.OperationController")
    @patch("cli.commands.tweaks_commands.ActionCenterOrchestrator")
    def test_cli_preview_and_unconfirmed_apply_never_execute(self, orchestrator, controller, apply, review, load):
        from types import SimpleNamespace
        from cli.commands.tweaks_commands import _handle_profile
        from core.tasks.tweak_profiles import ProfileReview
        review.return_value = ProfileReview("Daily", "gnome", (), 1)
        output = Mock()
        runtime = Mock()
        for operation, dry_run, yes in (("preview", False, False), ("apply", False, False), ("apply", True, True)):
            code = _handle_profile(SimpleNamespace(profile_action=operation, path="/profile.json", yes=yes), True, output, Mock(), object(), runtime, dry_run=dry_run)
            self.assertEqual(code, 0)
            self.assertEqual(output.call_args.args[0]["schema"], "loofi.tweak-profile-review/v1")
        apply.assert_not_called()

    @patch("core.tasks.tweak_profiles.load_profile")
    @patch("core.tasks.tweak_profiles.review_profile")
    @patch("core.tasks.tweak_profiles.apply_profile")
    @patch("cli.commands.tweaks_commands.OperationController")
    @patch("cli.commands.tweaks_commands.ActionCenterOrchestrator")
    def test_cli_confirmed_apply_uses_shared_result_schema(self, orchestrator, controller, apply, review, load):
        from types import SimpleNamespace
        from cli.commands.tweaks_commands import _handle_profile
        from core.tasks.tweak_profiles import ProfileResult
        apply.return_value = ProfileResult("succeeded", (), "Verified")
        output = Mock()
        args = SimpleNamespace(profile_action="apply", path="/profile.json", yes=True, ids=["gnome-battery"])
        self.assertEqual(_handle_profile(args, True, output, Mock(), object(), Mock(), dry_run=False), 0)
        apply.assert_called_once_with(review.return_value, controller.return_value, confirmed=True, selected_ids=["gnome-battery"])
        self.assertEqual(output.call_args.args[0], apply.return_value.to_dict())

    def test_gui_review_only_selects_available_changed_rows(self):
        from PyQt6.QtCore import Qt
        from PyQt6.QtWidgets import QApplication
        from ui.tweak_profiles import ProfileSelectionDialog
        app = QApplication.instance() or QApplication([])
        dialog = ProfileSelectionDialog("Review", "Select settings", [("ready", "Old → New", True), ("same", "Already matches", False), ("unknown", "Unavailable", False)])
        self.assertEqual(dialog.selected_ids(), ("ready",))
        dialog.entries.item(0).setCheckState(Qt.CheckState.Unchecked)
        self.assertEqual(dialog.selected_ids(), ())
        self.assertEqual(dialog.entries.accessibleName(), "Profile settings")
        dialog.deleteLater()
        app.processEvents()
