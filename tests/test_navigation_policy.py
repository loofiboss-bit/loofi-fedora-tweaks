"""Tests for the pure v15 navigation policy."""

import unittest
from dataclasses import replace
from unittest.mock import patch

from core.navigation.destinations import placement_for_route
from core.navigation.manifest import all_routes
from core.navigation.models import (
    DirectLinkBehavior,
    FedoraVariant,
    NavigationContext,
    NavigationDecision,
    NavigationMode,
)
from core.navigation.policy import NavigationPolicy, validate_navigation_policy

_ORIGINAL_EVALUATE = NavigationPolicy.evaluate


def _context(**overrides):
    values = {
        "mode": NavigationMode.STANDARD,
        "installed_components": frozenset({"core", "specialist"}),
        "fedora_variant": FedoraVariant.TRADITIONAL,
        "capabilities": frozenset({"dnf"}),
        "incompatible_plugin_ids": frozenset(),
        "favorite_route_ids": frozenset(),
    }
    values.update(overrides)
    return NavigationContext(**values)


class TestNavigationPolicyCompatibility(unittest.TestCase):
    def test_unknown_route_fails_safe_to_home(self):
        result = NavigationPolicy.evaluate("does-not-exist")

        self.assertEqual(result.decision, NavigationDecision.UNAVAILABLE)
        self.assertIsNone(result.route_id)
        self.assertEqual(result.fallback_route_id, "atlas_dashboard")
        self.assertFalse(result.search_visible)
        self.assertEqual(result.direct_link_behavior, DirectLinkBehavior.EXPLAIN)

    def test_alias_resolves_to_canonical_route(self):
        result = NavigationPolicy.evaluate("Action Center")

        self.assertEqual(result.route_id, "maintenance:action-center")
        self.assertEqual(result.decision, NavigationDecision.VISIBLE)

    def test_dashboard_redirects_without_replacing_its_route_identity(self):
        result = NavigationPolicy.evaluate("dashboard")

        self.assertEqual(result.route_id, "dashboard")
        self.assertEqual(result.destination_id, "system")
        self.assertEqual(result.decision, NavigationDecision.HIDDEN)
        self.assertEqual(result.redirect_route_id, "system_info")
        self.assertEqual(result.direct_link_behavior, DirectLinkBehavior.REDIRECT)
        self.assertFalse(result.search_visible)

    def test_dashboard_redirect_cannot_bypass_target_compatibility(self):
        result = NavigationPolicy.evaluate(
            "dashboard",
            _context(incompatible_plugin_ids=frozenset({"system_info"})),
        )

        self.assertEqual(result.route_id, "dashboard")
        self.assertEqual(result.decision, NavigationDecision.UNAVAILABLE)
        self.assertEqual(result.direct_link_behavior, DirectLinkBehavior.EXPLAIN)
        self.assertIsNone(result.redirect_route_id)
        self.assertFalse(result.search_visible)

    def test_dashboard_redirect_cannot_bypass_missing_core_component(self):
        result = NavigationPolicy.evaluate(
            "dashboard",
            _context(installed_components=frozenset({"specialist"})),
        )

        self.assertEqual(result.decision, NavigationDecision.UNAVAILABLE)
        self.assertEqual(result.required_component, "core")
        self.assertEqual(result.direct_link_behavior, DirectLinkBehavior.EXPLAIN)

    @patch("core.navigation.policy.placement_for_route", return_value=None)
    def test_registered_route_without_placement_fails_safe(self, mock_placement):
        result = NavigationPolicy.evaluate("system_info")

        self.assertEqual(result.route_id, "system_info")
        self.assertEqual(result.decision, NavigationDecision.UNAVAILABLE)
        self.assertEqual(result.fallback_route_id, "atlas_dashboard")


class TestNavigationPolicySafety(unittest.TestCase):
    def test_action_center_is_standard_visible_on_both_fedora_variants(self):
        traditional = NavigationPolicy.evaluate(
            "maintenance:action-center",
            _context(fedora_variant=FedoraVariant.TRADITIONAL),
        )
        atomic = NavigationPolicy.evaluate(
            "maintenance:action-center",
            _context(
                fedora_variant=FedoraVariant.ATOMIC,
                capabilities=frozenset({"rpm-ostree"}),
            ),
        )

        for result in (traditional, atomic):
            self.assertEqual(result.decision, NavigationDecision.VISIBLE)
            self.assertEqual(result.destination_id, "software_updates")
            self.assertEqual(result.risk, "medium")
            self.assertEqual(result.direct_link_behavior, DirectLinkBehavior.ALLOW)

    def test_favorite_does_not_bypass_advanced_mode_gate(self):
        result = NavigationPolicy.evaluate(
            "development",
            _context(favorite_route_ids=frozenset({"development"})),
        )

        self.assertTrue(result.is_favorite)
        self.assertEqual(result.decision, NavigationDecision.GATED)
        self.assertEqual(result.required_mode, NavigationMode.ADVANCED)
        self.assertFalse(result.search_visible)

    def test_missing_component_is_unavailable_even_when_favorited(self):
        result = NavigationPolicy.evaluate(
            "ai_lab",
            _context(
                mode=NavigationMode.ADVANCED,
                installed_components=frozenset({"core"}),
                favorite_route_ids=frozenset({"ai_lab"}),
            ),
        )

        self.assertEqual(result.decision, NavigationDecision.UNAVAILABLE)
        self.assertEqual(result.required_component, "specialist")
        self.assertEqual(result.fallback_route_id, "atlas_dashboard")
        self.assertFalse(result.search_visible)

    def test_incompatible_plugin_is_unavailable_even_when_favorited(self):
        result = NavigationPolicy.evaluate(
            "security",
            _context(
                incompatible_plugin_ids=frozenset({"security"}),
                favorite_route_ids=frozenset({"security"}),
            ),
        )

        self.assertEqual(result.decision, NavigationDecision.UNAVAILABLE)
        self.assertEqual(result.fallback_route_id, "network")
        self.assertFalse(result.search_visible)

    def test_overlays_are_hidden_on_traditional_fedora(self):
        result = NavigationPolicy.evaluate(
            "maintenance:overlays",
            _context(
                mode=NavigationMode.ADVANCED,
                favorite_route_ids=frozenset({"maintenance:overlays"}),
            ),
        )

        self.assertEqual(result.decision, NavigationDecision.HIDDEN)
        self.assertEqual(result.direct_link_behavior, DirectLinkBehavior.EXPLAIN)
        self.assertFalse(result.search_visible)

    def test_overlays_are_visible_on_capable_atomic_fedora_in_advanced_mode(self):
        result = NavigationPolicy.evaluate(
            "maintenance:overlays",
            _context(
                mode=NavigationMode.ADVANCED,
                fedora_variant=FedoraVariant.ATOMIC,
                capabilities=frozenset({"rpm-ostree"}),
            ),
        )

        self.assertEqual(result.decision, NavigationDecision.VISIBLE)
        self.assertTrue(result.search_visible)

    def test_missing_atomic_capability_is_unavailable(self):
        result = NavigationPolicy.evaluate(
            "maintenance:overlays",
            _context(
                mode=NavigationMode.ADVANCED,
                fedora_variant=FedoraVariant.ATOMIC,
                capabilities=frozenset(),
            ),
        )

        self.assertEqual(result.decision, NavigationDecision.UNAVAILABLE)
        self.assertEqual(result.required_capabilities, frozenset({"rpm-ostree"}))


class TestNavigationPolicyCoverage(unittest.TestCase):
    def test_every_route_has_outcome_for_full_mode_variant_matrix(self):
        contexts = (
            _context(),
            _context(
                fedora_variant=FedoraVariant.ATOMIC,
                capabilities=frozenset({"rpm-ostree"}),
            ),
            _context(mode=NavigationMode.ADVANCED),
            _context(
                mode=NavigationMode.ADVANCED,
                fedora_variant=FedoraVariant.ATOMIC,
                capabilities=frozenset({"rpm-ostree"}),
            ),
        )

        outcomes = 0
        for route in all_routes():
            for context in contexts:
                with self.subTest(route=route.id, context=context):
                    result = NavigationPolicy.evaluate(route.id, context)
                    self.assertEqual(result.route_id, route.id)
                    self.assertIsInstance(result.decision, NavigationDecision)
                    outcomes += 1

        self.assertEqual(outcomes, 78 * 4)
        self.assertEqual(validate_navigation_policy(), [])

    def test_standard_mode_never_exposes_advanced_routes_through_favorites(self):
        advanced_ids = {
            route.id
            for route in all_routes()
            if placement_for_route(route.id).advanced_only
        }
        context = _context(favorite_route_ids=frozenset(advanced_ids))

        for route_id in advanced_ids:
            with self.subTest(route=route_id):
                result = NavigationPolicy.evaluate(route_id, context)
                self.assertNotEqual(result.decision, NavigationDecision.VISIBLE)
                self.assertFalse(result.search_visible)

    @patch("core.navigation.policy.NavigationPolicy.evaluate")
    def test_validator_reports_unstable_policy_outcome(self, mock_evaluate):
        valid = _ORIGINAL_EVALUATE("atlas_dashboard")
        mock_evaluate.return_value = replace(valid, route_id="wrong-route")

        errors = validate_navigation_policy()

        self.assertTrue(any("no stable policy outcome" in error for error in errors))


if __name__ == "__main__":
    unittest.main()
