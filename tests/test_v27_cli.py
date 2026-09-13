"""Tests for the 8 canonical v27 CLI commands."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from cli.main import main
from cli.parser import build_parser


class TestV27CliParser:
    """Verify that only the 8 canonical v27 commands are registered."""

    EXPECTED_COMMANDS = {
        "info",
        "check",
        "updates",
        "troubleshoot",
        "changes",
        "activity",
        "doctor",
        "support-bundle",
    }

    DECOMMISSIONED_COMMANDS = [
        "tuning",
        "agent",
        "firewall",
        "preset",
        "mesh",
        "teleport",
        "ai-models",
        "daemon",
        "web",
    ]

    def test_canonical_commands_registered(self):
        parser = build_parser()
        subparsers_action = next(
            a for a in parser._actions if a.dest == "command"
        )
        assert set(subparsers_action.choices.keys()) == self.EXPECTED_COMMANDS

    @pytest.mark.parametrize("cmd", EXPECTED_COMMANDS)
    def test_canonical_commands_parse(self, cmd: str):
        parser = build_parser()
        if cmd == "changes":
            args = parser.parse_args(["changes", "list"])
        elif cmd == "activity":
            args = parser.parse_args(["activity", "list"])
        elif cmd == "troubleshoot":
            args = parser.parse_args(["troubleshoot", "profiles"])
        elif cmd == "updates":
            args = parser.parse_args(["updates", "check"])
        else:
            args = parser.parse_args([cmd])
        assert args.command == cmd

    @pytest.mark.parametrize("cmd", DECOMMISSIONED_COMMANDS)
    def test_decommissioned_commands_rejected(self, cmd: str):
        parser = build_parser()
        with pytest.raises(SystemExit):
            parser.parse_args([cmd])


class TestV27CliExecution:
    """Verify execution dispatch for all 8 canonical commands."""

    @patch("cli.main.cmd_info", return_value=0)
    def test_info_execution(self, mock_cmd: MagicMock):
        assert main(["info"]) == 0
        mock_cmd.assert_called_once()

    @patch("cli.main.cmd_check", return_value=0)
    def test_check_execution(self, mock_cmd: MagicMock):
        assert main(["check"]) == 0
        mock_cmd.assert_called_once()

    @patch("cli.main.cmd_updates", return_value=0)
    def test_updates_execution(self, mock_cmd: MagicMock):
        assert main(["updates", "check"]) == 0
        mock_cmd.assert_called_once()

    @patch("cli.main.cmd_troubleshoot", return_value=0)
    def test_troubleshoot_execution(self, mock_cmd: MagicMock):
        assert main(["troubleshoot", "profiles"]) == 0
        mock_cmd.assert_called_once()

    @patch("cli.main.cmd_changes", return_value=0)
    def test_changes_execution(self, mock_cmd: MagicMock):
        assert main(["changes", "list"]) == 0
        mock_cmd.assert_called_once()

    @patch("cli.main.cmd_activity", return_value=0)
    def test_activity_execution(self, mock_cmd: MagicMock):
        assert main(["activity", "list"]) == 0
        mock_cmd.assert_called_once()

    @patch("cli.main.cmd_doctor", return_value=0)
    def test_doctor_execution(self, mock_cmd: MagicMock):
        assert main(["doctor"]) == 0
        mock_cmd.assert_called_once()

    @patch("cli.main.cmd_support_bundle", return_value=0)
    def test_support_bundle_execution(self, mock_cmd: MagicMock):
        assert main(["support-bundle"]) == 0
        mock_cmd.assert_called_once()
