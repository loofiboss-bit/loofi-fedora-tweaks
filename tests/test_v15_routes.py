"""Long-lived v15 route IDs retained by the v19 navigation catalog."""

from __future__ import annotations

import unittest

from core.navigation import canonical_persisted_route, resolve


class TestV15StableRoutes(unittest.TestCase):
    def test_home_diagnostics_and_health_ids_remain_resolvable(self):
        for route_id in (
            "atlas_dashboard",
            "diagnostics",
            "diagnostics:boot",
            "health",
            "maintenance:health-timeline",
            "maintenance:action-center",
        ):
            with self.subTest(route_id=route_id):
                self.assertEqual(resolve(route_id).id, route_id)
                self.assertEqual(canonical_persisted_route(route_id), route_id)


if __name__ == "__main__":
    unittest.main()
