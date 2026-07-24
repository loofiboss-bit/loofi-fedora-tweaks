"""Authenticated read-only System Check API contracts."""

from __future__ import annotations

import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from core.observability.snapshot import HealthSnapshot
from core.system_check.models import SystemCheckResult


def _snapshot() -> HealthSnapshot:
    return HealthSnapshot.from_system_check(
        SystemCheckResult(
            "check-1",
            "system-check-quick-v1",
            "completed",
            False,
            10.0,
            20.0,
            (),
            (),
            (),
            ("maintenance",),
        )
    )


class TestSystemCheckApi(unittest.TestCase):
    def test_latest_result_requires_authentication(self):
        from utils.api_server import APIServer

        response = TestClient(APIServer().app).get(
            "/api/system-check/latest"
        )

        self.assertIn(response.status_code, {401, 403})

    @patch("core.observability.HealthTimelineStore")
    def test_latest_result_is_bounded_read_only_and_does_not_collect(
        self,
        store_cls,
    ):
        from api.routes.system import get_latest_system_check

        store_cls.return_value.load.return_value = [_snapshot()]
        store_cls.return_value.last_error = ""

        payload = get_latest_system_check(_auth="token")

        self.assertTrue(payload["read_only"])
        self.assertEqual(payload["schema_id"], "loofi.system-check")
        self.assertEqual(payload["schema_version"], 1)
        self.assertEqual(payload["result"]["check_id"], "check-1")
        self.assertEqual(payload["source_status"], "available")
        store_cls.return_value.load.assert_called_once_with()

    def test_api_exposes_no_system_check_mutation_route(self):
        from utils.api_server import APIServer

        routes = {
            (getattr(route, "path", ""), method)
            for route in APIServer().app.routes
            for method in (getattr(route, "methods", set()) or set())
        }

        self.assertIn(("/api/system-check/latest", "GET"), routes)
        self.assertNotIn(("/api/system-check/run", "POST"), routes)
        self.assertNotIn(("/api/system-check/confirm", "POST"), routes)
        self.assertNotIn(("/api/system-check/execute", "POST"), routes)


if __name__ == "__main__":
    unittest.main()
