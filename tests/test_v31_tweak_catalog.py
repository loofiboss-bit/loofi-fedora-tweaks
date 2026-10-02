"""Regression tests for v31 tweak catalog extensions (GNOME, KDE, DNF5)."""

from __future__ import annotations

import unittest
from types import SimpleNamespace

from core.actions.catalog import ActionCatalog
from core.executor.command_policy import validate_command_vector
from core.tasks.tweaks import (
    BY_ID,
    TWEAKS,
    command_for,
    read_tweak,
    visible_tweaks,
)
from core.tweak_commands import (
    gnome_schema,
    valid_value,
    values_equal,
)
from test_tweaks_v30_1 import FakeRuntime, profile


class TestV31TweakCatalog(unittest.TestCase):
    """Verify newly introduced v31 tweaks across GNOME, KDE, and DNF5."""

    def test_new_gnome_tweaks_schema_and_command_validation(self) -> None:
        new_gnome_keys = {
            "gnome-button-layout": ("org.gnome.desktop.wm.preferences", "button-layout"),
            "gnome-tap-to-click": ("org.gnome.desktop.peripherals.touchpad", "tap-to-click"),
            "gnome-night-light": ("org.gnome.settings-daemon.plugins.color", "night-light-enabled"),
            "gnome-sound-overamp": ("org.gnome.desktop.sound", "allow-volume-above-100-percent"),
            "gnome-font-antialiasing": ("org.gnome.desktop.interface", "font-antialiasing"),
        }
        for tweak_id, (expected_schema, expected_key) in new_gnome_keys.items():
            tweak = BY_ID[tweak_id]
            self.assertEqual(tweak.desktop, "gnome")
            self.assertEqual(gnome_schema(tweak_id), expected_schema)

            for value, _label in tweak.choices:
                self.assertTrue(valid_value(tweak_id, value))
                cmd = command_for(tweak, value)
                validate_command_vector(cmd)
                self.assertEqual(cmd[0], "gsettings")
                self.assertEqual(cmd[1], "set")
                self.assertEqual(cmd[2], expected_schema)
                self.assertEqual(cmd[3], expected_key)

            with self.assertRaises(ValueError):
                command_for(tweak, "invalid-malicious-value")

    def test_new_kde_tweaks_specs_and_command_validation(self) -> None:
        new_kde_keys = {
            "kde-tap-to-click": ("kcminputrc", "Touchpad", "TapToClick"),
            "kde-night-color": ("kwinrc", "NightColor", "Active"),
        }
        for tweak_id, (file_name, group, key) in new_kde_keys.items():
            tweak = BY_ID[tweak_id]
            self.assertEqual(tweak.desktop, "kde")

            for value, _label in tweak.choices:
                self.assertTrue(valid_value(tweak_id, value))
                cmd = command_for(tweak, value)
                validate_command_vector(cmd)
                self.assertEqual(cmd[0], "kwriteconfig6")
                self.assertIn("--file", cmd)
                self.assertIn(file_name, cmd)
                self.assertIn("--group", cmd)
                self.assertIn(group, cmd)
                self.assertIn("--key", cmd)
                self.assertIn(key, cmd)

            with self.assertRaises(ValueError):
                command_for(tweak, "unexpected-value")

    def test_dnf_parallel_downloads_properties_and_execution(self) -> None:
        tweak = BY_ID["dnf-parallel-downloads"]
        self.assertEqual(tweak.desktop, "all")
        self.assertTrue(tweak.privileged)
        self.assertEqual(tweak.group, "System & Packaging")

        # Test command generation
        for val, _ in tweak.choices:
            self.assertTrue(valid_value(tweak.id, val))
            cmd = command_for(tweak, val)
            self.assertEqual(cmd, ["dnf5", "config-manager", "setopt", f"max_parallel_downloads={val}"])

        with self.assertRaises(ValueError):
            command_for(tweak, "999")

        # Test reading with dnf dump mock
        runtime = FakeRuntime("gnome")
        state = read_tweak(tweak, runtime.platform_profile(), runtime.execute_read_only)
        self.assertEqual(state.status, "ready")
        self.assertEqual(state.value, "10")

        # Test atomic fedora marks dnf tweak unavailable
        atomic_prof = SimpleNamespace(
            is_fedora=True,
            is_atomic=True,
            desktop=SimpleNamespace(value="gnome"),
            deployment_backend=SimpleNamespace(value="rpm_ostree"),
        )
        atomic_state = read_tweak(tweak, atomic_prof, runtime.execute_read_only)
        self.assertEqual(atomic_state.status, "unavailable")

    def test_action_catalog_contains_all_v31_actions(self) -> None:
        catalog = ActionCatalog()
        v31_tweak_ids = [
            "gnome-button-layout",
            "gnome-tap-to-click",
            "gnome-night-light",
            "gnome-sound-overamp",
            "gnome-font-antialiasing",
            "kde-tap-to-click",
            "kde-night-color",
            "dnf-parallel-downloads",
        ]
        for tid in v31_tweak_ids:
            tweak = BY_ID[tid]
            action_def = catalog.get(tweak.action_id)
            self.assertIsNotNone(action_def, f"ActionDefinition missing for {tweak.action_id}")
            self.assertEqual(action_def.id, tweak.action_id)

            restore_id = f"restore-{tid}"
            restore_def = catalog.get(restore_id)
            self.assertIsNotNone(restore_def, f"Restore ActionDefinition missing for {restore_id}")
            self.assertEqual(restore_def.id, restore_id)

            if tweak.privileged:
                self.assertTrue(action_def.privileged)
                self.assertEqual(action_def.risk_level, "medium")
                self.assertEqual(action_def.interaction_policy, "confirm")
            else:
                self.assertFalse(action_def.privileged)
                self.assertEqual(action_def.risk_level, "low")
                self.assertEqual(action_def.interaction_policy, "automatic")
