"""Tests for v15 navigation-mode and persisted-route migrations."""

import json
import tempfile
import unittest
from pathlib import Path

from core.navigation.migrations import (
    canonical_persisted_route,
    legacy_experience_for_mode,
    migrate_last_route,
    migrate_quick_action,
    migrate_quick_actions,
    migrate_route_references,
    navigation_mode_from_value,
)
from core.navigation.models import NavigationMode
from utils.settings import SettingsManager, migrate_settings


class TestModeMigration(unittest.TestCase):
    def test_v14_levels_map_to_two_v15_modes(self):
        expected = {
            "beginner": NavigationMode.STANDARD,
            "intermediate": NavigationMode.ADVANCED,
            "advanced": NavigationMode.ADVANCED,
            "standard": NavigationMode.STANDARD,
            None: NavigationMode.STANDARD,
            "bad": NavigationMode.STANDARD,
        }
        for value, mode in expected.items():
            with self.subTest(value=value):
                self.assertEqual(navigation_mode_from_value(value), mode)

    def test_mode_migration_is_idempotent(self):
        for mode in NavigationMode:
            with self.subTest(mode=mode):
                self.assertIs(navigation_mode_from_value(mode), mode)
                self.assertIs(
                    navigation_mode_from_value(mode.value),
                    mode,
                )

    def test_v14_shell_adapter_is_explicit(self):
        self.assertEqual(
            legacy_experience_for_mode(NavigationMode.STANDARD),
            "beginner",
        )
        self.assertEqual(
            legacy_experience_for_mode(NavigationMode.ADVANCED),
            "advanced",
        )


class TestRouteMigration(unittest.TestCase):
    def test_aliases_become_canonical_routes(self):
        self.assertEqual(
            canonical_persisted_route("Updates"),
            "maintenance:updates",
        )

    def test_dashboard_persistence_redirects_to_system_overview(self):
        self.assertEqual(canonical_persisted_route("dashboard"), "system_info")
        self.assertEqual(migrate_last_route("dashboard"), "system_info")

    def test_invalid_last_route_falls_back_to_home(self):
        self.assertEqual(migrate_last_route("missing-route"), "atlas_dashboard")
        self.assertEqual(migrate_last_route(None), "atlas_dashboard")

    def test_route_collections_deduplicate_and_preserve_unknown_state(self):
        migrated = migrate_route_references(
            ["dashboard", "system_info", "Updates", "future:route", "future:route"]
        )

        self.assertEqual(
            migrated,
            ["system_info", "maintenance:updates", "future:route"],
        )

    def test_non_collection_route_state_returns_empty_list(self):
        self.assertEqual(migrate_route_references("maintenance:updates"), [])
        self.assertEqual(migrate_route_references(None), [])


class TestQuickActionMigration(unittest.TestCase):
    def test_legacy_target_tab_migrates_without_mutating_input(self):
        action = {"id": "cleanup", "target_tab": "Cleanup"}

        migrated = migrate_quick_action(action)

        self.assertEqual(action, {"id": "cleanup", "target_tab": "Cleanup"})
        self.assertEqual(
            migrated,
            {"id": "cleanup", "route_id": "maintenance:cleanup"},
        )

    def test_dashboard_quick_action_uses_compatibility_target(self):
        action = {"id": "overview", "route_id": "dashboard"}

        self.assertEqual(
            migrate_quick_action(action)["route_id"],
            "system_info",
        )

    def test_quick_action_migration_is_idempotent_and_ignores_bad_entries(self):
        raw = [
            {"id": "updates", "target_tab": "Updates"},
            "bad",
        ]
        first = migrate_quick_actions(raw)
        second = migrate_quick_actions(first)

        self.assertEqual(first, second)
        self.assertEqual(len(first), 1)

    def test_invalid_quick_action_inputs_fail_closed(self):
        self.assertEqual(migrate_quick_actions({"id": "not-a-list"}), [])
        self.assertEqual(
            migrate_quick_action({"id": "bad", "target_tab": "missing-route"}),
            {"id": "bad"},
        )


class TestSettingsNavigationMigration(unittest.TestCase):
    def test_existing_v14_settings_gain_mode_and_last_route(self):
        migrated, changed = migrate_settings(
            {
                "experience_level": "intermediate",
                "last_route": "dashboard",
                "favorite_routes": ["Home", "dashboard", "future:route"],
                "state_schema_version": 1,
            }
        )

        self.assertTrue(changed)
        self.assertEqual(migrated["experience_level"], "advanced")
        self.assertEqual(migrated["navigation_mode"], "advanced")
        self.assertEqual(migrated["last_route_id"], "system_info")
        self.assertEqual(
            migrated["favorite_routes"],
            ["atlas_dashboard", "system_info", "future:route"],
        )

    def test_new_mode_is_source_of_truth_for_legacy_shell_adapter(self):
        standard, _ = migrate_settings(
            {"navigation_mode": "standard", "experience_level": "advanced"}
        )
        advanced, _ = migrate_settings(
            {"navigation_mode": "advanced", "experience_level": "beginner"}
        )

        self.assertEqual(standard["experience_level"], "beginner")
        self.assertEqual(advanced["experience_level"], "advanced")

    def test_hidden_routes_use_same_idempotent_route_adapter(self):
        first, _ = migrate_settings(
            {
                "hidden_routes": ["dashboard", "Updates", "future:route"],
            }
        )
        second, changed = migrate_settings(first)

        self.assertEqual(
            first["hidden_routes"],
            ["system_info", "maintenance:updates", "future:route"],
        )
        self.assertFalse(changed)
        self.assertEqual(first, second)

    def test_settings_migration_is_idempotent(self):
        first, first_changed = migrate_settings(
            {
                "experienceLevel": "intermediate",
                "last_active_route": "Updates",
                "favorites": ["Home", "dashboard"],
            }
        )
        second, second_changed = migrate_settings(first)

        self.assertTrue(first_changed)
        self.assertFalse(second_changed)
        self.assertEqual(first, second)

    def test_manager_persists_migrated_schema(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "settings.json"
            path.write_text(
                json.dumps(
                    {
                        "experience_level": "intermediate",
                        "last_route_id": "dashboard",
                    }
                )
            )

            manager = SettingsManager(settings_path=path)
            saved = json.loads(path.read_text())

            self.assertEqual(manager.get("navigation_mode"), "advanced")
            self.assertEqual(manager.get("last_route_id"), "system_info")
            self.assertEqual(saved, manager.all())


if __name__ == "__main__":
    unittest.main()
