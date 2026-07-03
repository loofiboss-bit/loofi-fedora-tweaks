"""Tests for v12 maintenance trend detection."""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "loofi-fedora-tweaks"))

from core.observability import HealthSnapshot, MaintenanceTrendAnalyzer, ProblemFingerprint


def _fp(identifier):
    return ProblemFingerprint(id=identifier, kind="failed-service", title=identifier, summary=identifier, source_id="failed-services")


def _snapshot(timestamp, fingerprints, state="warning"):
    return HealthSnapshot(
        timestamp=timestamp,
        app_version="12.0.0",
        app_codename="Lighthouse",
        fedora_target="44",
        atomic=False,
        daily_maintenance={"cards": [{"id": "failed-services", "state": state}]},
        action_center_summary={},
        problem_fingerprints=fingerprints,
    )


class TestMaintenanceTrendAnalyzer(unittest.TestCase):
    """Trend analyzer detects recurring and resolved issues."""

    def test_recurring_and_resolved_fingerprints(self):
        one = _fp("failed-service:one")
        two = _fp("failed-service:two")
        summary = MaintenanceTrendAnalyzer([
            _snapshot(1.0, [one, two]),
            _snapshot(2.0, [one]),
        ]).analyze()

        self.assertEqual([item.id for item in summary.recurring], ["failed-service:one"])
        self.assertEqual([item.id for item in summary.resolved], ["failed-service:two"])

    def test_worsening_card_state(self):
        summary = MaintenanceTrendAnalyzer([
            _snapshot(1.0, [], state="success"),
            _snapshot(2.0, [], state="blocked"),
        ]).analyze()

        self.assertEqual(summary.worsening, ["failed-services"])


if __name__ == "__main__":
    unittest.main()

