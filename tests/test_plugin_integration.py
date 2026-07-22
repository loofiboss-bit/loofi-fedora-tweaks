"""Integration contracts for Haven's built-in-only product catalog."""

import unittest

from core.plugins.loader import PluginLoader
from core.plugins.registry import PluginRegistry
from core.product_catalog import product_catalog, validate_product_catalog


class TestProductCatalogIntegration(unittest.TestCase):
    def setUp(self):
        PluginRegistry.reset()

    def tearDown(self):
        PluginRegistry.reset()

    def test_catalog_reconciles_all_navigation_views(self):
        catalog = {entry.route_id: entry for entry in product_catalog()}

        self.assertEqual(validate_product_catalog(), [])
        self.assertIn("community:marketplace", catalog)
        self.assertFalse(catalog["community:marketplace"].placement.discoverable)
        self.assertEqual(catalog["community:marketplace"].compatibility_redirect, "community:presets")

    def test_static_specs_register_without_constructing_widgets(self):
        registry = PluginRegistry.instance()

        PluginLoader(registry=registry).register_builtin_specs()

        self.assertGreater(len(registry.list_specs()), 0)
        self.assertEqual(registry.list_all(), [])


if __name__ == "__main__":
    unittest.main()
