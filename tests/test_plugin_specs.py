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

        self.assertEqual(len(ids), 17)
        self.assertEqual(len(ids), len(set(ids)))
        self.assertIn("overview", ids)
        self.assertLess(ids.index("overview"), ids.index("atlas_dashboard"))
        self.assertNotIn("dashboard", ids)
        self.assertNotIn("ui.dashboard_tab", {spec.module for spec in BUILTIN_PLUGIN_SPECS})
        self.assertTrue(all(spec.module.startswith("ui.") for spec in BUILTIN_PLUGIN_SPECS))
        self.assertFalse(any(spec.module == "" for spec in BUILTIN_PLUGIN_SPECS))

    def test_builtin_specs_use_packaged_semantic_icons(self):
        icon_map_path = Path(__file__).parents[1] / "assets" / "icons" / "icon-map.json"
        icon_ids = set(json.loads(icon_map_path.read_text()))

        self.assertTrue(all(spec.icon in icon_ids for spec in BUILTIN_PLUGIN_SPECS))

    def test_metadata_adapter_preserves_shell_fields(self):
        spec = next(item for item in BUILTIN_PLUGIN_SPECS if item.id == "overview")

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

    def test_ui_metadata_is_projected_from_catalog_without_importing_ui(self):
        source_root = Path(__file__).parents[1] / "loofi-fedora-tweaks"

        for spec in BUILTIN_PLUGIN_SPECS:
            with self.subTest(plugin=spec.id):
                path = source_root.joinpath(*spec.module.split(".")).with_suffix(".py")
                tree = ast.parse(path.read_text())
                projected = False
                for node in tree.body:
                    if isinstance(node, ast.ClassDef) and node.name == spec.class_name:
                        candidates = []
                        for statement in node.body:
                            if (isinstance(statement, ast.Assign) and len(statement.targets) == 1
                                    and isinstance(statement.targets[0], ast.Name) and statement.targets[0].id == "_METADATA"):
                                candidates.append(statement.value)
                            elif isinstance(statement, ast.FunctionDef) and statement.name == "metadata":
                                candidates.extend(item.value for item in statement.body if isinstance(item, ast.Return))
                        projected = any(
                            isinstance(value, ast.Call)
                            and isinstance(value.func, ast.Name)
                            and value.func.id == "plugin_metadata_for_module"
                            and len(value.args) == 1
                            and isinstance(value.args[0], ast.Name)
                            and value.args[0].id == "__name__"
                            for value in candidates
                        )
                self.assertTrue(projected)


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
        self.assertEqual(len(self.loader.register_builtin_specs()), 17)
        self.assertEqual(self.loader.register_builtin_specs(), [])

    @patch("core.plugins.loader.PluginLoader._import_plugin")
    def test_load_builtin_imports_one_spec_and_reuses_instance(self, mock_import):
        self.loader.register_builtin_specs()
        plugin = MagicMock()
        plugin.metadata.return_value = next(item for item in BUILTIN_PLUGIN_SPECS if item.id == "atlas_dashboard").metadata()
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
        plugin.metadata.return_value = next(item for item in BUILTIN_PLUGIN_SPECS if item.id == "overview").metadata()
        mock_import.return_value = plugin

        with self.assertRaises(ValueError):
            self.loader.load_builtin("atlas_dashboard")

        self.assertIsNone(self.registry.get("atlas_dashboard"))


if __name__ == "__main__":
    unittest.main()
