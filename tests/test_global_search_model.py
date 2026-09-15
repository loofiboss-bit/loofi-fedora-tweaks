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


def _traditional_context(*, mode=NavigationMode.STANDARD, **kwargs):
    return NavigationContext(
        mode=mode,
        fedora_variant=FedoraVariant.TRADITIONAL,
        capabilities=frozenset({"fedora", "dnf5"}),
        **kwargs,
    )


class TestGlobalSearchModel(unittest.TestCase):
    def test_combines_routes_settings_and_actions(self):
        model = GlobalSearchModel(
            _traditional_context(),
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
            _traditional_context(),
            configured_quick_actions=[
                {"id": "gaming", "label": "Gaming Mode", "route_id": "gaming"}
            ],
        )

        route_ids = {result.route_id for result in model.all_results()}

        self.assertNotIn("gaming", route_ids)
        self.assertNotIn("settings:advanced", route_ids)

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
        results = GlobalSearchModel(_traditional_context()).all_results(SearchFilter.ACTIONS)

        self.assertTrue(results)
        self.assertTrue(
            all(result.kind is SearchResultKind.ACTION for result in results)
        )
        self.assertFalse(any(callable(value) for result in results for value in result.__dict__.values()))

    def test_action_center_results_only_target_action_center(self):
        results = [
            result
            for result in GlobalSearchModel(_traditional_context()).all_results(SearchFilter.ACTIONS)
            if result.action_id is not None
        ]

        action_ids = {result.action_id for result in results}
        self.assertTrue(
            {"dnf-clean-all", "restart-failed-service", "fstrim-all"}.issubset(
                action_ids
            )
        )
        self.assertIn("update-fedora-system", action_ids)
        self.assertIn("update-flatpaks", action_ids)
        self.assertIn("update-firmware", action_ids)
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

    def test_task_words_are_order_independent_and_use_catalog_actions(self):
        model = GlobalSearchModel(_traditional_context())

        free_space = {
            result.action_id
            for result in model.search("space free disk", search_filter=SearchFilter.ACTIONS)
        }
        updates = {
            result.action_id
            for result in model.search("updates", search_filter=SearchFilter.ACTIONS)
        }
        slow = {
            result.action_id
            for result in model.search("system slow", search_filter=SearchFilter.ACTIONS)
        }

        self.assertIn("fstrim-all", free_space)
        self.assertIn("update-fedora-system", updates)
        self.assertIn("restart-failed-service", slow)

    def test_configured_quick_actions_become_ranked_suggestions(self):
        model = GlobalSearchModel(
            _traditional_context(),
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
            _traditional_context(favorite_route_ids=frozenset({"network:dns"}))
        )

        results = model.search("dns")

        self.assertTrue(results[0].pinned)
        self.assertEqual(results[0].route_id, "network:dns")

    def test_search_is_deterministic_and_limit_is_enforced(self):
        model = GlobalSearchModel(_traditional_context())

        first = model.search("system", limit=5)
        second = model.search("system", limit=5)

        self.assertEqual(first, second)
        self.assertLessEqual(len(first), 5)

    def test_goal_search_exposes_canonical_v29_tasks_without_callbacks(self):
        model = GlobalSearchModel(_traditional_context())

        results = model.search("flatpak install")

        task = next(result for result in results if result.task_id == "install:flatpaks")
        self.assertEqual(task.route_id, "install")
        self.assertEqual(task.destination_id, "install")
        self.assertFalse(task.manual_only)
        self.assertFalse(any(callable(value) for value in task.__dict__.values()))


if __name__ == "__main__":
    unittest.main()
