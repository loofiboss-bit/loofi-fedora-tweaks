"""Haven built-in plugin loader contracts."""

import unittest

from core.plugins.loader import PluginLoader
from core.plugins.registry import PluginRegistry
from core.plugins.spec import BUILTIN_PLUGIN_SPECS


class TestBuiltInPluginLoader(unittest.TestCase):
    def setUp(self):
        PluginRegistry.reset()

    def tearDown(self):
        PluginRegistry.reset()

    def test_registers_static_built_in_specs_without_importing_ui(self):
        registry = PluginRegistry.instance()
        loader = PluginLoader(registry=registry)

        registered = loader.register_builtin_specs()

        self.assertEqual(len(registered), len(BUILTIN_PLUGIN_SPECS))
        self.assertEqual(
            {spec.id for spec in registry.list_specs()},
            {spec.id for spec in BUILTIN_PLUGIN_SPECS},
        )

    def test_external_directory_is_never_scanned_or_imported(self):
        loader = PluginLoader(registry=PluginRegistry.instance())

        self.assertEqual(loader.load_external(directory="/path/that/must/not/be/read"), [])

if __name__ == "__main__":
    unittest.main()
