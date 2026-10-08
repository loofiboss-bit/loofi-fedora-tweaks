"""Rootless contracts for independently verified pointer writes and notification."""

from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from core.actions import tweaks as actions
from core.actions.contracts import PolicyDecision
from core.actions.operation_controller import OperationOutcome
from core.actions.tweak_operations import (
    CURSOR_NOTIFICATION_ACTION_ID,
    cursor_notification_parameters,
    cursor_notification_result,
    notify_verified_cursor_change,
)
from core.tasks.tweaks import BY_ID, TweakState
from core.tweak_commands import CURSOR_NOTIFY


def _source(tweak_id="kde-cursor-theme", *, restoring=False, value="CustomPointer", before="Breeze", run_id="source-1"):
    record = {"version": 1, "kind": "restore" if restoring else "change", "tweak_id": tweak_id, "before": before, "after": value}
    parameters = {"source_run_id": "original-1"} if restoring else {"value": value}
    if restoring:
        record["source_run_id"] = "original-1"
    return SimpleNamespace(
        run_id=run_id, action_id=f"{'restore' if restoring else 'set'}-{tweak_id}",
        affected_resources=(f"tweak:{tweak_id}",), parameters=parameters, state="succeeded",
        execution_result={"success": True}, verification_result={"success": True, "data": {"tweak_change": record}},
    )


def _plan(tweak_id="kde-cursor-theme", value="CustomPointer", counterpart="32", restoring=False):
    other = "kde-cursor-size" if tweak_id == "kde-cursor-theme" else "kde-cursor-theme"
    return SimpleNamespace(
        parameters={"source_run_id": "source-1"} if restoring else {"value": value},
        policy_decision=PolicyDecision(True, "ready", "Ready", facts={
            "current": "Breeze" if tweak_id == "kde-cursor-theme" else "32", "requested": value,
            "counterpart_id": other, "counterpart_value": counterpart,
        }),
    )


class TestCursorWriteVerification(unittest.TestCase):
    @patch("core.actions.tweaks.read_cursor_config")
    @patch("core.actions.tweaks.read_tweak")
    def test_preflight_binds_both_settings_and_rejects_racing_read(self, read, pair):
        tweak = BY_ID["kde-cursor-theme"]
        read.return_value = TweakState(tweak, "ready", "Breeze", (("Breeze", "Breeze"), ("CustomPointer", "My pointer")))
        pair.return_value = ({"kde-cursor-theme": "Breeze", "kde-cursor-size": "35"}, "")
        accepted = actions._preflight(tweak, {"value": "CustomPointer"}, Mock())
        self.assertTrue(accepted.allowed)
        self.assertEqual(accepted.facts["counterpart_value"], "35")
        pair.return_value = ({"kde-cursor-theme": "Changed", "kde-cursor-size": "35"}, "")
        self.assertFalse(actions._preflight(tweak, {"value": "CustomPointer"}, Mock()).allowed)

    @patch("core.actions.tweaks.read_cursor_config")
    @patch("core.actions.tweaks.read_tweak")
    def test_both_setting_orders_preserve_counterpart(self, read, pair):
        for tweak_id, value, counterpart in (("kde-cursor-theme", "CustomPointer", "32"), ("kde-cursor-size", "48", "CustomPointer")):
            tweak = BY_ID[tweak_id]
            read.return_value = TweakState(tweak, "ready", value, ((value, value),))
            other = "kde-cursor-size" if tweak_id == "kde-cursor-theme" else "kde-cursor-theme"
            pair.return_value = ({tweak_id: value, other: counterpart}, "")
            run = SimpleNamespace(action_id=tweak.action_id)
            plan = _plan(tweak_id, value, counterpart)
            verified = actions._verify(tweak, run, plan, Mock())
            self.assertEqual(verified.state, "succeeded")
            self.assertEqual(verified.data["tweak_change"]["after"], value)
            pair.return_value = ({tweak_id: value, other: "Unexpected"}, "")
            self.assertEqual(actions._verify(tweak, run, plan, Mock()).state, "failed")

    @patch("core.actions.tweaks.read_cursor_config")
    @patch("core.actions.tweaks.read_tweak")
    def test_pair_read_failure_and_own_drift_fail_verification(self, read, pair):
        tweak = BY_ID["kde-cursor-theme"]
        read.return_value = TweakState(tweak, "ready", "CustomPointer", (("CustomPointer", "Custom"),))
        for values, error in (({}, "Read failed"), ({"kde-cursor-theme": "Breeze", "kde-cursor-size": "32"}, "")):
            pair.return_value = (values, error)
            self.assertEqual(actions._verify(tweak, SimpleNamespace(action_id=tweak.action_id), _plan(), Mock()).state, "failed")

    @patch("core.actions.tweaks.read_cursor_config")
    @patch("core.actions.tweaks.read_tweak")
    def test_custom_numeric_restoration_is_exact(self, read, pair):
        tweak = BY_ID["kde-cursor-size"]
        read.return_value = TweakState(tweak, "ready", "35", tweak.choices)
        pair.return_value = ({"kde-cursor-theme": "CustomPointer", "kde-cursor-size": "35"}, "")
        run = SimpleNamespace(action_id="restore-kde-cursor-size")
        result = actions._verify(tweak, run, _plan(tweak.id, "35", "CustomPointer", restoring=True), Mock())
        self.assertEqual(result.state, "succeeded")
        self.assertEqual(result.data["tweak_change"]["after"], "35")
        self.assertEqual(result.data["tweak_change"]["source_run_id"], "source-1")


class TestCursorNotification(unittest.TestCase):
    @patch("core.actions.tweaks.read_tweak")
    @patch("core.actions.tweaks.read_tweak_runs")
    def test_latest_source_is_bound_per_setting_and_saved_drift_is_rejected(self, history, read):
        source = _source()
        history.return_value = ([source, _source("kde-cursor-size", value="48", before="32", run_id="size-2")], "")
        read.return_value = TweakState(BY_ID["kde-cursor-theme"], "ready", "CustomPointer", (("CustomPointer", "Custom"),))
        params = {"tweak_id": "kde-cursor-theme", "source_run_id": "source-1"}
        self.assertEqual(actions._render_cursor_notification(params, Mock()), list(CURSOR_NOTIFY))
        read.return_value = TweakState(BY_ID["kde-cursor-theme"], "ready", "Breeze", (("Breeze", "Breeze"),))
        with self.assertRaises(ValueError):
            actions._cursor_notification_source(params, Mock())
        history.return_value = ([source, _source(run_id="later")], "")
        with self.assertRaises(ValueError):
            actions._cursor_notification_source(params, Mock())

    @patch("core.actions.tweaks.read_tweak")
    @patch("core.actions.tweaks.read_tweak_runs")
    def test_custom_size_restore_can_notify_but_invalid_evidence_cannot(self, history, read):
        source = _source("kde-cursor-size", restoring=True, value="0", before="48")
        history.return_value = ([source], "")
        read.return_value = TweakState(BY_ID["kde-cursor-size"], "ready", "0", BY_ID["kde-cursor-size"].choices)
        params = {"tweak_id": "kde-cursor-size", "source_run_id": "source-1"}
        self.assertEqual(actions._cursor_notification_source(params, Mock())[1], "0")
        source.verification_result["data"]["tweak_change"]["source_run_id"] = "different"
        with self.assertRaises(ValueError):
            actions._cursor_notification_source(params, Mock())

    @patch("core.actions.tweaks._cursor_notification_source")
    def test_signal_verifies_delivery_only_and_requires_successful_execution(self, source):
        source.return_value = (BY_ID["kde-cursor-theme"], "CustomPointer")
        plan = SimpleNamespace(parameters={"tweak_id": "kde-cursor-theme", "source_run_id": "source-1"})
        result = actions._verify_cursor_notification(SimpleNamespace(execution_result={"success": True}), plan, Mock())
        self.assertTrue(result.data["notification_sent"])
        self.assertNotIn("session_verified", result.data)
        self.assertIn("Visual effect is unverified", result.message)
        self.assertEqual(actions._verify_cursor_notification(SimpleNamespace(execution_result={"success": False}), plan, Mock()).state, "failed")

    def test_resources_are_independent_and_notification_does_not_claim_setting(self):
        definitions = {definition.id: definition for definition in actions.tweak_action_definitions()}
        self.assertEqual(definitions[CURSOR_NOTIFICATION_ACTION_ID].affected_resources, ("session:cursor-notification",))
        for tweak_id in ("kde-cursor-theme", "kde-cursor-size"):
            self.assertEqual(definitions[f"set-{tweak_id}"].affected_resources, (f"tweak:{tweak_id}",))

    def test_follow_up_failure_retains_saved_success_and_success_requires_evidence(self):
        source = OperationOutcome("set-kde-cursor-theme", "succeeded", "verify", "Saved", run_id="source-1")
        self.assertEqual(cursor_notification_parameters(source), {"tweak_id": "kde-cursor-theme", "source_run_id": "source-1"})
        failed = OperationOutcome(CURSOR_NOTIFICATION_ACTION_ID, "failed", "run", "DBus failed")
        result = cursor_notification_result(source, failed)
        self.assertTrue(result.saved_verified)
        self.assertFalse(result.notification_sent)
        unsupported = OperationOutcome("set-kde-color", "succeeded", "verify", "Saved", run_id="color-1")
        self.assertIsNone(cursor_notification_parameters(unsupported))
        run = SimpleNamespace(verification_result={"success": True, "data": {"notification_sent": True}})
        sent = OperationOutcome(CURSOR_NOTIFICATION_ACTION_ID, "succeeded", "verify", "Sent", run=run)
        self.assertTrue(cursor_notification_result(source, sent).notification_sent)
        run.verification_result["data"] = {"session_verified": True}
        self.assertFalse(cursor_notification_result(source, sent).notification_sent)

    def test_adapter_preserves_saved_result_when_prepare_blocks(self):
        source = OperationOutcome("restore-kde-cursor-size", "succeeded", "verify", "Saved", run_id="restore-1")
        controller = Mock()
        controller.prepare.return_value = SimpleNamespace(blocked=True, plan=SimpleNamespace(policy_decision=PolicyDecision(False, "missing", "Tool missing")))
        result = notify_verified_cursor_change(controller, source)
        self.assertTrue(result.saved_verified)
        self.assertFalse(result.notification_sent)
        controller.confirm.assert_not_called()
