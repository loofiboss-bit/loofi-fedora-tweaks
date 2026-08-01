"""Security and closed-planning contract tests for the Web API."""

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
    from utils.api_server import APIServer, TokenRateLimiter
    from utils.auth import AuthManager


def _iter_api_methods(routes):
    """Yield methods from flat and nested FastAPI router representations."""
    for route in routes:
        path = getattr(route, "path", "")
        methods = set(getattr(route, "methods", set()) or set())
        if path:
            yield path, methods
        original_router = getattr(route, "original_router", None)
        if original_router is not None:
            yield from _iter_api_methods(getattr(original_router, "routes", ()))


class TestClosedPlanningAPI(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = APIServer()
        cls.server.app.dependency_overrides[AuthManager.verify_bearer_token] = lambda: "test-token"
        cls.client = TestClient(cls.server.app)

    def test_health_is_authenticated_without_version_leak(self):
        response = self.client.get("/api/health")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok"})

    def test_health_rejects_missing_authentication(self):
        server = APIServer()
        response = TestClient(server.app).get("/api/health")
        self.assertIn(response.status_code, {401, 403})

    def test_only_closed_planning_and_token_are_non_read_methods(self):
        non_read = []
        for path, methods in _iter_api_methods(self.server.app.routes):
            if not path.startswith("/api"):
                continue
            methods -= {"GET", "HEAD", "OPTIONS"}
            if methods:
                non_read.append((path, methods))
        self.assertEqual(
            non_read,
            [
                ("/api/action-center/plans", {"POST"}),
                ("/api/token", {"POST"}),
            ],
        )

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


class TestApiTrustBoundary(unittest.TestCase):
    def test_non_loopback_bind_is_rejected(self):
        with self.assertRaises(ValueError):
            APIServer(host="0.0.0.0")

    def test_ipv6_loopback_is_accepted(self):
        server = APIServer(host="::1")
        self.assertEqual(server.host, "::1")

    def test_token_limiter_expires_old_attempts(self):
        limiter = TokenRateLimiter(limit=2, window_seconds=60)
        self.assertTrue(limiter.allow("client", now=0))
        self.assertTrue(limiter.allow("client", now=1))
        self.assertFalse(limiter.allow("client", now=2))
        self.assertTrue(limiter.allow("client", now=61))


if __name__ == "__main__":
    unittest.main()
