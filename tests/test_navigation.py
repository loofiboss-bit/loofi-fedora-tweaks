"""Tests for the v8 Beacon navigation manifest."""

import os
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "loofi-fedora-tweaks"))


class TestNavigationManifest(unittest.TestCase):
    """Validate stable navigation route data."""

    def test_route_ids_are_unique(self):
        from core.navigation import all_routes

        route_ids = [route.id for route in all_routes()]
        self.assertEqual(len(route_ids), len(set(route_ids)))

    def test_required_subroutes_exist(self):
        from core.navigation import get_route

        required = [
            "maintenance:updates",
            "maintenance:cleanup",
            "maintenance:smart-updates",
            "maintenance:overlays",
            "system-monitor:performance",
            "system-monitor:processes",
            "software:apps",
            "software:repos",
            "software:flatpak",
            "security:overview",
            "security:firewall",
            "security:privacy",
            "security:ports",
            "network:connections",
            "network:dns",
            "network:privacy",
            "network:monitoring",
            "desktop:director",
            "desktop:theming",
            "desktop:display",
            "development:containers",
            "development:developer",
            "automation:scheduler",
            "automation:replicator",
            "community:presets",
            "community:marketplace",
            "community:plugins",
            "community:featured",
            "diagnostics:watchtower",
            "diagnostics:boot",
            "ai-lab:models",
            "loofi-link:devices",
            "virtualization:vms",
            "settings:appearance",
            "agents:dashboard",
        ]
        for route_id in required:
            self.assertIsNotNone(get_route(route_id), route_id)

    def test_legacy_alias_resolution(self):
        from core.navigation import resolve

        self.assertEqual(resolve("Updates").id, "maintenance:updates")
        self.assertEqual(resolve("Cleanup").id, "maintenance:cleanup")
        self.assertEqual(resolve("Apps").id, "software:apps")
        self.assertEqual(resolve("Repos").id, "software:repos")
        self.assertEqual(resolve("Privacy").id, "security:privacy")
        self.assertEqual(resolve("Processes").id, "system-monitor:processes")
        self.assertEqual(resolve("HP Tweaks").id, "hardware")
        self.assertEqual(resolve("monitor:processes").id, "system-monitor:processes")

    def test_risk_and_visibility_values_are_valid(self):
        from core.navigation import all_routes

        risks = {"none", "low", "medium", "high"}
        visibility = {"beginner", "advanced", "all"}
        for route in all_routes():
            self.assertIn(route.risk, risks, route)
            self.assertIn(route.visibility, visibility, route)

    def test_palette_and_quick_action_routes_are_manifest_routes(self):
        from core.navigation import all_routes, routes_for_palette, routes_for_quick_actions

        route_ids = {route.id for route in all_routes()}
        self.assertTrue({route.id for route in routes_for_palette()}.issubset(route_ids))
        self.assertTrue({route.id for route in routes_for_quick_actions()}.issubset(route_ids))

    @patch.dict(os.environ, {"QT_QPA_PLATFORM": "offscreen"})
    def test_manifest_validates_against_live_builtin_registry_and_icons(self):
        from core.navigation import all_routes, validate_routes
        from core.plugins.loader import PluginLoader
        from core.plugins.registry import PluginRegistry
        from ui.icon_pack import resolve_icon_path

        PluginRegistry.reset()
        loaded = PluginLoader().load_builtins(context={})
        try:
            self.assertIn("virtualization", loaded)
            plugin_routes = {route.id for route in all_routes() if ":" not in route.id}
            self.assertTrue(set(loaded).issubset(plugin_routes))
            self.assertEqual(validate_routes(loaded, resolve_icon_path), [])
        finally:
            PluginRegistry.reset()


if __name__ == "__main__":
    unittest.main()
