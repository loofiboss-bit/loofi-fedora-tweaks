"""Compass evidence composition and conservative correlation tests."""

from __future__ import annotations

import unittest

from core.troubleshooting.adapters import (
    SourceChange,
    SourceEvidence,
    adapt_structured_source,
)
from core.troubleshooting.composition import compose_session
from core.troubleshooting.lifecycle import new_session, start_session
from core.troubleshooting.models import NextStep, TroubleshootingFinding


class TestTroubleshootingComposition(unittest.TestCase):
    SESSION_ID = "12345678-1234-5678-9234-567812345678"

    def _running(self):
        return start_session(
            new_session(
                "network_problem",
                "traditional",
                started_at=1.0,
                session_id=self.SESSION_ID,
            ),
            started_at=2.0,
        )

    @staticmethod
    def _finding(*, collected_at: float = 4.0) -> TroubleshootingFinding:
        return TroubleshootingFinding.build(
            finding_type="network-state-degraded",
            category="network",
            severity="attention",
            title="Network state needs review",
            summary="No active NetworkManager connection was retained.",
            evidence_explanation="The source-owned NetworkManager metadata is empty.",
            source_id="network-state",
            collected_at=collected_at,
            freshness="fresh",
            evidence_quality="confirmed",
            applicable_variants=frozenset({"traditional"}),
            affected_resources=("network-manager",),
            evidence={"active_connection": False},
            next_step=NextStep.navigation("network"),
        )

    def test_composition_is_deterministic_and_labels_related_changes(self):
        network = adapt_structured_source(
            profile_id="network_problem",
            variant="traditional",
            source_id="network-state",
            state="completed",
            started_at=2.0,
            completed_at=4.0,
            facts={"active_connection": False},
            findings=(self._finding(),),
        )
        dns = adapt_structured_source(
            profile_id="network_problem",
            variant="traditional",
            source_id="dns-state",
            state="empty",
            started_at=2.0,
            completed_at=3.0,
            facts={"server_count": 0},
        )
        journal_base = adapt_structured_source(
            profile_id="network_problem",
            variant="traditional",
            source_id="change-journal",
            state="completed",
            started_at=2.0,
            completed_at=3.0,
            facts={"event_count": 2},
        )
        journal = SourceEvidence(
            journal_base.result,
            changes=(
                SourceChange(
                    "loofi_app:1234567890abcdef1234",
                    "loofi_app",
                    3.0,
                    ("network-manager",),
                ),
                SourceChange(
                    "loofi_app:abcdef1234567890abcd",
                    "loofi_app",
                    5.0,
                    ("network-manager",),
                ),
            ),
        )

        result = compose_session(
            self._running(),
            (journal, dns, network),
            completed_at=5.0,
        )

        self.assertEqual(result.state, "completed")
        self.assertEqual(len(result.related_changes), 1)
        related = result.related_changes[0]
        self.assertEqual(related.label, "Possibly related")
        self.assertEqual(
            related.match_reasons,
            frozenset({"time_proximity", "shared_resource"}),
        )
        self.assertEqual(
            tuple(item.source_id for item in result.source_results),
            ("change-journal", "dns-state", "network-state"),
        )

    def test_partial_or_stale_source_cannot_produce_all_clear(self):
        for state in ("partial", "stale"):
            with self.subTest(state=state):
                network = adapt_structured_source(
                    profile_id="network_problem",
                    variant="traditional",
                    source_id="network-state",
                    state=state,
                    started_at=2.0,
                    completed_at=3.0,
                    facts={"active_connection": True},
                    reason_code=f"{state}-evidence",
                    message=f"Network evidence is {state}.",
                )
                result = compose_session(
                    self._running(),
                    (network,),
                    completed_at=4.0,
                )
                self.assertEqual(result.state, "partial")
                self.assertFalse(result.findings)

    def test_missing_sources_remain_unavailable_and_no_database_is_required(self):
        network = adapt_structured_source(
            profile_id="network_problem",
            variant="traditional",
            source_id="network-state",
            state="empty",
            started_at=2.0,
            completed_at=3.0,
        )

        result = compose_session(
            self._running(),
            (network,),
            completed_at=4.0,
        )

        self.assertEqual(result.state, "partial")
        self.assertEqual(result.unavailable_sources, ("change-journal", "dns-state"))
        self.assertEqual(dict(result.compatibility.source_versions), {"network-state": 1})

    def test_composition_rejects_duplicate_sources_and_out_of_session_timing(self):
        network = adapt_structured_source(
            profile_id="network_problem",
            variant="traditional",
            source_id="network-state",
            state="empty",
            started_at=2.0,
            completed_at=3.0,
        )
        with self.assertRaisesRegex(ValueError, "duplicate"):
            compose_session(
                self._running(),
                (network, network),
                completed_at=4.0,
            )
        early = adapt_structured_source(
            profile_id="network_problem",
            variant="traditional",
            source_id="dns-state",
            state="empty",
            started_at=1.0,
            completed_at=2.0,
        )
        with self.assertRaisesRegex(ValueError, "timing"):
            compose_session(
                self._running(),
                (early,),
                completed_at=4.0,
            )
        with self.assertRaisesRegex(ValueError, "total budget"):
            compose_session(
                self._running(),
                (),
                completed_at=28.0,
            )


if __name__ == "__main__":
    unittest.main()
