"""CLI contracts for canonical System Check commands and health aliases."""

from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from cli.main import cmd_health
from cli.parser import build_parser
from core.system_check.presentation import (
    FindingView,
    HistoryView,
    SystemCheckPageState,
)


def _state() -> SystemCheckPageState:
    return SystemCheckPageState(
        latest_check_id="check-1",
        latest_state="completed",
        latest_completed_at=20.0,
        atomic=False,
        findings=(
            FindingView(
                "package-state",
                "fingerprint-1",
                "packages",
                "attention",
                "Package state needs review",
                "Review the saved signal.",
                "fresh",
                "maintenance:updates",
                "",
                (),
            ),
        ),
        history=(
            HistoryView(20.0, "system-check", "completed", "check-1", 1, 1, 0, 0),
        ),
        metrics=(),
        unavailable_sources=(),
        snapshot_error="",
        metric_error="",
    )


class TestSystemCheckParser(unittest.TestCase):
    def test_new_and_compatibility_health_commands_parse(self):
        parser = build_parser()
        for command in (
            "check",
            "findings",
            "history",
            "comparison",
            "snapshot",
            "timeline",
        ):
            with self.subTest(command=command):
                args = parser.parse_args(["health", command])
                self.assertEqual(args.command, "health")
                self.assertEqual(args.health_action, command)

    def test_global_json_applies_to_system_check_commands(self):
        args = build_parser().parse_args(["--json", "health", "findings"])
        self.assertTrue(args.json)


class TestSystemCheckCli(unittest.TestCase):
    @patch("cli.main._print")
    @patch("cli.main._output_json")
    @patch("cli.main._json_output", True)
    @patch("core.system_check.presentation.SystemCheckPresentationService")
    def test_findings_json_has_stable_versioned_envelope(
        self,
        service_cls,
        output_json,
        print_fn,
    ):
        service_cls.return_value.load.return_value = _state()

        self.assertEqual(cmd_health(SimpleNamespace(health_action="findings")), 0)

        payload = output_json.call_args.args[0]
        self.assertEqual(payload["schema_id"], "loofi.system-check")
        self.assertEqual(payload["schema_version"], 1)
        self.assertEqual(payload["command"], "findings")
        self.assertEqual(payload["data"]["findings"][0]["finding_id"], "package-state")
        print_fn.assert_not_called()

    @patch("cli.main._output_json")
    @patch("cli.main._json_output", True)
    @patch("core.system_check.presentation.SystemCheckPresentationService")
    def test_history_limit_is_forwarded(self, service_cls, output_json):
        service_cls.return_value.load.return_value = _state()

        self.assertEqual(
            cmd_health(SimpleNamespace(health_action="history", limit=7)),
            0,
        )

        service_cls.return_value.load.assert_called_once_with(history_limit=7)
        self.assertEqual(output_json.call_args.args[0]["command"], "history")

    @patch("cli.main._output_json")
    @patch("cli.main._json_output", True)
    @patch("core.system_check.service.SystemCheckService")
    def test_check_runs_only_the_system_check_service(self, service_cls, output_json):
        result = MagicMock(state="completed", findings=(), source_errors=())
        result.to_dict.return_value = {"schema_version": 1, "state": "completed"}
        service_cls.return_value.run.return_value = result

        self.assertEqual(cmd_health(SimpleNamespace(health_action="check")), 0)

        service_cls.return_value.run.assert_called_once_with()
        payload = output_json.call_args.args[0]
        self.assertEqual(payload["command"], "check")
        self.assertEqual(payload["data"]["result"]["state"], "completed")

    @patch("cli.main._output_json")
    @patch("cli.main._json_output", True)
    @patch("core.system_check.comparison.latest_comparison")
    @patch("core.observability.HealthTimelineStore")
    def test_comparison_has_read_only_versioned_cli_parity(
        self,
        store_cls,
        latest,
        output_json,
    ):
        latest.return_value.to_dict.return_value = {
            "before_check_id": "before",
            "after_check_id": "after",
        }

        self.assertEqual(
            cmd_health(SimpleNamespace(health_action="comparison")),
            0,
        )

        payload = output_json.call_args.args[0]
        self.assertEqual(payload["schema_id"], "loofi.system-check-comparison")
        self.assertEqual(payload["schema_version"], 1)
        self.assertEqual(
            payload["data"]["comparison"]["after_check_id"],
            "after",
        )
        store_cls.return_value.load.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()
