"""Outer entrypoint forwarding contracts for the public CLI."""

import os
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "loofi-fedora-tweaks"))

import main as app_main  # noqa: E402


class TestCliHelpDispatch(unittest.TestCase):
    def test_helper_only_for_help_after_cli_flag(self):
        self.assertEqual(
            app_main._forwarded_cli_help(["--cli", "--help"]),
            ["--help"],
        )
        self.assertEqual(
            app_main._forwarded_cli_help(["-c", "activity", "--help"]),
            ["activity", "--help"],
        )
        self.assertIsNone(app_main._forwarded_cli_help(["--help", "--cli"]))
        self.assertIsNone(app_main._forwarded_cli_help(["--cli", "info"]))

    @patch("cli.main.main", return_value=0)
    def test_outer_entrypoint_forwards_cli_help(self, cli_main):
        result = app_main.main(["--cli", "activity", "--help"])

        self.assertEqual(result, 0)
        cli_main.assert_called_once_with(["activity", "--help"])


if __name__ == "__main__":
    unittest.main()
