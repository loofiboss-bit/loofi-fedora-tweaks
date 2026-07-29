"""Compatible Compass follow-up comparison tests."""

from __future__ import annotations

import unittest

from core.troubleshooting.adapters import adapt_structured_source
from core.troubleshooting.comparison import compare_sessions
from core.troubleshooting.composition import compose_session
from core.troubleshooting.lifecycle import new_session, start_session
from core.troubleshooting.models import NextStep, TroubleshootingFinding


class TestTroubleshootingComparison(unittest.TestCase):
    BEFORE_ID = "12345678-1234-5678-9234-567812345678"
    AFTER_ID = "12345678-1234-5678-9234-567812345679"

    @staticmethod
    def _finding(*, usage_percent: float, severity: str = "attention"):
        return TroubleshootingFinding.build(
            finding_type="network-pressure",
            category="network",
            severity=severity,  # type: ignore[arg-type]
            title="Network pressure",
            summary="Network evidence needs review.",
            evidence_explanation="The bounded source facts crossed a review threshold.",
            source_id="network-state",
            collected_at=3.0,
            freshness="fresh",
            evidence_quality="supported",
            applicable_variants=frozenset({"traditional"}),
            affected_resources=("network-manager",),
            evidence={"usage_percent": usage_percent, "state": "warning"},
            next_step=NextStep.navigation("network"),
        )

    def _session(
        self,
        *,
        session_id: str,
        started_at: float,
        completed_at: float,
        finding: TroubleshootingFinding | None,
        source_state: str = "completed",
        schema_version: int = 1,
        variant: str = "traditional",
    ):
        queued = new_session(
            "network_problem",
            variant,  # type: ignore[arg-type]
            started_at=started_at,
            session_id=session_id,
        )
        running = start_session(queued, started_at=started_at)
        sources = []
        for source_id in ("network-state", "dns-state", "change-journal"):
            state = source_state if source_id == "network-state" else "empty"
            reason = "source-partial" if state == "partial" else ""
            message = "The source is partial." if state == "partial" else ""
            sources.append(
                adapt_structured_source(
                    profile_id="network_problem",
                    variant=variant,  # type: ignore[arg-type]
                    source_id=source_id,
                    state=state,
                    started_at=started_at,
                    completed_at=completed_at - 0.5,
                    facts={"item_count": 1} if state in {"completed", "partial"} else {},
                    findings=(finding,) if source_id == "network-state" and finding else (),
                    reason_code=reason,
                    message=message,
                    schema_version=schema_version if source_id == "network-state" else 1,
                )
            )
        return compose_session(running, sources, completed_at=completed_at)

    def test_unchanged_resolved_and_worsened_are_deterministic(self):
        before = self._session(
            session_id=self.BEFORE_ID,
            started_at=1.0,
            completed_at=4.0,
            finding=self._finding(usage_percent=50.0),
        )
        unchanged = self._session(
            session_id=self.AFTER_ID,
            started_at=5.0,
            completed_at=8.0,
            finding=self._finding(usage_percent=50.0),
        )
        worsened = self._session(
            session_id=self.AFTER_ID,
            started_at=5.0,
            completed_at=8.0,
            finding=self._finding(usage_percent=80.0, severity="critical"),
        )
        resolved = self._session(
            session_id=self.AFTER_ID,
            started_at=5.0,
            completed_at=8.0,
            finding=None,
        )

        self.assertEqual(compare_sessions(before, unchanged).outcomes[0].state, "unchanged")
        self.assertEqual(compare_sessions(before, worsened).outcomes[0].state, "worsened")
        self.assertEqual(compare_sessions(before, resolved).outcomes[0].state, "resolved")

    def test_partial_follow_up_source_is_not_comparable(self):
        before = self._session(
            session_id=self.BEFORE_ID,
            started_at=1.0,
            completed_at=4.0,
            finding=self._finding(usage_percent=50.0),
        )
        after = self._session(
            session_id=self.AFTER_ID,
            started_at=5.0,
            completed_at=8.0,
            finding=self._finding(usage_percent=40.0),
            source_state="partial",
        )

        comparison = compare_sessions(before, after)

        self.assertFalse(comparison.comparable)
        self.assertEqual(comparison.reason_code, "partial-evidence")
        self.assertEqual(comparison.outcomes[0].state, "not_comparable")

    def test_variant_and_source_schema_mismatch_fail_closed(self):
        before = self._session(
            session_id=self.BEFORE_ID,
            started_at=1.0,
            completed_at=4.0,
            finding=self._finding(usage_percent=50.0),
        )
        atomic = self._session(
            session_id=self.AFTER_ID,
            started_at=5.0,
            completed_at=8.0,
            finding=None,
            variant="atomic",
        )
        schema_changed = self._session(
            session_id=self.AFTER_ID,
            started_at=5.0,
            completed_at=8.0,
            finding=self._finding(usage_percent=50.0),
            schema_version=2,
        )

        variant_comparison = compare_sessions(before, atomic)
        schema_comparison = compare_sessions(before, schema_changed)

        self.assertFalse(variant_comparison.comparable)
        self.assertEqual(variant_comparison.reason_code, "fedora-variant-mismatch")
        self.assertFalse(schema_comparison.comparable)
        self.assertEqual(schema_comparison.outcomes[0].reason_code, "source-schema-mismatch")


if __name__ == "__main__":
    unittest.main()
