"""Regression proofs for findings closed before the Anchor release."""

from unittest import TestCase
from unittest.mock import patch

from core.executor.command_policy import CommandValidationError, validate_command
from services.security.sandbox import PluginIsolationManager


class TestApiCredentialBootstrap(TestCase):
    def test_remote_api_key_generation_route_does_not_exist(self):
        from fastapi.testclient import TestClient
        from utils.api_server import APIServer

        response = TestClient(APIServer().app).post("/api/key")
        self.assertEqual(response.status_code, 404)


class TestCommandPolicyArgumentLanguages(TestCase):
    def test_rpm_macro_evaluation_is_rejected(self):
        with self.assertRaises(CommandValidationError):
            validate_command("rpm", ["--eval", "macro-input"])

    def test_rpm_macro_definition_is_rejected(self):
        with self.assertRaises(CommandValidationError):
            validate_command("rpm", ["--define=unsafe value"])

    def test_read_only_rpm_query_remains_allowed(self):
        validate_command("rpm", ["-q", "bash"])


class TestPluginIsolationFailClosed(TestCase):
    @patch("services.security.sandbox.BubblewrapManager.is_installed", return_value=True)
    @patch("services.security.sandbox.SandboxManager.is_firejail_installed", return_value=True)
    def test_process_mode_is_not_claimed_from_binary_availability(self, _firejail, _bubblewrap):
        self.assertFalse(PluginIsolationManager.can_enforce_mode("process"))

    @patch("services.security.sandbox.BubblewrapManager.is_installed", return_value=True)
    def test_os_mode_is_not_claimed_from_binary_availability(self, _bubblewrap):
        self.assertFalse(PluginIsolationManager.can_enforce_mode("os"))

    def test_advisory_mode_remains_available(self):
        self.assertTrue(PluginIsolationManager.can_enforce_mode("advisory"))
