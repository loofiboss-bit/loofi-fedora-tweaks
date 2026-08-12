"""v25 Proof CLI run grammar and dispatch tests."""

from __future__ import annotations

import unittest
from argparse import Namespace
from unittest.mock import MagicMock, patch

from cli.parser import build_parser
from core.actions.direct import DirectActionParameterError, parse_typed_parameters


class TestV25CliRun(unittest.TestCase):
    def test_run_parser_supports_typed_parameters_and_local_flags(self):
        args = build_parser().parse_args(
            [
                "run",
                "restart-failed-service",
                "--param",
                "service=broken.service",
                "--yes",
                "--dry-run",
                "--json",
            ]
        )
        self.assertEqual(args.command, "run")
        self.assertEqual(args.action_id, "restart-failed-service")
        self.assertTrue(args.yes)
        self.assertTrue(args.dry_run)
        self.assertTrue(args.json)

    def test_typed_parameter_parser_is_closed(self):
        schema = {
            "days": {"type": "integer"},
            "enabled": {"type": "boolean"},
            "description": {"type": "string"},
        }
        self.assertEqual(
            parse_typed_parameters(["days=7", "enabled=true", "description=Safe"], schema),
            {"days": 7, "enabled": True, "description": "Safe"},
        )
        with self.assertRaises(DirectActionParameterError):
            parse_typed_parameters(["shell=echo bad"], schema)

    @patch("cli.main._output_json")
    @patch("cli.main.DirectActionService", create=True)
    def test_handler_emits_versioned_result_and_returns_stable_code(self, service_cls, output_json):
        # The implementation imports the service lazily; patch the source module too.
        result = MagicMock()
        result.to_dict.return_value = {"schema": "loofi.direct-action/v1", "status": "review_required"}
        result.exit_code = 2
        result.display_label = "Review required"
        result.action_id = "dnf-clean-all"
        result.message = "Review first"
        result.plan_id = "plan-1"
        result.preview = ()
        service_cls.return_value.run.return_value = result
        args = Namespace(action_id="dnf-clean-all", param=[], yes=False, dry_run=False, timeout=120, target="44")
        import cli.main as cli_main

        with patch("core.actions.DirectActionService", return_value=service_cls.return_value):
            cli_main._json_output = True
            self.assertEqual(cli_main.cmd_run(args), 2)
        output_json.assert_called_once()


if __name__ == "__main__":
    unittest.main()
