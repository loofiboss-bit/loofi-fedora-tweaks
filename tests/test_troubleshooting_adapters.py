"""Read-only Compass evidence adapter coverage."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from core.change_journal.models import (
    ChangeEvent,
    ChangeJournalSnapshot,
    ChangeSourceStatus,
)
from core.observability.snapshot import HealthSnapshot
from core.observability.timeline import HealthTimelineStore
from core.system_check.models import (
    FindingEvidence,
    SystemCheckResult,
    SystemFinding,
)
from core.troubleshooting.adapters import (
    adapt_action_center,
    adapt_change_journal,
    adapt_observability,
    adapt_structured_source,
    adapt_system_check,
)


class TestTroubleshootingAdapters(unittest.TestCase):
    def test_structured_adapter_preserves_closed_evidence_states(self):
        cases = (
            ("completed", {}, "", ""),
            ("empty", {"item_count": 0}, "", ""),
            ("partial", {"item_count": 1}, "source-partial", "Some evidence is unavailable."),
            ("stale", {"item_count": 1}, "stale-evidence", "Saved evidence is stale."),
            ("unavailable", None, "tool-unavailable", "The source is unavailable."),
            ("failed", None, "source-failed", "The source failed."),
            ("cancelled", None, "session-cancelled", "Collection was cancelled."),
        )
        for state, facts, reason_code, message in cases:
            with self.subTest(state=state):
                evidence = adapt_structured_source(
                    profile_id="network_problem",
                    variant="traditional",
                    source_id="network-state",
                    state=state,
                    started_at=1.0,
                    completed_at=2.0,
                    facts=facts,
                    reason_code=reason_code,
                    message=message,
                )
                self.assertEqual(evidence.result.state, state)

    def test_structured_adapter_rejects_cross_profile_and_budget_overrun(self):
        with self.assertRaisesRegex(ValueError, "does not belong"):
            adapt_structured_source(
                profile_id="network_problem",
                variant="traditional",
                source_id="network-scan",
                state="empty",
                started_at=1.0,
                completed_at=2.0,
            )
        with self.assertRaisesRegex(ValueError, "exceeded"):
            adapt_structured_source(
                profile_id="network_problem",
                variant="traditional",
                source_id="network-state",
                state="completed",
                started_at=1.0,
                completed_at=7.0,
            )

    def test_system_check_adapter_retains_findings_and_variant(self):
        finding = SystemFinding.build(
            finding_id="root-disk-pressure",
            category="storage",
            severity="attention",
            title="Root filesystem needs attention",
            summary="Root usage crossed the review threshold.",
            evidence=FindingEvidence.from_mapping(
                "maintenance",
                {"root_usage_percent": 92.0},
                collected_at=11.0,
            ),
            applicable_variants=frozenset({"traditional", "atomic"}),
            freshness_state="fresh",
            affected_resources=("filesystem:/",),
            route_id="maintenance:cleanup",
        )
        result = SystemCheckResult(
            "check-1",
            "system-check-quick-v1",
            "completed",
            False,
            10.0,
            12.0,
            (finding,),
            completed_sources=("maintenance",),
        )

        evidence = adapt_system_check(
            result,
            profile_id="storage_pressure",
            variant="traditional",
        )

        self.assertEqual(evidence.result.state, "completed")
        self.assertEqual(len(evidence.findings), 1)
        self.assertEqual(evidence.findings[0].source_id, "system-check")
        self.assertEqual(evidence.findings[0].next_step.target_id, "maintenance:cleanup")

        mismatch = adapt_system_check(
            result,
            profile_id="storage_pressure",
            variant="atomic",
        )
        self.assertEqual(mismatch.result.state, "unavailable")
        self.assertFalse(mismatch.findings)

    def test_observability_adapter_filters_variants_and_marks_stale(self):
        traditional = self._snapshot(timestamp=10.0, atomic=False)
        atomic = self._snapshot(timestamp=19.0, atomic=True)

        evidence = adapt_observability(
            (traditional, atomic),
            profile_id="system_slow",
            variant="traditional",
            started_at=20.0,
            completed_at=21.0,
            stale_after_seconds=5.0,
        )

        self.assertEqual(evidence.result.state, "stale")
        self.assertEqual(evidence.result.facts_dict()["snapshot_count"], 1)

    def test_change_journal_adapter_keeps_variant_specific_events_separate(self):
        snapshot = ChangeJournalSnapshot(
            events=(
                ChangeEvent(
                    "dnf5:1234567890abcdef12345678",
                    "dnf5",
                    8.0,
                    "system",
                    "Traditional package change.",
                    ("package-manager",),
                ),
                ChangeEvent(
                    "rpm_ostree:1234567890abcdef1234",
                    "rpm_ostree",
                    9.0,
                    "system",
                    "Atomic deployment change.",
                    ("rpm-ostree-deployment",),
                ),
            ),
            sources=(
                ChangeSourceStatus("dnf5", "available", 10.0),
                ChangeSourceStatus("rpm_ostree", "available", 10.0),
            ),
            generated_at=10.0,
        )

        traditional = adapt_change_journal(
            snapshot,
            profile_id="updates_failed",
            variant="traditional",
            started_at=10.0,
            completed_at=11.0,
        )
        atomic = adapt_change_journal(
            snapshot,
            profile_id="updates_failed",
            variant="atomic",
            started_at=10.0,
            completed_at=11.0,
        )

        self.assertEqual(tuple(item.source_kind for item in traditional.changes), ("dnf5",))
        self.assertEqual(tuple(item.source_kind for item in atomic.changes), ("rpm_ostree",))

    def test_action_center_adapter_reads_only_problem_records(self):
        plans = (
            SimpleNamespace(
                plan_id="plan-1",
                action_id="dnf-clean-all",
                state="blocked",
                supported_variants=frozenset({"traditional"}),
                affected_resources=("package-manager",),
            ),
            SimpleNamespace(
                plan_id="plan-2",
                action_id="dnf-clean-all",
                state="ready",
                supported_variants=frozenset({"traditional"}),
                affected_resources=("package-manager",),
            ),
        )
        runs = (
            SimpleNamespace(
                run_id="run-1",
                action_id="dnf-clean-all",
                state="verification_failed",
                supported_variants=frozenset({"traditional"}),
                affected_resources=("package-manager",),
            ),
        )

        evidence = adapt_action_center(
            plans,
            runs,
            profile_id="updates_failed",
            variant="traditional",
            started_at=1.0,
            completed_at=2.0,
        )

        self.assertEqual(evidence.result.state, "completed")
        self.assertEqual(len(evidence.findings), 2)
        self.assertTrue(all(item.next_step.kind == "navigation" for item in evidence.findings))

    def test_observability_store_read_only_path_never_migrates_file(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "timeline.json"
            payload = {
                "schema_version": 0,
                "snapshots": [self._snapshot(timestamp=10.0, atomic=False).to_dict()],
            }
            original = json.dumps(payload, sort_keys=True)
            path.write_text(original, encoding="utf-8")

            snapshots = HealthTimelineStore(path).load_read_only()

            self.assertEqual(len(snapshots), 1)
            self.assertEqual(path.read_text(encoding="utf-8"), original)

    @staticmethod
    def _snapshot(*, timestamp: float, atomic: bool) -> HealthSnapshot:
        return HealthSnapshot(
            timestamp=timestamp,
            app_version="22.0.0",
            app_codename="Alignment",
            fedora_target="44",
            atomic=atomic,
            daily_maintenance={},
            action_center_summary={},
        )


if __name__ == "__main__":
    unittest.main()
