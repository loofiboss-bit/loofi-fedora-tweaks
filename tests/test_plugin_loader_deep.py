"""Focused error and compatibility coverage for the built-in loader."""

import unittest
from unittest.mock import MagicMock, patch

from core.plugins.loader import PluginLoader
from core.plugins.registry import PluginRegistry


class TestPluginLoaderCompatibility(unittest.TestCase):
    def setUp(self):
        PluginRegistry.reset()

    def tearDown(self):
        PluginRegistry.reset()

    def test_version_parser_is_total(self):
        self.assertEqual(PluginLoader._parse_version("v18.2.0"), (18, 2, 0))
        self.assertEqual(PluginLoader._parse_version(""), (0,))

    @patch("core.plugins.loader.importlib.import_module", side_effect=ImportError("missing"))
    def test_bulk_load_continues_when_ui_module_is_missing(self, _import_module):
        loader = PluginLoader(registry=PluginRegistry.instance())

        self.assertEqual(loader.load_builtins(), [])

    def test_unknown_built_in_id_is_rejected(self):
        loader = PluginLoader(registry=PluginRegistry.instance())

        with self.assertRaises(KeyError):
            loader.load_builtin("not-a-product-route")

    def test_context_is_forwarded_to_cached_instance(self):
        registry = MagicMock()
        cached = MagicMock()
        registry.get.return_value = cached
        loader = PluginLoader(registry=registry)

        self.assertIs(loader.load_builtin("cached", {"main_window": object()}), cached)
        cached.set_context.assert_called_once()


if __name__ == "__main__":
    unittest.main()
