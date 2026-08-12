"""v25 Proof Safety & Execution settings contracts."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from core.settings.execution import (
    EXECUTION_SETTINGS_SCHEMA,
    ExecutionSettings,
    ExecutionSettingsFutureSchemaError,
    ExecutionSettingsStore,
)


class TestExecutionSettings(unittest.TestCase):
    def test_missing_settings_use_direct_defaults(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            store = ExecutionSettingsStore(Path(temp_dir) / "execution-settings.json")
            settings = store.load()
            self.assertEqual(settings.effective_mode, "direct")
            self.assertTrue(settings.confirm_medium_risk)
            self.assertTrue(settings.automatically_verify)

    def test_settings_are_versioned_and_round_trip_atomically(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "execution-settings.json"
            store = ExecutionSettingsStore(path)
            store.update(execution_mode="review_first", show_command_preview=False)
            payload = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(payload["schema"], EXECUTION_SETTINGS_SCHEMA)
            self.assertEqual(payload["schema_version"], 1)
            self.assertFalse(payload["show_command_preview"])
            self.assertEqual(store.load().execution_mode, "review_first")

    def test_legacy_payload_is_migrated_without_new_execution_authority(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "execution-settings.json"
            path.write_text(
                json.dumps({"confirm_dangerous_actions": False, "mode": "review_first"}),
                encoding="utf-8",
            )
            store = ExecutionSettingsStore(path)
            settings = store.load()
            self.assertEqual(settings.execution_mode, "review_first")
            self.assertFalse(settings.confirm_medium_risk)
            self.assertEqual(json.loads(path.read_text(encoding="utf-8"))["schema_version"], 1)

    def test_future_schema_is_read_only_and_forces_review_first(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "execution-settings.json"
            original = {"schema": "loofi.execution-settings/v99", "schema_version": 99, "execution_mode": "direct"}
            path.write_text(json.dumps(original), encoding="utf-8")
            store = ExecutionSettingsStore(path)
            settings = store.load()
            self.assertTrue(settings.future_schema)
            self.assertEqual(settings.effective_mode, "review_first")
            with self.assertRaises(ExecutionSettingsFutureSchemaError):
                store.save(ExecutionSettings())
            self.assertEqual(json.loads(path.read_text(encoding="utf-8")), original)

    def test_unknown_update_key_is_rejected(self) -> None:
        store = ExecutionSettingsStore(Path(tempfile.mkdtemp()) / "execution-settings.json")
        with self.assertRaises(ValueError):
            store.update(arbitrary_authority=True)

    def test_malformed_schema_version_is_read_only_and_forces_review_first(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "execution-settings.json"
            original = {"schema": EXECUTION_SETTINGS_SCHEMA, "schema_version": "future", "execution_mode": "direct"}
            path.write_text(json.dumps(original), encoding="utf-8")
            store = ExecutionSettingsStore(path)

            settings = store.load()

            self.assertTrue(settings.future_schema)
            self.assertEqual(settings.effective_mode, "review_first")
            self.assertEqual(json.loads(path.read_text(encoding="utf-8")), original)


if __name__ == "__main__":
    unittest.main()
