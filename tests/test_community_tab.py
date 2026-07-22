"""Haven local-profile and legacy-extension safety contracts."""

import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import MagicMock

from cli.commands.plugin_commands import handle_plugins
from core.plugins.legacy import LegacyExtensionService


class TestLegacyExtensionService(unittest.TestCase):
    def test_inventory_never_imports_or_modifies_extension_code(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            extension = root / "example"
            extension.mkdir()
            executable = extension / "plugin.py"
            executable.write_text("raise RuntimeError('must never execute')")
            (extension / "plugin.json").write_text("{}")

            records = LegacyExtensionService.list_extensions(root)

            self.assertEqual(records[0].name, "example")
            self.assertTrue(records[0].manifest_present)
            self.assertEqual(executable.read_text(), "raise RuntimeError('must never execute')")

    def test_export_is_data_only_and_private(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "example").mkdir()
            destination = root / "legacy.json"

            LegacyExtensionService.export_manifest(destination, root)

            payload = json.loads(destination.read_text())
            self.assertEqual(payload["execution"], "disabled")
            self.assertEqual(destination.stat().st_mode & 0o777, 0o600)


class TestLegacyPluginCli(unittest.TestCase):
    def test_enable_returns_machine_readable_retirement(self):
        output_json = MagicMock()
        result = handle_plugins(
            SimpleNamespace(action="enable", name="example"),
            True,
            output_json,
            MagicMock(),
            LegacyExtensionService,
        )

        self.assertEqual(result, 2)
        self.assertEqual(output_json.call_args.args[0]["error"], "feature_retired")


if __name__ == "__main__":
    unittest.main()
