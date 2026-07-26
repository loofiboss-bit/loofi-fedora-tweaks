"""
Tests for utils/settings.py - SettingsManager.
Covers: singleton, defaults, get/set, save/load round-trip,
reset, corrupt JSON recovery, and unknown-key handling.
"""

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

# Add source path to sys.path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'loofi-fedora-tweaks'))

from utils.settings import SettingsManager, AppSettings, KNOWN_KEYS, STATE_SCHEMA_VERSION, migrate_settings


# ---------------------------------------------------------------------------
# Helper: create a SettingsManager with a temp file
# ---------------------------------------------------------------------------

def _make_manager(tmpdir: str, initial: dict = None) -> SettingsManager:
    """Create a SettingsManager backed by a file inside *tmpdir*."""
    path = Path(tmpdir) / "settings.json"
    if initial is not None:
        path.write_text(json.dumps(initial, indent=2))
    return SettingsManager(settings_path=path)


# ---------------------------------------------------------------------------
# TestDefaults - verify AppSettings defaults
# ---------------------------------------------------------------------------

class TestDefaults(unittest.TestCase):
    """AppSettings dataclass should expose sane defaults."""

    def test_default_theme_is_dark(self):
        self.assertEqual(AppSettings().theme, "dark")

    def test_default_follow_system_is_true(self):
        self.assertTrue(AppSettings().follow_system_theme)

    def test_default_start_minimized_is_false(self):
        self.assertFalse(AppSettings().start_minimized)

    def test_default_show_notifications_is_true(self):
        self.assertTrue(AppSettings().show_notifications)

    def test_default_confirm_dangerous_is_true(self):
        self.assertTrue(AppSettings().confirm_dangerous_actions)

    def test_default_log_level_is_info(self):
        self.assertEqual(AppSettings().log_level, "INFO")

    def test_retired_plugin_analytics_is_not_persisted(self):
        self.assertNotIn("plugin_analytics_enabled", KNOWN_KEYS)
        self.assertNotIn("plugin_analytics_anonymous_id", KNOWN_KEYS)

    def test_default_state_contract_is_empty_and_versioned(self):
        defaults = AppSettings()
        self.assertEqual(defaults.favorite_routes, [])
        self.assertEqual(defaults.hidden_routes, [])
        self.assertEqual(defaults.navigation_mode, "standard")
        self.assertEqual(defaults.last_route_id, "atlas_dashboard")
        self.assertEqual(defaults.window_geometry, {})
        self.assertEqual(defaults.state_schema_version, STATE_SCHEMA_VERSION)

    def test_known_keys_match_dataclass_fields(self):
        from dataclasses import fields
        field_names = {f.name for f in fields(AppSettings)}
        self.assertEqual(KNOWN_KEYS, field_names)

    def test_legacy_explicit_theme_does_not_switch_to_system_theme(self):
        migrated, changed = migrate_settings({"theme": "light"})

        self.assertTrue(changed)
        self.assertEqual(migrated["theme"], "light")
        self.assertFalse(migrated["follow_system_theme"])


# ---------------------------------------------------------------------------
# TestSingleton - singleton behaviour
# ---------------------------------------------------------------------------

class TestSingleton(unittest.TestCase):
    """SettingsManager.instance() returns the same object."""

    def setUp(self):
        SettingsManager._reset_instance()

    def tearDown(self):
        SettingsManager._reset_instance()

    def test_instance_returns_same_object(self):
        a = SettingsManager.instance()
        b = SettingsManager.instance()
        self.assertIs(a, b)

    def test_reset_clears_singleton(self):
        a = SettingsManager.instance()
        SettingsManager._reset_instance()
        b = SettingsManager.instance()
        self.assertIsNot(a, b)


# ---------------------------------------------------------------------------
# TestGetSet - get / set / all
# ---------------------------------------------------------------------------

class TestGetSet(unittest.TestCase):
    """Basic get and set operations."""

    def test_get_default_theme(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            mgr = _make_manager(tmpdir)
            self.assertEqual(mgr.get("theme"), "dark")

    def test_set_and_get(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            mgr = _make_manager(tmpdir)
            mgr.set("theme", "light")
            self.assertEqual(mgr.get("theme"), "light")

    def test_set_unknown_key_raises(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            mgr = _make_manager(tmpdir)
            with self.assertRaises(KeyError):
                mgr.set("nonexistent_key", 42)

    def test_legacy_experience_key_is_no_longer_writable(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            mgr = _make_manager(tmpdir)
            with self.assertRaises(KeyError):
                mgr.set("experience_level", "advanced")

    def test_get_unknown_key_raises(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            mgr = _make_manager(tmpdir)
            with self.assertRaises(KeyError):
                mgr.get("nonexistent_key")

    def test_get_unknown_key_with_default(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            mgr = _make_manager(tmpdir)
            self.assertEqual(mgr.get("nonexistent_key", "fallback"), "fallback")

    def test_all_returns_copy(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            mgr = _make_manager(tmpdir)
            all_settings = mgr.all()
            all_settings["theme"] = "MODIFIED"
            # Original should be unchanged
            self.assertEqual(mgr.get("theme"), "dark")

    def test_all_contains_all_known_keys(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            mgr = _make_manager(tmpdir)
            self.assertEqual(set(mgr.all().keys()), KNOWN_KEYS)


# ---------------------------------------------------------------------------
# TestSaveLoad - persistence round-trip
# ---------------------------------------------------------------------------

class TestSaveLoad(unittest.TestCase):
    """Save and load round-trip."""

    def test_save_creates_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "settings.json"
            mgr = SettingsManager(settings_path=path)
            self.assertTrue(mgr.save())
            self.assertTrue(path.exists())

    @patch("pathlib.Path.write_text", side_effect=OSError("read-only"))
    def test_save_reports_persistence_failure(self, _mock_write_text):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "settings.json"
            mgr = SettingsManager(settings_path=path)

            self.assertFalse(mgr.save())

    def test_save_load_round_trip(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "settings.json"

            mgr1 = SettingsManager(settings_path=path)
            mgr1.set("theme", "light")
            mgr1.set("start_minimized", True)
            mgr1.save()

            mgr2 = SettingsManager(settings_path=path)
            self.assertEqual(mgr2.get("theme"), "light")
            self.assertTrue(mgr2.get("start_minimized"))

    def test_saved_json_is_valid(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "settings.json"
            mgr = SettingsManager(settings_path=path)
            mgr.save()

            raw = json.loads(path.read_text())
            self.assertIsInstance(raw, dict)
            self.assertIn("theme", raw)

    def test_save_creates_parent_dirs(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "sub" / "dir" / "settings.json"
            mgr = SettingsManager(settings_path=path)
            mgr.save()
            self.assertTrue(path.exists())

    def test_retired_plugin_analytics_keys_are_rejected(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "settings.json"
            manager = SettingsManager(settings_path=path)
            with self.assertRaises(KeyError):
                manager.set("plugin_analytics_enabled", True)


# ---------------------------------------------------------------------------
# TestCorruptFile - recovery from bad data
# ---------------------------------------------------------------------------

class TestCorruptFile(unittest.TestCase):
    """Corrupt settings files should fall back to defaults."""

    def test_corrupt_json_uses_defaults(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "settings.json"
            path.write_text("not valid json{{{")

            mgr = SettingsManager(settings_path=path)
            self.assertEqual(mgr.get("theme"), "dark")
            self.assertTrue(mgr.get("show_notifications"))

    def test_non_dict_json_uses_defaults(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "settings.json"
            path.write_text('"just a string"')

            mgr = SettingsManager(settings_path=path)
            self.assertEqual(mgr.get("theme"), "dark")

    def test_missing_file_uses_defaults(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "does_not_exist.json"
            mgr = SettingsManager(settings_path=path)
            self.assertEqual(mgr.get("theme"), "dark")

    def test_extra_keys_in_file_are_ignored(self):
        """Unknown keys sitting in the JSON file should not leak in."""
        with tempfile.TemporaryDirectory() as tmpdir:
            data = {"theme": "light", "unknown_future_key": True}
            mgr = _make_manager(tmpdir, initial=data)
            self.assertEqual(mgr.get("theme"), "light")
            self.assertNotIn("unknown_future_key", mgr.all())


# ---------------------------------------------------------------------------
# TestStateMigration - v9 app state contract
# ---------------------------------------------------------------------------

class TestStateMigration(unittest.TestCase):
    """Legacy UI state should migrate to canonical JSON-safe settings keys."""

    def test_theme_and_experience_migrate_from_legacy_nested_keys(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            mgr = _make_manager(tmpdir, initial={
                "ui": {
                    "theme": "light",
                    "experience_level": "advanced",
                },
            })

            self.assertEqual(mgr.get("theme"), "light")
            self.assertEqual(mgr.get("navigation_mode"), "advanced")
            self.assertNotIn("experience_level", mgr.all())
            self.assertEqual(mgr.get("state_schema_version"), STATE_SCHEMA_VERSION)

    def test_favorites_and_hidden_routes_migrate_from_navigation_state(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            mgr = _make_manager(tmpdir, initial={
                "navigation": {
                    "favorites": ["home", "home", "maintenance:updates"],
                    "hidden_routes": ["settings:advanced", "", "system:hardware"],
                },
            })

            self.assertEqual(mgr.get("favorite_routes"), ["atlas_dashboard", "maintenance:updates"])
            self.assertEqual(mgr.get("hidden_routes"), ["settings:advanced", "system:hardware"])

    def test_window_geometry_migrates_from_legacy_list(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            mgr = _make_manager(tmpdir, initial={"geometry": [10, 20, 1280, 720]})

            self.assertEqual(mgr.get("window_geometry"), {
                "x": 10,
                "y": 20,
                "width": 1280,
                "height": 720,
            })

    def test_settings_migration_is_idempotent(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "settings.json"
            legacy = {
                "appearance": {"theme": "highcontrast"},
                "experienceLevel": "intermediate",
                "favorite_tabs": ["software:apps"],
                "hiddenRoutes": ["settings:advanced"],
                "main_window_geometry": {"x": 1, "y": 2, "width": 800, "height": 600, "extra": "drop"},
            }
            path.write_text(json.dumps(legacy, indent=2))

            first = SettingsManager(settings_path=path).all()
            second = SettingsManager(settings_path=path).all()

            self.assertEqual(first, second)
            self.assertEqual(second["theme"], "highcontrast")
            self.assertEqual(second["navigation_mode"], "advanced")
            self.assertEqual(second["favorite_routes"], ["software:apps"])
            self.assertEqual(second["hidden_routes"], ["settings:advanced"])
            self.assertEqual(second["window_geometry"], {"x": 1, "y": 2, "width": 800, "height": 600})


# ---------------------------------------------------------------------------
# TestReset - reset to defaults
# ---------------------------------------------------------------------------

class TestReset(unittest.TestCase):
    """reset() restores defaults and persists."""

    def test_reset_restores_defaults(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            mgr = _make_manager(tmpdir)
            mgr.set("theme", "light")
            mgr.set("start_minimized", True)
            self.assertTrue(mgr.reset())

            self.assertEqual(mgr.get("theme"), "dark")
            self.assertFalse(mgr.get("start_minimized"))

    def test_reset_persists_to_disk(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "settings.json"
            mgr = SettingsManager(settings_path=path)
            mgr.set("theme", "light")
            mgr.reset()

            # Reload from disk
            mgr2 = SettingsManager(settings_path=path)
            self.assertEqual(mgr2.get("theme"), "dark")


if __name__ == '__main__':
    unittest.main()
