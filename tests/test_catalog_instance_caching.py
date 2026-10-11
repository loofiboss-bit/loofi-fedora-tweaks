"""Static catalog cache contracts and per-instance mutable schema isolation."""

from __future__ import annotations

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "loofi-fedora-tweaks"))

from core.actions.catalog import ActionCatalog  # noqa: E402
from core.product_catalog import (  # noqa: E402
    catalog_entry,
    catalog_plugins,
    catalog_routes,
    plugin_metadata_for_module,
    product_catalog,
)
from core.tasks.catalog import TaskCatalog  # noqa: E402


class TestCatalogCachingContracts(unittest.TestCase):
    def test_product_entries_and_indexes_are_built_once_in_catalog_order(self) -> None:
        first = product_catalog()
        second = product_catalog()
        self.assertIs(first, second)
        self.assertTrue(all(catalog_entry(entry.route_id) is entry for entry in first))
        self.assertEqual(
            tuple(entry.route_id for entry in first),
            tuple(route.id for route in catalog_routes() if catalog_entry(route.id) is not None),
        )

    def test_plugin_module_index_preserves_legacy_projection_and_lookup_error(self) -> None:
        for plugin in catalog_plugins():
            with self.subTest(module=plugin.module):
                self.assertEqual(plugin_metadata_for_module(plugin.module).id, plugin.id)
                self.assertEqual(
                    plugin_metadata_for_module(f"loofi-fedora-tweaks.{plugin.module}").id,
                    plugin.id,
                )
        with self.assertRaisesRegex(LookupError, "no product catalog plugin for module"):
            plugin_metadata_for_module("missing.plugin")

    def test_default_action_definitions_share_static_work_but_not_mutable_schemas(self) -> None:
        first = ActionCatalog()
        second = ActionCatalog()
        first_definition = first.get("restart-failed-service")
        second_definition = second.get("restart-failed-service")
        assert first_definition is not None and second_definition is not None
        self.assertIsNot(first_definition, second_definition)
        self.assertIsNot(first_definition.parameter_schema, second_definition.parameter_schema)
        self.assertIsNot(
            first_definition.parameter_schema["service"],
            second_definition.parameter_schema["service"],
        )
        self.assertEqual(first.list(), second.list())
        first_definition.parameter_schema["service"]["required"] = False
        self.assertTrue(second_definition.parameter_schema["service"]["required"])

    def test_injected_action_definitions_remain_the_supplied_definitions(self) -> None:
        definition = ActionCatalog().get("restart-failed-service")
        assert definition is not None
        injected = ActionCatalog([definition])
        self.assertIs(injected.get(definition.id), definition)
        self.assertEqual([item.id for item in injected.list()], [definition.id])

    def test_default_task_descriptors_are_cached_and_injected_catalogs_stay_isolated(self) -> None:
        first = TaskCatalog(include_action_guidance=False)
        second = TaskCatalog(include_action_guidance=False)
        first_tasks = first.all()
        second_tasks = second.all()
        self.assertEqual(first_tasks, second_tasks)
        self.assertIs(first_tasks[0], second_tasks[0])

        injected = TaskCatalog([first_tasks[0]])
        self.assertIs(injected.get(first_tasks[0].id), first_tasks[0])
        self.assertEqual(injected.all(), (first_tasks[0],))
        schema = first.get("install:applications").parameter_schema
        other_schema = second.get("install:applications").parameter_schema
        self.assertIsNot(schema, other_schema)
        schema["source"]["required"] = False
        self.assertTrue(other_schema["source"]["required"])


if __name__ == "__main__":
    unittest.main()
