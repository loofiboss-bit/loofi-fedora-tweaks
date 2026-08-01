"""Version-neutral Web API mutation and loopback security gates."""

from __future__ import annotations

import unittest

from utils.api_server import APIServer


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


class TestApiSecurity(unittest.TestCase):
    def test_bind_remains_loopback_only(self):
        with self.assertRaises(ValueError):
            APIServer(host="0.0.0.0")

    def test_only_closed_planning_and_token_use_non_read_methods(self):
        non_read = []
        for path, methods in _iter_api_methods(APIServer().app.routes):
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

    def test_action_and_system_check_mutation_routes_are_absent(self):
        paths = {
            getattr(route, "path", "")
            for route in APIServer().app.routes
        }
        for path in (
            "/api/execute",
            "/api/action-center/confirm",
            "/api/action-center/execute",
            "/api/system-check/run",
            "/api/system-check/confirm",
            "/api/system-check/execute",
        ):
            with self.subTest(path=path):
                self.assertNotIn(path, paths)


if __name__ == "__main__":
    unittest.main()
