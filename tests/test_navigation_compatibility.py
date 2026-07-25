"""v19 System Check route compatibility and destination-count gates."""

from __future__ import annotations

import unittest

from core.navigation import (
    STANDARD_DESTINATIONS,
    all_routes,
    canonical_persisted_route,
    placement_for_route,
    resolve,
)


class TestSystemCheckNavigationCompatibility(unittest.TestCase):
    def test_catalog_counts_and_standard_destination_count_stay_fixed(self):
        self.assertEqual(len(all_routes()), 81)
        self.assertEqual(len(STANDARD_DESTINATIONS), 6)

    def test_both_health_routes_use_one_canonical_plugin_and_section(self):
        health = resolve("health")
        history = resolve("maintenance:health-timeline")
        health_placement = placement_for_route(health.id)
        history_placement = placement_for_route(history.id)

        self.assertEqual(health.plugin_id, "health")
        self.assertEqual(history.plugin_id, "health")
        self.assertEqual(health_placement.section_id, "system_check")
        self.assertEqual(history_placement.section_id, "system_check")
        self.assertIsNone(health_placement.redirect_route_id)
        self.assertIsNone(history_placement.redirect_route_id)
        self.assertEqual(history.subroute, "history")

    def test_persisted_ids_and_legacy_aliases_resolve_without_rewrite(self):
        self.assertEqual(canonical_persisted_route("health"), "health")
        self.assertEqual(
            canonical_persisted_route("maintenance:health-timeline"),
            "maintenance:health-timeline",
        )
        self.assertEqual(resolve("System Health").id, "health")
        self.assertEqual(
            resolve("Health Timeline").id,
            "maintenance:health-timeline",
        )

    def test_home_and_diagnostics_deep_links_remain_independent(self):
        self.assertEqual(resolve("atlas_dashboard").plugin_id, "atlas_dashboard")
        self.assertEqual(resolve("diagnostics").plugin_id, "diagnostics")
        self.assertEqual(resolve("diagnostics:boot").plugin_id, "diagnostics")
        self.assertNotEqual(resolve("diagnostics").plugin_id, "health")


if __name__ == "__main__":
    unittest.main()
