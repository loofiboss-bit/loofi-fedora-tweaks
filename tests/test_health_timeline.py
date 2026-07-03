"""Tests for v12 health timeline storage."""

import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "loofi-fedora-tweaks"))

from core.observability import HealthSnapshot, HealthTimelineStore


def _snapshot(timestamp):
    return HealthSnapshot(
        timestamp=timestamp,
        app_version="12.0.0",
        app_codename="Lighthouse",
        fedora_target="44",
        atomic=False,
        daily_maintenance={"cards": []},
        action_center_summary={},
    )


class TestHealthTimelineStore(unittest.TestCase):
    """Timeline retention and corrupt file handling are deterministic."""

    def test_retention_limits_saved_snapshots(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            store = HealthTimelineStore(Path(tmpdir) / "timeline.json", retention=2)
            store.append(_snapshot(1.0))
            store.append(_snapshot(2.0))
            store.append(_snapshot(3.0))

            self.assertEqual([item.timestamp for item in store.load()], [2.0, 3.0])

    def test_corrupt_history_returns_empty_without_crashing(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "timeline.json"
            path.write_text("{not-json", encoding="utf-8")
            store = HealthTimelineStore(path)

            self.assertEqual(store.load(), [])
            self.assertIn("corrupt-history", store.last_error)


if __name__ == "__main__":
    unittest.main()
