"""Tests for profile API routes (v24.0)."""

import os
import sys
import unittest
from unittest.mock import patch

import pytest

try:
    from fastapi.testclient import TestClient
    _HAS_FASTAPI = True
except ImportError:
    _HAS_FASTAPI = False

pytestmark = pytest.mark.skipif(not _HAS_FASTAPI, reason="fastapi not installed")

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'loofi-fedora-tweaks'))

if _HAS_FASTAPI:
    from utils.api_server import APIServer, RouteRateLimitPolicy
    from utils.auth import AuthManager
    from utils.containers import Result
else:
    class RouteRateLimitPolicy:  # type: ignore[no-redef]
        def __init__(self, rate=0.0, capacity=0, retry_guidance=""):
            self.rate = rate
            self.capacity = capacity
            self.retry_guidance = retry_guidance

    class APIServer:  # type: ignore[no-redef]
        _RATE_LIMIT_CONFIG = {}

    # Dummy so @patch return_value=Result(...) doesn't crash at collection
    class Result:  # type: ignore[no-redef]
        def __init__(self, success=True, message="", data=None):
            self.success = success
            self.message = message
            self.data = data or {}


class TestAPIProfiles(unittest.TestCase):
    """Profile endpoint coverage with auth override."""

    @classmethod
    def _build_client(cls):
        server = APIServer()
        server.app.dependency_overrides[AuthManager.verify_bearer_token] = lambda: "test-token"
        return TestClient(server.app)

    @classmethod
    def setUpClass(cls):
        cls.client = cls._build_client()

    @patch("api.routes.profiles.ProfileManager.get_active_profile", return_value="gaming")
    @patch("api.routes.profiles.ProfileManager.list_profiles", return_value=[{"key": "gaming", "builtin": True}])
    def test_profiles_list(self, mock_list, mock_active):
        resp = self.client.get("/api/profiles")
        self.assertEqual(resp.status_code, 200)
        payload = resp.json()
        self.assertEqual(payload["active_profile"], "gaming")
        self.assertEqual(payload["profiles"][0]["key"], "gaming")

    @patch("api.routes.profiles.SafetyManager.api_mutation_block_reason", return_value=None)
    @patch("api.routes.profiles.ProfileManager.apply_profile", return_value=Result(True, "ok", {"warnings": []}))
    def test_profiles_apply(self, mock_apply, mock_safe_mode):
        resp = self.client.post("/api/profiles/apply", json={"name": "gaming", "create_snapshot": False})
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.json()["success"])

    @patch("api.routes.profiles.AuditLogger")
    @patch("api.routes.profiles.SafetyManager.api_mutation_block_reason", return_value="Safe Mode blocked profile changes")
    @patch("api.routes.profiles.ProfileManager.apply_profile")
    def test_profiles_apply_blocked_by_safe_mode(self, mock_apply, mock_safe_mode, mock_audit_cls):
        resp = self.client.post("/api/profiles/apply", json={"name": "gaming", "create_snapshot": False})

        self.assertEqual(resp.status_code, 403)
        self.assertIn("Safe Mode blocked", resp.json()["detail"])
        mock_apply.assert_not_called()
        mock_audit_cls.return_value.log.assert_called_once()

    @patch("api.routes.profiles.AuditLogger")
    @patch("api.routes.profiles.SafetyManager.api_mutation_block_reason", return_value=None)
    @patch("api.routes.profiles.ProfileManager.import_bundle_data", return_value=Result(True, "imported", {"imported": 1}))
    def test_profile_import_all_audits_success(self, mock_import_all, mock_safe_mode, mock_audit_cls):
        resp = self.client.post(
            "/api/profiles/import-all",
            json={
                "bundle": {"schema_version": 1, "profiles": [{"key": "x", "name": "X", "settings": {}}]},
                "overwrite": True,
            },
        )

        self.assertEqual(resp.status_code, 200)
        mock_import_all.assert_called_once()
        mock_audit_cls.return_value.log.assert_called_once_with(
            "api.profiles.import_all",
            params={"overwrite": True, "profile_count": 1, "success": True},
            exit_code=0,
        )

    @patch("api.routes.profiles.ProfileManager.export_profile_data", return_value={})
    def test_profile_export_single_not_found(self, mock_export):
        resp = self.client.get("/api/profiles/unknown/export")
        self.assertEqual(resp.status_code, 200)
        self.assertIn("error", resp.json())

    def test_profile_import_single_validation_error(self):
        resp = self.client.post("/api/profiles/import", json={"overwrite": False})
        self.assertEqual(resp.status_code, 422)

    @patch("api.routes.profiles.SafetyManager.api_mutation_block_reason", return_value=None)
    @patch("api.routes.profiles.ProfileManager.import_profile_data", return_value=Result(True, "imported", {"key": "one"}))
    def test_profile_import_single_success(self, mock_import, mock_safe_mode):
        resp = self.client.post(
            "/api/profiles/import",
            json={"profile": {"key": "one", "name": "One", "settings": {}}, "overwrite": False},
        )
        self.assertEqual(resp.status_code, 200)
        payload = resp.json()
        self.assertTrue(payload["success"])
        self.assertEqual(payload["data"]["key"], "one")

    @patch("api.routes.profiles.ProfileManager.export_bundle_data", return_value={"kind": "profile_bundle", "profiles": []})
    def test_profile_export_all(self, mock_export_all):
        resp = self.client.get("/api/profiles/export-all?include_builtins=true")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["kind"], "profile_bundle")

    @patch("api.routes.profiles.SafetyManager.api_mutation_block_reason", return_value=None)
    @patch("api.routes.profiles.ProfileManager.import_bundle_data", return_value=Result(False, "with errors", {"errors": [{"key": "x"}]}))
    def test_profile_import_all_overwrite(self, mock_import_all, mock_safe_mode):
        resp = self.client.post(
            "/api/profiles/import-all",
            json={
                "bundle": {"schema_version": 1, "profiles": [{"key": "x", "name": "X", "settings": {}}]},
                "overwrite": True,
            },
        )
        self.assertEqual(resp.status_code, 200)
        payload = resp.json()
        self.assertFalse(payload["success"])
        self.assertEqual(payload["data"]["errors"][0]["key"], "x")

    @patch.object(
        APIServer,
        "_RATE_LIMIT_CONFIG",
        new={
            "auth": RouteRateLimitPolicy(
                rate=10.0,
                capacity=50,
                retry_guidance="Wait before retrying auth endpoints.",
            ),
            "read": RouteRateLimitPolicy(
                rate=0.0,
                capacity=2,
                retry_guidance="Reduce read polling before retrying.",
            ),
            "mutation": RouteRateLimitPolicy(
                rate=0.0,
                capacity=1,
                retry_guidance="Retry mutations after the backoff window.",
            ),
        },
    )
    @patch("api.routes.profiles.SafetyManager.api_mutation_block_reason", return_value=None)
    @patch("api.routes.profiles.ProfileManager.apply_profile", return_value=Result(True, "ok", {"warnings": []}))
    @patch("api.routes.profiles.ProfileManager.get_active_profile", return_value="gaming")
    @patch("api.routes.profiles.ProfileManager.list_profiles", return_value=[{"key": "gaming", "builtin": True}])
    def test_mutation_routes_are_stricter_than_read_only(self, mock_list, mock_active, mock_apply, mock_safe_mode):
        client = self._build_client()

        read_one = client.get("/api/profiles")
        read_two = client.get("/api/profiles")
        mutate_one = client.post("/api/profiles/apply", json={"name": "gaming", "create_snapshot": False})
        mutate_two = client.post("/api/profiles/apply", json={"name": "gaming", "create_snapshot": False})

        self.assertEqual(read_one.status_code, 200)
        self.assertEqual(read_two.status_code, 200)
        self.assertEqual(read_one.headers["X-Loofi-Route-Policy"], "read")
        self.assertEqual(mutate_one.status_code, 200)
        self.assertEqual(mutate_one.headers["X-Loofi-Route-Policy"], "mutation")
        self.assertEqual(mutate_two.status_code, 429)

        payload = mutate_two.json()
        self.assertEqual(payload["route_policy"], "mutation")
        self.assertGreaterEqual(payload["retry_after_seconds"], 1)
        self.assertIn("Retry after", payload["detail"])

    @patch.object(
        APIServer,
        "_RATE_LIMIT_CONFIG",
        new={
            "auth": RouteRateLimitPolicy(
                rate=10.0,
                capacity=50,
                retry_guidance="Wait before retrying auth endpoints.",
            ),
            "read": RouteRateLimitPolicy(
                rate=0.0,
                capacity=1,
                retry_guidance="Reduce read polling before retrying.",
            ),
            "mutation": RouteRateLimitPolicy(
                rate=10.0,
                capacity=50,
                retry_guidance="Retry mutations after the backoff window.",
            ),
        },
    )
    @patch("api.routes.profiles.ProfileManager.export_profile_data", return_value={"key": "gaming"})
    def test_profile_export_route_uses_read_rate_policy(self, mock_export):
        client = self._build_client()

        first = client.get("/api/profiles/gaming/export")
        second = client.get("/api/profiles/gaming/export")

        self.assertEqual(first.status_code, 200)
        self.assertEqual(first.headers["X-Loofi-Route-Policy"], "read")
        self.assertEqual(second.status_code, 429)
        payload = second.json()
        self.assertEqual(payload["route_policy"], "read")
        self.assertIn("Retry after", payload["detail"])


if __name__ == "__main__":
    unittest.main()
