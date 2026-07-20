"""Read-only profile API contract tests."""

import unittest
from unittest.mock import patch

import pytest

try:
    from fastapi.testclient import TestClient
    _HAS_FASTAPI = True
except ImportError:
    _HAS_FASTAPI = False

pytestmark = pytest.mark.skipif(not _HAS_FASTAPI, reason="fastapi not installed")

if _HAS_FASTAPI:
    from utils.api_server import APIServer
    from utils.auth import AuthManager


class TestAPIProfiles(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        server = APIServer()
        server.app.dependency_overrides[AuthManager.verify_bearer_token] = lambda: "test-token"
        cls.client = TestClient(server.app)

    @patch("api.routes.profiles.ProfileManager.get_active_profile", return_value="gaming")
    @patch("api.routes.profiles.ProfileManager.list_profiles", return_value=[{"key": "gaming", "builtin": True}])
    def test_profiles_list(self, _list, _active):
        response = self.client.get("/api/profiles")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["active_profile"], "gaming")

    @patch("api.routes.profiles.ProfileManager.export_bundle_data", return_value={"kind": "profile_bundle", "profiles": []})
    def test_profile_export_all(self, _export):
        response = self.client.get("/api/profiles/export-all?include_builtins=true")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["kind"], "profile_bundle")

    @patch("api.routes.profiles.ProfileManager.export_profile_data", return_value={})
    def test_profile_export_single_not_found(self, _export):
        response = self.client.get("/api/profiles/unknown/export")
        self.assertEqual(response.status_code, 200)
        self.assertIn("error", response.json())


if __name__ == "__main__":
    unittest.main()
