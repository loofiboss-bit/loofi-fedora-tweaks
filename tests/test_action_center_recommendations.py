"""Tests for v12 Action Center health recommendations."""

import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "loofi-fedora-tweaks"))

from core.actions import ActionCenterService
from core.observability import HealthSnapshot, HealthTimelineStore, ProblemFingerprint


def _snapshot(timestamp, fingerprint):
    return HealthSnapshot(
        timestamp=timestamp,
        app_version="12.0.0",
        app_codename="Lighthouse",
        fedora_target="44",
        atomic=False,
        daily_maintenance={"cards": []},
        action_center_summary={},
        problem_fingerprints=[fingerprint],
    )


class TestActionCenterRecommendations(unittest.TestCase):
    """Recommendations are deduped and manual-safe."""

    def test_timeline_recommendation_is_manual_only(self):
        fp = ProblemFingerprint(
            id="failed-service:abc",
            kind="failed-service",
            title="Failed unit: bad.service",
            summary="bad.service is recurring.",
            source_id="failed-services",
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            store = HealthTimelineStore(Path(tmpdir) / "timeline.json")
            store.save([_snapshot(1.0, fp), _snapshot(2.0, fp)])
            with patch("core.observability.HealthTimelineStore", return_value=store):
                recommendations = ActionCenterService().recommendations_from_timeline()

        self.assertEqual(len(recommendations), 1)
        self.assertTrue(recommendations[0].manual_only)
        self.assertEqual(recommendations[0].dedupe_key, "observability:failed-service:abc")
        self.assertIn("snapshot_id", recommendations[0].metadata)


if __name__ == "__main__":
    unittest.main()
