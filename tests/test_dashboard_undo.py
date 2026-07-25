"""Compatibility tests for dashboard activity and reviewed recovery."""

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "loofi-fedora-tweaks"))

from utils.history import HistoryEntry, HistoryManager  # noqa: E402


class TestHistoryEntry(unittest.TestCase):
    def test_legacy_command_is_inert(self):
        entry = HistoryEntry.from_dict(
            {
                "id": "abc123",
                "timestamp": "2026-01-01T00:00:00+00:00",
                "description": "Changed theme",
                "undo_command": ["gsettings", "set", "theme", "dark"],
            }
        )

        self.assertEqual(entry.id, "abc123")
        self.assertEqual(entry.undo_command, ())
        self.assertNotIn("undo_command", entry.to_dict())

    def test_closed_recovery_round_trip(self):
        entry = HistoryEntry.from_dict(
            {
                "id": "abc",
                "timestamp": "2026-01-01T00:00:00+00:00",
                "description": "Package change",
                "recovery_action_id": "dnf5-history-undo",
                "recovery_parameters": {"transaction_id": 8},
            }
        )

        self.assertEqual(entry.recovery_action_id, "dnf5-history-undo")
        self.assertEqual(entry.to_dict()["recovery_parameters"], {"transaction_id": 8})


class TestHistoryManagerCompatibility(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.path = Path(self.temporary.name) / "history.json"
        self.manager = HistoryManager()
        self.manager.HISTORY_FILE = str(self.path)

    def tearDown(self):
        self.temporary.cleanup()

    def test_recent_entries_are_newest_first(self):
        self.manager.log_change("First")
        self.manager.log_change("Second")

        recent = self.manager.get_recent(2)

        self.assertEqual([entry.description for entry in recent], ["Second", "First"])

    def test_legacy_command_does_not_make_entry_recoverable(self):
        self.path.write_text(
            json.dumps(
                [
                    {
                        "id": "legacy",
                        "timestamp": "2026-01-01T00:00:00+00:00",
                        "description": "Legacy",
                        "undo_command": ["false"],
                    }
                ]
            ),
            encoding="utf-8",
        )

        self.assertFalse(self.manager.can_undo())
        self.assertFalse(self.manager.undo_action("legacy").success)

    @patch("subprocess.run")
    def test_reviewed_recovery_never_executes_from_history(self, mock_run):
        self.manager.log_change(
            "Recoverable",
            recovery_action_id="dnf5-history-undo",
            recovery_parameters={"transaction_id": 1},
        )

        result = self.manager.undo_last_action()

        self.assertFalse(result.success)
        self.assertEqual(result.data["recovery_action_id"], "dnf5-history-undo")
        mock_run.assert_not_called()


if __name__ == "__main__":
    unittest.main()
