"""Contract tests for the single shell navigation model."""

from __future__ import annotations

import unittest

from core.navigation import get_route
from core.navigation.routes import (
    LEGACY_ALIASES,
    START_ROUTE_ID,
    advanced_shell_route_for,
    all_shell_routes,
    get_shell_route,
    visible_shell_routes,
)


class TestShellRoutes(unittest.TestCase):
    def test_standard_mode_shows_overview_tasks_and_activity(self):
        labels = [route.label for route in visible_shell_routes(False)]
        self.assertEqual(labels, ["Overview", "Tweaks", "Apps", "Updates", "Health", "Activity"])

    def test_advanced_mode_adds_only_advanced_rows_after_core_jobs(self):
        routes = visible_shell_routes(True)
        self.assertEqual(
            [route.label for route in routes],
            ["Overview", "Tweaks", "Apps", "Updates", "Health", "Activity", "System", "Storage", "Network", "Security", "Logs"],
        )
        self.assertTrue(all(route.advanced for route in routes[6:]))
        self.assertFalse(any(route.advanced for route in routes[:6]))

    def test_start_route_is_overview(self):
        self.assertEqual(START_ROUTE_ID, "overview")
        self.assertEqual(visible_shell_routes(False)[0].default_route_id, START_ROUTE_ID)

    def test_ids_are_unique(self):
        ids = [route.id for route in all_shell_routes()]
        self.assertEqual(len(ids), len(set(ids)))

    def test_advanced_routes_resolve_in_the_manifest(self):
        for route in all_shell_routes():
            if not route.advanced:
                continue
            self.assertIsNotNone(get_route(route.default_route_id), route.id)
            for route_id in route.route_ids:
                self.assertIsNotNone(get_route(route_id), f"{route.id}:{route_id}")
            self.assertIn(route.default_route_id, route.route_ids)

    def test_a_route_belongs_to_at_most_one_advanced_row(self):
        owners: dict[str, str] = {}
        for route in all_shell_routes():
            for route_id in route.route_ids:
                self.assertNotIn(route_id, owners, route_id)
                owners[route_id] = route.id

    def test_advanced_lookup_and_unknown_ids(self):
        self.assertEqual(advanced_shell_route_for("network").id, "network")
        self.assertIsNone(advanced_shell_route_for("utility:tune"))
        self.assertIsNone(get_shell_route("missing"))

    def test_legacy_aliases_target_known_destinations(self):
        for alias, target in LEGACY_ALIASES.items():
            self.assertTrue(target.startswith("utility:"), alias)
        self.assertEqual(LEGACY_ALIASES["home"], "utility:tune")


if __name__ == "__main__":
    unittest.main()
