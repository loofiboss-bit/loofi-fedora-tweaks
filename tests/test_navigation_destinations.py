"""Tests for the v15 destination and route-placement contracts."""

import unittest
from unittest.mock import patch

from core.navigation.destinations import (
    ADVANCED_DESTINATION,
    STANDARD_DESTINATIONS,
    all_destinations,
    destinations_for_mode,
    placement_for_route,
    validate_destinations,
)
from core.navigation.manifest import all_routes, resolve
from core.navigation.models import (
    Destination,
    FedoraVariant,
    NavigationMode,
    RoutePlacement,
)


_BROKEN_DESTINATION = Destination(
    "broken",
    "Broken",
    "missing-icon",
    "missing-default",
    ("other-route",),
)
_BROKEN_PLACEMENT = RoutePlacement(
    "missing-route",
    "missing-destination",
    "broken-section",
    redirect_route_id="missing-redirect",
)


class TestDestinationDefinitions(unittest.TestCase):
    def test_standard_mode_has_exactly_six_destinations(self):
        self.assertEqual(
            [destination.id for destination in STANDARD_DESTINATIONS],
            [
                "home",
                "software_updates",
                "system",
                "network_security",
                "desktop",
                "settings",
            ],
        )
        self.assertEqual(
            destinations_for_mode(NavigationMode.STANDARD),
            STANDARD_DESTINATIONS,
        )

    def test_advanced_mode_adds_one_advanced_destination(self):
        destinations = destinations_for_mode(NavigationMode.ADVANCED)

        self.assertEqual(len(destinations), 7)
        self.assertEqual(destinations[-1], ADVANCED_DESTINATION)
        self.assertTrue(destinations[-1].advanced_only)

    def test_every_default_route_resolves_and_belongs_to_destination(self):
        for destination in all_destinations():
            with self.subTest(destination=destination.id):
                self.assertIsNotNone(resolve(destination.default_route_id))
                self.assertIn(destination.default_route_id, destination.route_ids)


class TestRoutePlacements(unittest.TestCase):
    def test_all_manifest_routes_have_exactly_one_valid_placement(self):
        routes = all_routes()
        placements = [placement_for_route(route.id) for route in routes]

        self.assertEqual(len(routes), 78)
        self.assertTrue(all(placement is not None for placement in placements))
        self.assertEqual(len({placement.route_id for placement in placements}), 78)
        self.assertEqual(validate_destinations(), [])

    def test_representative_sections_match_phase_one_contract(self):
        expected = {
            "atlas_dashboard": ("home", "overview"),
            "software:apps": ("software_updates", "applications"),
            "maintenance:action-center": ("software_updates", "action_center"),
            "maintenance:health-timeline": ("system", "system_health_history"),
            "system-monitor:processes": ("system", "processes"),
            "snapshots": ("system", "recovery_points"),
            "security:firewall": ("network_security", "firewall"),
            "desktop:display": ("desktop", "displays"),
            "settings:behavior": ("settings", "behavior"),
            "development:containers": ("advanced", "development"),
            "profiles": ("advanced", "profiles"),
        }
        for route_id, placement_ids in expected.items():
            with self.subTest(route_id=route_id):
                placement = placement_for_route(route_id)
                self.assertIsNotNone(placement)
                self.assertEqual(
                    (placement.destination_id, placement.section_id),
                    placement_ids,
                )

    def test_dashboard_is_resolvable_compatibility_route(self):
        route = resolve("dashboard")
        placement = placement_for_route("dashboard")

        self.assertIsNotNone(route)
        self.assertEqual(route.id, "dashboard")
        self.assertEqual(route.plugin_id, "system_info")
        self.assertEqual(placement.destination_id, "system")
        self.assertEqual(placement.redirect_route_id, "system_info")
        self.assertFalse(placement.discoverable)

    def test_action_center_is_standard_core_route(self):
        placement = placement_for_route("maintenance:action-center")

        self.assertFalse(placement.advanced_only)
        self.assertEqual(placement.component_id, "core")
        self.assertEqual(
            placement.allowed_variants,
            frozenset({FedoraVariant.TRADITIONAL, FedoraVariant.ATOMIC}),
        )

    def test_overlays_are_explicitly_advanced_and_atomic_only(self):
        placement = placement_for_route("maintenance:overlays")

        self.assertTrue(placement.advanced_only)
        self.assertEqual(
            placement.allowed_variants,
            frozenset({FedoraVariant.ATOMIC}),
        )


class TestDestinationValidationFailures(unittest.TestCase):
    @patch(
        "core.navigation.destinations._DESTINATION_BY_ID",
        new={},
    )
    @patch(
        "core.navigation.destinations._DESTINATIONS",
        new=(_BROKEN_DESTINATION, _BROKEN_DESTINATION),
    )
    @patch(
        "core.navigation.destinations._PLACEMENTS",
        new=(_BROKEN_PLACEMENT, _BROKEN_PLACEMENT),
    )
    def test_validator_reports_structural_drift(self):
        errors = validate_destinations()

        self.assertTrue(any("destination placements" in error for error in errors))
        self.assertTrue(any("has no destination placement" in error for error in errors))
        self.assertIn("placement references unknown route missing-route", errors)
        self.assertIn("duplicate destination id: broken", errors)
        self.assertTrue(any("unknown default route" in error for error in errors))
        self.assertTrue(any("default route is outside" in error for error in errors))
        self.assertTrue(any("unknown destination" in error for error in errors))
        self.assertTrue(any("redirects to unknown route" in error for error in errors))

    @patch(
        "core.navigation.destinations._DESTINATION_BY_ID",
        new={
            "home": Destination(
                "home",
                "Home",
                "home",
                "atlas_dashboard",
                (),
            )
        },
    )
    @patch(
        "core.navigation.destinations._DESTINATIONS",
        new=(
            Destination(
                "home",
                "Home",
                "home",
                "atlas_dashboard",
                ("atlas_dashboard",),
            ),
        ),
    )
    @patch(
        "core.navigation.destinations._PLACEMENTS",
        new=(RoutePlacement("atlas_dashboard", "home", "overview"),),
    )
    def test_validator_reports_route_missing_from_destination(self):
        errors = validate_destinations()

        self.assertIn("route atlas_dashboard missing from destination home", errors)

    @patch(
        "core.navigation.destinations._PLACEMENTS",
        new=(
            RoutePlacement(
                "atlas_dashboard",
                "home",
                "overview",
                redirect_route_id="atlas_dashboard",
            ),
        ),
    )
    def test_validator_rejects_self_redirect(self):
        errors = validate_destinations()

        self.assertIn("route atlas_dashboard has a redirect cycle", errors)

    @patch(
        "core.navigation.destinations._PLACEMENTS",
        new=(
            RoutePlacement(
                "atlas_dashboard",
                "home",
                "overview",
                redirect_route_id="dashboard",
            ),
            RoutePlacement(
                "dashboard",
                "system",
                "overview",
                redirect_route_id="atlas_dashboard",
            ),
        ),
    )
    def test_validator_rejects_multi_route_redirect_cycle(self):
        errors = validate_destinations()

        self.assertTrue(any("redirect cycle" in error for error in errors))


if __name__ == "__main__":
    unittest.main()
