"""Tests for the PyQt-free v15 global discovery model."""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "loofi-fedora-tweaks"))

from core.navigation import (  # noqa: E402
    FedoraVariant,
    GlobalSearchModel,
    NavigationContext,
    NavigationMode,
    SearchFilter,
    SearchResultKind,
)


class TestGlobalSearchModel(unittest.TestCase):
    def test_combines_routes_settings_and_actions(self):
        model = GlobalSearchModel(
            configured_quick_actions=[
                {
                    "id": "updates",
                    "label": "Update System",
                    "route_id": "maintenance:updates",
                }
            ]
        )

        kinds = {result.kind for result in model.all_results()}

        self.assertEqual(
            kinds,
            {
                SearchResultKind.ROUTE,
                SearchResultKind.SETTING,
                SearchResultKind.ACTION,
            },
        )

    def test_standard_mode_does_not_leak_advanced_routes_or_suggestions(self):
        model = GlobalSearchModel(
            NavigationContext(mode=NavigationMode.STANDARD),
            configured_quick_actions=[
                {"id": "gaming", "label": "Gaming Mode", "route_id": "gaming"}
            ],
        )

        route_ids = {result.route_id for result in model.all_results()}

        self.assertNotIn("gaming", route_ids)
        self.assertIn("settings:advanced", route_ids)

    def test_missing_specialist_component_removes_results_and_pins_do_not_bypass(self):
        context = NavigationContext(
            mode=NavigationMode.ADVANCED,
            installed_components=frozenset({"core"}),
            favorite_route_ids=frozenset({"gaming"}),
        )

        results = GlobalSearchModel(context).all_results()

        self.assertNotIn("gaming", {result.route_id for result in results})

    def test_atomic_context_hides_traditional_only_cache_action(self):
        context = NavigationContext(
            fedora_variant=FedoraVariant.ATOMIC,
            capabilities=frozenset({"rpm-ostree"}),
        )

        results = GlobalSearchModel(context).all_results(SearchFilter.ACTIONS)

        self.assertNotIn("dnf-clean-all", {result.action_id for result in results})
        self.assertIn("fstrim-all", {result.action_id for result in results})

    def test_action_filter_contains_only_navigation_descriptors(self):
        results = GlobalSearchModel().all_results(SearchFilter.ACTIONS)

        self.assertTrue(results)
        self.assertTrue(
            all(result.kind is SearchResultKind.ACTION for result in results)
        )
        self.assertFalse(any(callable(value) for result in results for value in result.__dict__.values()))

    def test_action_center_results_only_target_action_center(self):
        results = [
            result
            for result in GlobalSearchModel().all_results(SearchFilter.ACTIONS)
            if result.action_id is not None
        ]

        self.assertEqual(
            {result.action_id for result in results},
            {"dnf-clean-all", "restart-failed-service", "fstrim-all"},
        )
        self.assertEqual(
            {result.route_id for result in results},
            {"maintenance:action-center"},
        )
        restart = next(
            result
            for result in results
            if result.action_id == "restart-failed-service"
        )
        self.assertEqual(restart.risk, "medium")

    def test_configured_quick_actions_become_ranked_suggestions(self):
        model = GlobalSearchModel(
            configured_quick_actions=[
                {
                    "id": "updates",
                    "label": "Update System",
                    "target_tab": "Updates",
                }
            ]
        )

        results = model.search("", search_filter=SearchFilter.ACTIONS)

        self.assertTrue(results[0].suggested)
        self.assertEqual(results[0].route_id, "maintenance:updates")

    def test_favorites_are_ranked_as_pins_without_bypassing_policy(self):
        model = GlobalSearchModel(
            NavigationContext(favorite_route_ids=frozenset({"network:dns"}))
        )

        results = model.search("dns")

        self.assertTrue(results[0].pinned)
        self.assertEqual(results[0].route_id, "network:dns")

    def test_search_is_deterministic_and_limit_is_enforced(self):
        model = GlobalSearchModel()

        first = model.search("system", limit=5)
        second = model.search("system", limit=5)

        self.assertEqual(first, second)
        self.assertLessEqual(len(first), 5)


if __name__ == "__main__":
    unittest.main()
