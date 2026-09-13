"""Regression proofs retained across the Haven security-boundary cleanup."""

from unittest import TestCase

from core.executor.command_policy import CommandValidationError, validate_command




class TestCommandPolicyArgumentLanguages(TestCase):
    def test_rpm_macro_evaluation_is_rejected(self):
        with self.assertRaises(CommandValidationError):
            validate_command("rpm", ["--eval", "macro-input"])

    def test_rpm_macro_definition_is_rejected(self):
        with self.assertRaises(CommandValidationError):
            validate_command("rpm", ["--define=unsafe value"])

    def test_read_only_rpm_query_remains_allowed(self):
        validate_command("rpm", ["-q", "bash"])
