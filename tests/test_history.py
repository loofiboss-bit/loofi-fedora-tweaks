"""Tests for the v20 non-executable activity history."""

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "loofi-fedora-tweaks"))

from utils.history import (  # noqa: E402
    HISTORY_SCHEMA_VERSION,
    HistoryManager,
    HistoryVersionError,
)


class TestTypedHistory(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.path = Path(self.temporary.name) / "history.json"
        self.manager = HistoryManager()
        self.manager.HISTORY_FILE = str(self.path)

    def tearDown(self):
        self.temporary.cleanup()

    def test_log_change_discards_command_and_writes_v2_envelope(self):
        self.manager.log_change(
            "Enabled dark mode",
            ["gsettings", "set", "theme", "light"],
        )

        payload = json.loads(self.path.read_text(encoding="utf-8"))
        self.assertEqual(payload["schema_version"], HISTORY_SCHEMA_VERSION)
        self.assertEqual(payload["entries"][0]["description"], "Enabled dark mode")
        self.assertNotIn("undo_command", payload["entries"][0])
        self.assertFalse(self.manager.can_undo())

    def test_closed_recovery_reference_is_inert_but_discoverable(self):
        self.manager.log_change(
            "Prepared package recovery",
            recovery_action_id="dnf5-history-undo",
            recovery_parameters={"transaction_id": 42},
        )

        self.assertTrue(self.manager.can_undo())
        result = self.manager.undo_last_action()
        self.assertFalse(result.success)
        self.assertEqual(result.data["recovery_action_id"], "dnf5-history-undo")
        self.assertEqual(result.data["recovery_parameters"], {"transaction_id": 42})

    @patch("subprocess.run")
    def test_tampered_legacy_command_is_never_executed(self, mock_run):
        self.path.write_text(
            json.dumps(
                [
                    {
                        "id": "tampered",
                        "timestamp": "2026-01-01T00:00:00+00:00",
                        "description": "Legacy change",
                        "undo_command": ["pkexec", "tee", "/etc/example"],
                    }
                ]
            ),
            encoding="utf-8",
        )

        result = self.manager.undo_action("tampered")

        self.assertFalse(result.success)
        mock_run.assert_not_called()
        migrated = json.loads(self.path.read_text(encoding="utf-8"))
        self.assertEqual(migrated["schema_version"], HISTORY_SCHEMA_VERSION)
        self.assertNotIn("undo_command", migrated["entries"][0])
        backup = self.path.with_name("history.v1.json.bak")
        self.assertTrue(backup.exists())
        self.assertIn("undo_command", backup.read_text(encoding="utf-8"))

    def test_future_schema_is_read_only(self):
        original = {"schema_version": 99, "entries": []}
        self.path.write_text(json.dumps(original), encoding="utf-8")

        with self.assertRaises(HistoryVersionError):
            self.manager.get_recent()

        self.assertEqual(json.loads(self.path.read_text(encoding="utf-8")), original)

    def test_history_is_bounded_and_newest_first(self):
        for index in range(55):
            self.manager.log_change(f"Action {index}")

        recent = self.manager.get_recent(3)
        payload = json.loads(self.path.read_text(encoding="utf-8"))
        self.assertEqual(len(payload["entries"]), 50)
        self.assertEqual([entry.description for entry in recent], ["Action 54", "Action 53", "Action 52"])

    def test_corrupt_and_missing_history_are_empty(self):
        self.assertEqual(self.manager.get_recent(), [])
        self.path.write_text("not-json", encoding="utf-8")
        self.assertEqual(self.manager.get_recent(), [])

    def test_private_values_are_redacted(self):
        self.manager.log_change(
            "Changed /home/alice/config token=secret-value",
            recovery_action_id="manual",
            recovery_parameters={"password": "hunter2", "path": "/home/alice/file"},
        )

        entry = self.manager.get_recent(1)[0]
        self.assertNotIn("alice", entry.description)
        self.assertEqual(entry.recovery_parameters["password"], "<masked>")
        self.assertEqual(entry.recovery_parameters["path"], "/home/<user>/file")


if __name__ == "__main__":
    unittest.main()
