"""Version-neutral Web API mutation and loopback security gates."""

from __future__ import annotations

import unittest

from utils.api_server import APIServer


class TestApiSecurity(unittest.TestCase):
    def test_bind_remains_loopback_only(self):
        with self.assertRaises(ValueError):
            APIServer(host="0.0.0.0")

    def test_only_token_uses_a_non_read_method(self):
        non_read = []
        for route in APIServer().app.routes:
            path = getattr(route, "path", "")
            if not path.startswith("/api"):
                continue
            methods = set(getattr(route, "methods", set()) or set())
            methods -= {"GET", "HEAD", "OPTIONS"}
            if methods:
                non_read.append((path, methods))

        self.assertEqual(non_read, [("/api/token", {"POST"})])

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
