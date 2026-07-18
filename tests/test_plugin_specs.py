"""Tests for data-only built-in plugin specifications and lazy instances."""

import ast
import json
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from core.plugins.loader import PluginLoader
from core.plugins.registry import PluginRegistry
from core.plugins.spec import BUILTIN_PLUGIN_SPECS, PluginSpec


class TestPluginSpec(unittest.TestCase):
    def test_builtin_specs_are_complete_unique_and_data_only(self):
        ids = [spec.id for spec in BUILTIN_PLUGIN_SPECS]

        self.assertEqual(len(ids), 28)
        self.assertEqual(len(ids), len(set(ids)))
        self.assertNotIn("dashboard", ids)
        self.assertNotIn("ui.dashboard_tab", {spec.module for spec in BUILTIN_PLUGIN_SPECS})
        self.assertTrue(all(spec.module.startswith("ui.") for spec in BUILTIN_PLUGIN_SPECS))
        self.assertFalse(any(spec.module == "" for spec in BUILTIN_PLUGIN_SPECS))

    def test_builtin_specs_use_packaged_semantic_icons(self):
        icon_map_path = Path(__file__).parents[1] / "assets" / "icons" / "icon-map.json"
        icon_ids = set(json.loads(icon_map_path.read_text()))

        self.assertTrue(all(spec.icon in icon_ids for spec in BUILTIN_PLUGIN_SPECS))

    def test_metadata_adapter_preserves_shell_fields(self):
        spec = BUILTIN_PLUGIN_SPECS[0]

        metadata = spec.metadata()

        self.assertEqual(metadata.id, spec.id)
        self.assertEqual(metadata.name, spec.name)
        self.assertEqual(metadata.description, spec.description)
        self.assertEqual(metadata.category, spec.category)
        self.assertEqual(metadata.order, spec.order)

    def test_invalid_spec_fails_closed(self):
        with self.assertRaises(ValueError):
            PluginSpec(
                id="",
                name="Broken",
                description="",
                icon="",
                destination_id="home",
                module="ui.broken",
                class_name="Broken",
            )

    def test_spec_ids_match_runtime_metadata_without_importing_ui(self):
        source_root = Path(__file__).parents[1] / "loofi-fedora-tweaks"

        for spec in BUILTIN_PLUGIN_SPECS:
            with self.subTest(plugin=spec.id):
                path = source_root.joinpath(*spec.module.split(".")).with_suffix(".py")
                tree = ast.parse(path.read_text())
                runtime_id = None
                runtime_icon = None
                for node in tree.body:
                    if isinstance(node, ast.ClassDef) and node.name == spec.class_name:
                        for statement in node.body:
                            if not isinstance(statement, ast.Assign):
                                continue
                            if not any(
                                isinstance(target, ast.Name) and target.id == "_METADATA"
                                for target in statement.targets
                            ):
                                continue
                            for keyword in statement.value.keywords:
                                if keyword.arg == "id":
                                    runtime_id = ast.literal_eval(keyword.value)
                                if keyword.arg == "icon":
                                    runtime_icon = ast.literal_eval(keyword.value)
                self.assertEqual(runtime_id, spec.id)
                self.assertEqual(runtime_icon, spec.icon)


class TestPluginSpecRegistry(unittest.TestCase):
    def setUp(self):
        self.registry = PluginRegistry()
        self.loader = PluginLoader(registry=self.registry)

    def test_register_specs_does_not_import_ui_modules_or_create_instances(self):
        specialist_modules = {spec.module for spec in BUILTIN_PLUGIN_SPECS if spec.component == "specialist"}
        before = specialist_modules.intersection(sys.modules)

        registered = self.loader.register_builtin_specs()

        self.assertEqual(len(registered), len(BUILTIN_PLUGIN_SPECS))
        self.assertEqual(len(self.registry.list_specs()), len(BUILTIN_PLUGIN_SPECS))
        self.assertEqual(self.registry.list_all(), [])
        self.assertEqual(specialist_modules.intersection(sys.modules), before)

    def test_register_specs_is_idempotent(self):
        self.assertEqual(len(self.loader.register_builtin_specs()), 28)
        self.assertEqual(self.loader.register_builtin_specs(), [])

    @patch("core.plugins.loader.PluginLoader._import_plugin")
    def test_load_builtin_imports_one_spec_and_reuses_instance(self, mock_import):
        self.loader.register_builtin_specs()
        plugin = MagicMock()
        plugin.metadata.return_value = BUILTIN_PLUGIN_SPECS[0].metadata()
        mock_import.return_value = plugin

        first = self.loader.load_builtin("atlas_dashboard", context={"main_window": object()})
        second = self.loader.load_builtin("atlas_dashboard")

        self.assertIs(first, plugin)
        self.assertIs(second, plugin)
        mock_import.assert_called_once_with("ui.atlas_dashboard_tab", "AtlasDashboardTab")
        plugin.set_context.assert_called_once()
        self.assertEqual(len(self.registry.list_all()), 1)

    @patch("core.plugins.loader.PluginLoader._import_plugin")
    def test_runtime_id_mismatch_is_not_cached(self, mock_import):
        self.loader.register_builtin_specs()
        plugin = MagicMock()
        plugin.metadata.return_value = BUILTIN_PLUGIN_SPECS[1].metadata()
        mock_import.return_value = plugin

        with self.assertRaises(ValueError):
            self.loader.load_builtin("atlas_dashboard")

        self.assertIsNone(self.registry.get("atlas_dashboard"))


if __name__ == "__main__":
    unittest.main()
