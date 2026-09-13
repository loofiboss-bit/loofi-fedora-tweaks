"""CLI and authenticated read-only API contracts for Activity & Recovery."""

import argparse
import os
import sys
import unittest
from unittest.mock import MagicMock, patch
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "loofi-fedora-tweaks"))

from cli.parser import build_parser  # noqa: E402
from core.change_journal.models import (  # noqa: E402
    ChangeEvent,
    ChangeJournalSnapshot,
    ChangeSourceStatus,
    RecoveryCapability,
    stable_event_id,
)


def _event(recoverable=True):
    recovery = (
        RecoveryCapability(
            "action_center",
            "dnf5-history-undo",
            {"transaction_id": 42},
            "Prepare recovery",
        )
        if recoverable
        else RecoveryCapability(
            "manual_guidance",
            guidance="Review this change manually.",
        )
    )
    return ChangeEvent(
        stable_event_id("dnf5", "42"),
        "dnf5",
        100.0,
        "user",
        "DNF transaction 42 changed packages.",
        ("package-manager",),
        state="Ok",
        recovery=recovery,
    )


def _snapshot():
    return ChangeJournalSnapshot(
        (_event(),),
        (ChangeSourceStatus("dnf5", "available", 101.0),),
        101.0,
    )


class TestActivityParser(unittest.TestCase):
    def test_activity_commands_parse(self):
        listed = build_parser().parse_args(
            ["activity", "list", "--limit", "10", "--source", "dnf5"]
        )
        shown = build_parser().parse_args(
            ["activity", "show", _event().event_id]
        )

        self.assertEqual(listed.command, "activity")
        self.assertEqual(listed.activity_action, "list")
        self.assertEqual(listed.source, ["dnf5"])
        self.assertEqual(shown.activity_action, "show")


class TestActivityCli(unittest.TestCase):
    def setUp(self):
        import cli.main as cli_main

        cli_main._json_output = False

    @patch("core.change_journal.ChangeJournalService")
    @patch("cli.main._print")
    def test_list_reports_events_and_partial_sources(self, print_fn, service_cls):
        snapshot = _snapshot()
        partial = ChangeJournalSnapshot(
            snapshot.events,
            (
                *snapshot.sources,
                ChangeSourceStatus("fwupd", "unavailable", 101.0, "tool_unavailable"),
            ),
            snapshot.generated_at,
        )
        service_cls.return_value.snapshot.return_value = partial
        from cli.main import cmd_activity

        result = cmd_activity(
            argparse.Namespace(
                activity_action="list",
                limit=25,
                source=[],
                refresh=False,
            )
        )

        self.assertEqual(result, 0)
        rendered = " ".join(call.args[0] for call in print_fn.call_args_list)
        self.assertIn("DNF transaction 42", rendered)
        self.assertIn("Partial sources: fwupd", rendered)

    @patch("cli.main._emit_legacy_plans", return_value=0)
    @patch("cli.main._create_action_center_plan")
    @patch("core.change_journal.ChangeJournalService")
    def test_recover_creates_plan_but_never_applies(
        self,
        service_cls,
        create_plan,
        emit_plans,
    ):
        service_cls.return_value.get.return_value = _event()
        plan = MagicMock()
        create_plan.return_value = plan
        from cli.main import cmd_activity

        result = cmd_activity(
            argparse.Namespace(
                activity_action="recover",
                event_id=_event().event_id,
                refresh=True,
            )
        )

        self.assertEqual(result, 0)
        create_plan.assert_called_once_with(
            "dnf5-history-undo",
            {"transaction_id": 42},
        )
        emit_plans.assert_called_once_with([plan])

    @patch("core.change_journal.ChangeJournalService")
    @patch("cli.main._print")
    def test_manual_event_cannot_create_recovery_plan(self, print_fn, service_cls):
        service_cls.return_value.get.return_value = _event(recoverable=False)
        from cli.main import cmd_activity

        result = cmd_activity(
            argparse.Namespace(
                activity_action="recover",
                event_id=_event().event_id,
                refresh=False,
            )
        )

        self.assertEqual(result, 1)
        self.assertIn("manually", print_fn.call_args.args[0])


if __name__ == "__main__":
    unittest.main()
