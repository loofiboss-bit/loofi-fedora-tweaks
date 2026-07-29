"""Contracts for the committed V21 Phase 4 qualification evidence."""

from __future__ import annotations

import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
STARTUP = ROOT / "docs" / "reports" / "V21_PHASE4_STARTUP.json"
REPORT = ROOT / "docs" / "reports" / "V21_PHASE4_PLATFORM_QUALITY.md"
TASKS = ROOT / ".workflow" / "specs" / "tasks-v21.0.0.md"
RACE_LOCK = ROOT / ".workflow" / "specs" / ".race-lock.json"
PUBLICATION = ROOT / "docs" / "reports" / "V21_RELEASE_PUBLICATION.md"


class TestV21Phase4QualityGates(unittest.TestCase):
    def test_startup_evidence_meets_resolve_ceiling_and_idle_contract(self):
        evidence = json.loads(STARTUP.read_text(encoding="utf-8"))

        self.assertEqual(evidence["method"]["warmups"], 2)
        self.assertEqual(evidence["method"]["runs"], 7)
        self.assertLessEqual(
            evidence["summary"]["milestones_ms"]["meaningful_home"]["median"],
            250.094,
        )
        self.assertLessEqual(evidence["summary"]["rss_kib"]["median"], 83_582)

        for run in evidence["runs"]:
            self.assertEqual(run["runtime_plugin_ids"], ["atlas_dashboard"])
            self.assertEqual(run["active_timer_intervals_ms"], [])
            self.assertEqual(run["running_qthreads"], 0)
            self.assertEqual(run["subprocess_probes"], [])
            self.assertEqual(run["system_check_runtime_imports"], [])

    def test_phase_four_evidence_is_retained_in_current_v23_release_state(self):
        report = REPORT.read_text(encoding="utf-8")
        tasks = TASKS.read_text(encoding="utf-8")
        race_lock = json.loads(RACE_LOCK.read_text(encoding="utf-8"))
        publication = PUBLICATION.read_text(encoding="utf-8")

        self.assertIn("Product version remains `20.0.0 \"Continuity\"`", report)
        self.assertIn("- [x] P4: lifecycle regression", tasks)
        self.assertIn(
            "- [x] Synchronize version metadata to v21.0.0", tasks
        )
        self.assertEqual(race_lock["product_version"], "v23.0.2")
        self.assertEqual(race_lock["current_public_release"], "v23.0.2")
        self.assertEqual(
            race_lock["current_release_commit"],
            "8d0a94eec17586ff2b0101ad460083fbf26ef9b7",
        )
        self.assertIn("843760c4fe2725d093a977554badf8d1eb2451be", publication)
        self.assertIn("10774741", publication)


if __name__ == "__main__":
    unittest.main()
