"""Immutable, bounded Compass troubleshooting model tests."""

from __future__ import annotations

import dataclasses
import unittest

from core.troubleshooting.lifecycle import finalize_session, new_session, start_session
from core.troubleshooting.models import (
    FindingComparison,
    NextStep,
    RelatedChangeReference,
    SourceResult,
    TroubleshootingComparison,
    TroubleshootingFinding,
    TroubleshootingSession,
)
from core.troubleshooting.profiles import require_profile


class TestTroubleshootingModels(unittest.TestCase):
    def _source(self, source_id: str = "system-check") -> SourceResult:
        budget = require_profile("system_slow").budget_for(source_id, "traditional")
        self.assertIsNotNone(budget)
        return SourceResult.completed(
            source_id,
            started_at=10.0,
            completed_at=11.0,
            timeout_seconds=budget.timeout_seconds,
            facts={"pressure": "normal", "usage_percent": 50.0},
        )

    def _finding(self, next_step: NextStep | None = None) -> TroubleshootingFinding:
        return TroubleshootingFinding.build(
            finding_type="resource-pressure",
            category="performance",
            severity="attention",
            title="Resource pressure needs review",
            summary="Saved evidence reports sustained pressure.",
            evidence_explanation="The bounded resource trend crossed its review threshold.",
            source_id="system-check",
            collected_at=11.0,
            freshness="fresh",
            evidence_quality="supported",
            applicable_variants=frozenset({"traditional", "atomic"}),
            affected_resources=("metric:cpu-pressure",),
            evidence={"pressure": "high", "sample_count": 5},
            next_step=next_step or NextStep.navigation("health"),
        )

    def test_next_step_accepts_only_one_closed_inert_kind(self):
        action = NextStep.action("dnf-clean-all")
        navigation = NextStep.navigation(
            "health",
            {"finding_id": "resource-pressure"},
        )
        collection = NextStep.collect(
            "observability",
            reason_code="refresh-stale-evidence",
        )
        manual = NextStep.manual(
            "Review the affected service without changing it.",
            reason_code="manual-review-required",
        )
        none = NextStep.none(reason_code="no-safe-next-step")

        self.assertEqual(action.kind, "action")
        self.assertEqual(navigation.parameters_dict()["finding_id"], "resource-pressure")
        self.assertEqual(collection.kind, "collect")
        self.assertEqual(manual.kind, "manual")
        self.assertEqual(none.kind, "none")

    def test_unknown_actions_routes_and_execution_payloads_are_rejected(self):
        with self.assertRaisesRegex(ValueError, "Unknown Action"):
            NextStep.action("arbitrary-command")
        with self.assertRaisesRegex(ValueError, "Unknown canonical"):
            NextStep.navigation("future:route")
        for payload in (
            {"command": ["sh", "-c", "id"]},
            {"callback": lambda: None},
            {"renderer": object()},
            {"token": "secret"},
            {"stdout": "raw command output"},
        ):
            with self.subTest(payload=tuple(payload)):
                with self.assertRaises(ValueError):
                    NextStep.navigation("health", payload)
        with self.assertRaises(ValueError):
            NextStep(
                "navigation",
                "health",
                (("command", ("id",)),),
            )

    def test_source_results_enforce_timeout_and_failure_semantics(self):
        completed = self._source()
        self.assertEqual(completed.state, "completed")

        with self.assertRaisesRegex(ValueError, "exceeded"):
            SourceResult.completed(
                "system-check",
                started_at=0.0,
                completed_at=46.0,
                timeout_seconds=45.0,
                facts={},
            )
        with self.assertRaisesRegex(ValueError, "reach"):
            SourceResult(
                "system-check",
                "timed_out",
                0.0,
                44.0,
                45.0,
                reason_code="source-timeout",
                message="The source timed out.",
            )
        with self.assertRaisesRegex(ValueError, "cannot claim facts"):
            SourceResult(
                "system-check",
                "failed",
                0.0,
                1.0,
                45.0,
                (("value", True),),
                "collector-failed",
                "The source failed.",
            )
        with self.assertRaises(ValueError):
            SourceResult(
                "system-check",
                "completed",
                0.0,
                1.0,
                45.0,
                (("command-vector", ("id",)),),
            )

    def test_finding_fingerprint_is_deterministic_and_contract_is_immutable(self):
        first = self._finding()
        second = self._finding()

        self.assertEqual(first.fingerprint, second.fingerprint)
        self.assertEqual(len(first.fingerprint), 64)
        with self.assertRaises(dataclasses.FrozenInstanceError):
            first.summary = "Changed"

    def test_finding_rejects_personal_paths_unbounded_text_and_tampering(self):
        with self.assertRaisesRegex(ValueError, "privacy-safe"):
            TroubleshootingFinding.build(
                finding_type="resource-pressure",
                category="performance",
                severity="attention",
                title="Review",
                summary="Review",
                evidence_explanation="Evidence",
                source_id="system-check",
                collected_at=11.0,
                freshness="fresh",
                evidence_quality="limited",
                applicable_variants=frozenset({"traditional"}),
                affected_resources=("/home/alice/private",),
                evidence={"value": True},
                next_step=NextStep.none(reason_code="no-safe-next-step"),
            )
        with self.assertRaisesRegex(ValueError, "512-character"):
            TroubleshootingFinding.build(
                finding_type="resource-pressure",
                category="performance",
                severity="attention",
                title="x" * 513,
                summary="Review",
                evidence_explanation="Evidence",
                source_id="system-check",
                collected_at=11.0,
                freshness="fresh",
                evidence_quality="limited",
                applicable_variants=frozenset({"traditional"}),
                affected_resources=("metric:cpu",),
                evidence={"value": True},
                next_step=NextStep.none(reason_code="no-safe-next-step"),
            )
        payload = self._finding().to_dict()
        payload["fingerprint"] = "0" * 64
        with self.assertRaisesRegex(ValueError, "fingerprint"):
            TroubleshootingFinding.from_dict(payload)
        safe = self._finding()
        with self.assertRaises(ValueError):
            TroubleshootingFinding(
                safe.finding_type,
                safe.category,
                safe.severity,
                safe.title,
                safe.summary,
                safe.evidence_explanation,
                safe.source_id,
                safe.collected_at,
                safe.freshness,
                safe.evidence_quality,
                safe.applicable_variants,
                safe.affected_resources,
                (("raw-output", "private"),),
                safe.next_step,
            )

    def test_session_round_trip_retains_source_state_lists(self):
        queued = new_session(
            "system_slow",
            "traditional",
            started_at=10.0,
            session_id="12345678-1234-5678-9234-567812345678",
        )
        running = start_session(queued, started_at=10.0)
        source = self._source()
        session = finalize_session(
            running,
            completed_at=12.0,
            source_results=(source,),
            findings=(self._finding(),),
        )

        restored = TroubleshootingSession.from_dict(session.to_dict())

        self.assertEqual(restored, session)
        self.assertEqual(restored.state, "partial")
        self.assertEqual(restored.completed_sources, ("system-check",))
        self.assertEqual(
            restored.unavailable_sources,
            ("change-journal", "observability"),
        )
        payload = session.to_dict()
        payload["completed_sources"] = []
        with self.assertRaisesRegex(ValueError, "does not match"):
            TroubleshootingSession.from_dict(payload)

    def test_terminal_session_cannot_omit_a_profile_source(self):
        source = self._source()
        with self.assertRaisesRegex(ValueError, "every applicable"):
            TroubleshootingSession(
                "12345678-1234-5678-9234-567812345678",
                "system_slow",
                1,
                "traditional",
                "completed",
                10.0,
                12.0,
                source_results=(source,),
            )

    def test_related_change_is_always_possibly_related_and_has_no_command(self):
        change = RelatedChangeReference(
            "change-1",
            "change-journal",
            12.0,
            ("package:demo",),
            frozenset({"time_proximity", "shared_resource"}),
        )
        payload = change.to_dict()

        self.assertEqual(payload["label"], "Possibly related")
        self.assertNotIn("command", payload)
        payload["label"] = "Confirmed cause"
        with self.assertRaisesRegex(ValueError, "Possibly related"):
            RelatedChangeReference.from_dict(payload)

    def test_comparison_contract_does_not_implement_causal_inference(self):
        outcome = FindingComparison(
            "a" * 64,
            "",
            "not_comparable",
            "follow-up-source-unavailable",
        )
        comparison = TroubleshootingComparison(
            "12345678-1234-5678-9234-567812345678",
            "12345678-1234-5678-9234-567812345679",
            "system_slow",
            1,
            "traditional",
            (outcome,),
            False,
            "source-unavailable",
        )

        self.assertFalse(comparison.comparable)
        self.assertEqual(comparison.to_dict()["outcomes"][0]["state"], "not_comparable")
        self.assertEqual(
            TroubleshootingComparison.from_dict(comparison.to_dict()),
            comparison,
        )


if __name__ == "__main__":
    unittest.main()
