"""Regression proofs retained across the Haven security-boundary cleanup."""

from unittest import TestCase

from core.executor.command_policy import CommandValidationError, validate_command


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
