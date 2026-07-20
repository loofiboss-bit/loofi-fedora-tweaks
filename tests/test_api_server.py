"""Security and read-only contract tests for the Web API."""

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


class TestReadOnlyAPI(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = APIServer()
        cls.server.app.dependency_overrides[AuthManager.verify_bearer_token] = lambda: "test-token"
        cls.client = TestClient(cls.server.app)

    def test_health_is_public_without_version_leak(self):
        response = self.client.get("/api/health")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok"})

    def test_only_token_is_a_non_read_method(self):
        non_read = []
        for route in self.server.app.routes:
            path = getattr(route, "path", "")
            if not path.startswith("/api"):
                continue
            methods = set(getattr(route, "methods", set()) or set()) - {"GET", "HEAD", "OPTIONS"}
            if methods:
                non_read.append((path, methods))
        self.assertEqual(non_read, [("/api/token", {"POST"})])

    def test_removed_mutation_routes_are_absent(self):
        paths = {getattr(route, "path", "") for route in self.server.app.routes}
        self.assertNotIn("/api/execute", paths)
        self.assertNotIn("/api/profiles/apply", paths)
        self.assertNotIn("/api/profiles/import", paths)
        self.assertNotIn("/api/profiles/import-all", paths)
        self.assertNotIn("/api/observability/snapshot", paths)

    @patch("core.observability.snapshot.HealthSnapshot.collect")
    def test_current_observability_is_not_persisted(self, collect):
        collect.return_value.to_dict.return_value = {"schema_version": 1}
        response = self.client.get("/api/observability/current?target=44")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["read_only"])
        collect.assert_called_once_with(fedora_target="44")

    def test_info_requires_authentication_without_override(self):
        server = APIServer()
        response = TestClient(server.app).get("/api/info")
        self.assertEqual(response.status_code, 401)

    def test_token_rejects_missing_and_invalid_api_keys(self):
        server = APIServer()
        client = TestClient(server.app)
        self.assertEqual(client.post("/api/token", data={}).status_code, 422)
        response = client.post("/api/token", data={"api_key": "invalid"})
        self.assertEqual(response.status_code, 401)

    def test_authenticated_info_remains_read_only(self):
        response = self.client.get("/api/info")
        self.assertEqual(response.status_code, 200)
        self.assertIn("system_type", response.json())


if __name__ == "__main__":
    unittest.main()
