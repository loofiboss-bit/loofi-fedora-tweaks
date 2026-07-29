"""Compass authority, evidence, and active-phase contracts."""

from __future__ import annotations

import hashlib
import json
import unittest
from pathlib import Path

from core.export.support_bundle import CURRENT_SUPPORT_BUNDLE_VERSION
from core.product_catalog import catalog_entry, catalog_routes
from version import __version__, __version_codename__


ROOT = Path(__file__).resolve().parents[1]
RACE_LOCK = ROOT / ".workflow" / "specs" / ".race-lock.json"
TASKS = ROOT / ".workflow" / "specs" / "tasks-v23.0.0.md"
STARTUP = ROOT / "docs" / "reports" / "V23_PHASE0_STARTUP.json"
SYSTEM_CHECK = ROOT / "docs" / "reports" / "V23_PHASE0_SYSTEM_CHECK.json"
SCREENSHOTS = ROOT / "docs" / "reports" / "V23_PHASE0_SCREENSHOTS.json"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


class TestV23Phase0Authority(unittest.TestCase):
    def test_product_version_stays_on_alignment_with_active_compass_lock(self):
        lock = json.loads(RACE_LOCK.read_text(encoding="utf-8"))

        self.assertEqual(__version__, lock["product_version"].removeprefix("v"))
        self.assertEqual(__version_codename__, lock["product_codename"])
        self.assertEqual(lock["product_version"], lock["current_public_release"])
        self.assertEqual(lock["version"], "v23.0.0")
        self.assertEqual(lock["target_version"], "v23.0.0")
        self.assertEqual(lock["status"], "active")
        self.assertEqual(lock["phase"], "phase-4-complete")

    def test_historical_v23_tag_collision_is_locked_without_resolution_claim(self):
        lock = json.loads(RACE_LOCK.read_text(encoding="utf-8"))
        collision = lock["historical_tag_collision"]

        self.assertEqual(collision["tag"], "v23.0.0")
        self.assertEqual(
            collision["peeled_commit"],
            "adc4cef116d147bd5b845f0ec98c3a1970b8b054",
        )
        self.assertEqual(
            collision["status"],
            "blocked-pending-separate-release-authority",
        )

    def test_existing_diagnostics_route_is_selected_without_route_change(self):
        routes = catalog_routes()
        entry = catalog_entry("diagnostics")
        logs = catalog_entry("logs")

        self.assertEqual(len(routes), 81)
        self.assertIsNotNone(entry)
        self.assertEqual(entry.destination.id, "system")
        self.assertEqual(entry.section.id, "troubleshooting")
        self.assertEqual(entry.plugin.id, "diagnostics")
        self.assertTrue(entry.placement.discoverable)
        self.assertEqual(logs.placement.redirect_route_id, "diagnostics:watchtower")

    def test_startup_baseline_locks_phase_zero_resource_budget(self):
        evidence = json.loads(STARTUP.read_text(encoding="utf-8"))

        self.assertEqual(evidence["method"]["warmups"], 2)
        self.assertEqual(evidence["method"]["runs"], 7)
        self.assertLessEqual(
            evidence["summary"]["milestones_ms"]["meaningful_home"]["median"],
            189.819,
        )
        self.assertLessEqual(evidence["summary"]["rss_kib"]["median"], 84_120)
        for run in evidence["runs"]:
            self.assertEqual(run["runtime_plugin_ids"], ["atlas_dashboard"])
            self.assertEqual(run["active_timer_intervals_ms"], [])
            self.assertEqual(run["running_qthreads"], 0)
            self.assertEqual(run["subprocess_probes"], [])
            self.assertEqual(run["system_check_runtime_imports"], [])

    def test_system_check_baseline_passes_all_existing_source_budgets(self):
        evidence = json.loads(SYSTEM_CHECK.read_text(encoding="utf-8"))

        self.assertEqual(evidence["status"], "passed")
        self.assertEqual(evidence["errors"], [])
        self.assertLessEqual(
            evidence["total_median_ms"],
            evidence["total_median_budget_ms"],
        )
        for source, duration in evidence["source_medians_ms"].items():
            self.assertLessEqual(
                duration,
                evidence["source_median_budgets_ms"][source],
            )
        self.assertTrue(all(run["state"] == "completed" for run in evidence["runs"]))
        self.assertTrue(all(run["source_errors"] == [] for run in evidence["runs"]))

    def test_screenshot_manifest_is_complete_and_does_not_claim_physical_gate(self):
        evidence = json.loads(SCREENSHOTS.read_text(encoding="utf-8"))

        self.assertEqual(evidence["captured_product_version"], __version__)
        self.assertEqual(
            evidence["captured_product_codename"],
            __version_codename__,
        )
        self.assertEqual(evidence["phase"], 0)
        self.assertEqual(evidence["status"], "passed")
        self.assertEqual(len(evidence["captures"]), 12)
        self.assertEqual(len(evidence["contact_sheets"]), 6)
        self.assertEqual(
            evidence["capture_policy"]["physical_gate"],
            "not_verified",
        )
        for record in evidence["contact_sheets"]:
            path = ROOT / record["path"]
            self.assertTrue(path.is_file())
            self.assertEqual(_sha256(path), record["sha256"])

    def test_phases_zero_through_four_are_complete_and_later_phases_are_not_started(self):
        text = TASKS.read_text(encoding="utf-8")
        phase_zero, phase_one_and_later = text.split(
            "## Phase 1 — Troubleshooting domain and profile catalog",
            maxsplit=1,
        )
        phase_one, phase_two_and_later = phase_one_and_later.split(
            "## Phase 2 — Evidence composition and conservative correlation",
            maxsplit=1,
        )
        phase_two, phase_three_and_later = phase_two_and_later.split(
            "## Phase 3 — Canonical Troubleshoot experience",
            maxsplit=1,
        )
        phase_three, phase_four_and_later = phase_three_and_later.split(
            "## Phase 4 — CLI, read-only API, and support case",
            maxsplit=1,
        )
        phase_four, later = phase_four_and_later.split(
            "## Phase 5 — Platform, performance, and security qualification",
            maxsplit=1,
        )

        self.assertIn("- [x]", phase_zero)
        self.assertNotIn("- [ ]", phase_zero)
        self.assertIn("- [x]", phase_one)
        self.assertNotIn("- [ ]", phase_one)
        self.assertIn("- [x]", phase_two)
        self.assertNotIn("- [ ]", phase_two)
        self.assertIn("- [x]", phase_three)
        self.assertNotIn("- [ ]", phase_three)
        self.assertIn("- [x]", phase_four)
        self.assertNotIn("- [ ]", phase_four)
        self.assertNotIn("- [x]", later)
        self.assertEqual(CURRENT_SUPPORT_BUNDLE_VERSION, 13)


if __name__ == "__main__":
    unittest.main()
