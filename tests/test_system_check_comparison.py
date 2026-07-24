"""Deterministic System Check before/after comparison contracts."""

from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock

from core.actions.contracts import ActionRun, FindingContext
from core.system_check.comparison import compare_results
from core.system_check.models import (
    CheckSourceError,
    FindingEvidence,
    SystemCheckResult,
    SystemFinding,
)
from core.system_check.presentation import _maintenance_outcome_views
from ui.maintenance_action_center import _ActionCenterSubTab


def _finding(
    *,
    finding_id: str = "root-disk-pressure",
    percent: float = 95.0,
    severity: str = "attention",
    source: str = "maintenance",
    resource: str = "filesystem:/",
) -> SystemFinding:
    return SystemFinding.build(
        finding_id=finding_id,
        category="storage",
        severity=severity,  # type: ignore[arg-type]
        title="Root filesystem needs attention",
        summary=f"Root usage is {percent} percent.",
        evidence=FindingEvidence.from_mapping(
            source,
            {"root_usage_percent": percent, "state": severity},
            collected_at=10.0,
        ),
        applicable_variants=frozenset({"traditional", "atomic"}),
        freshness_state="fresh",
        affected_resources=(resource,),
        route_id="maintenance:cleanup",
        manual_guidance="Review reclaimable data.",
        manual_reason_code="disk-review",
    )


def _result(
    check_id: str,
    completed_at: float,
    findings=(),
    *,
    atomic: bool = False,
    profile: str = "system-check-quick-v1",
    state: str = "completed",
    errors=(),
    completed_sources=("maintenance",),
) -> SystemCheckResult:
    return SystemCheckResult(
        check_id,
        profile,
        state,  # type: ignore[arg-type]
        atomic,
        completed_at - 1,
        completed_at,
        tuple(findings),
        tuple(errors),
        (),
        tuple(completed_sources),
    )


class TestSystemCheckComparison(unittest.TestCase):
    def test_classifies_resolved_unchanged_and_worsened_deterministically(self):
        resolved = _finding(resource="filesystem:/")
        unchanged = _finding(
            finding_id="large-system-journal",
            percent=90.0,
            source="storage-reclaim",
            resource="system-journal",
        )
        worsened = _finding(
            finding_id="package-health",
            percent=90.0,
            resource="package-manager",
        )
        after_unchanged = _finding(
            finding_id="large-system-journal",
            percent=90.0,
            source="storage-reclaim",
            resource="system-journal",
        )
        after_worsened = _finding(
            finding_id="package-health",
            percent=96.0,
            severity="critical",
            resource="package-manager",
        )

        comparison = compare_results(
            _result(
                "before",
                10.0,
                (resolved, unchanged, worsened),
                completed_sources=("maintenance", "storage-reclaim"),
            ),
            _result(
                "after",
                20.0,
                (after_worsened, after_unchanged),
                completed_sources=("maintenance", "storage-reclaim"),
            ),
        )

        self.assertTrue(comparison.comparable)
        self.assertEqual(
            {
                outcome.finding_id: outcome.state
                for outcome in comparison.outcomes
            },
            {
                "root-disk-pressure": "resolved",
                "large-system-journal": "unchanged",
                "package-health": "worsened",
            },
        )
        self.assertEqual(
            comparison.to_dict()["counts"],
            {
                "resolved": 1,
                "unchanged": 1,
                "worsened": 1,
                "not_comparable": 0,
            },
        )

    def test_missing_follow_up_source_is_not_claimed_resolved(self):
        finding = _finding()
        error = CheckSourceError(
            "maintenance",
            "collector-timeout",
            "Unavailable.",
            1000.0,
            True,
        )

        comparison = compare_results(
            _result("before", 10.0, (finding,)),
            _result(
                "after",
                20.0,
                (),
                state="partial",
                errors=(error,),
                completed_sources=("state-integrity",),
            ),
        )

        self.assertTrue(comparison.comparable)
        self.assertEqual(comparison.outcomes[0].state, "not_comparable")
        self.assertEqual(
            comparison.outcomes[0].reason_code,
            "follow_up_source_unavailable",
        )

    def test_profile_variant_and_order_mismatches_fail_closed(self):
        before = _result("before", 10.0, (_finding(),))
        fixtures = (
            (
                _result("after", 20.0, atomic=True),
                "fedora_variant_mismatch",
            ),
            (
                _result("after", 20.0, profile="future-profile"),
                "profile_mismatch",
            ),
            (
                _result("after", 5.0),
                "invalid_check_order",
            ),
        )
        for after, reason in fixtures:
            with self.subTest(reason=reason):
                comparison = compare_results(before, after)
                self.assertFalse(comparison.comparable)
                self.assertEqual(comparison.reason_code, reason)
                self.assertEqual(
                    comparison.outcomes[0].state,
                    "not_comparable",
                )

    def test_legacy_completed_result_without_source_list_remains_comparable(self):
        finding = _finding()

        comparison = compare_results(
            _result("before", 10.0, (finding,), completed_sources=()),
            _result("after", 20.0, (), completed_sources=()),
        )

        self.assertTrue(comparison.comparable)
        self.assertEqual(comparison.outcomes[0].state, "resolved")

    def test_result_parser_rejects_future_schema_without_mutation(self):
        payload = _result("check-1", 10.0).to_dict()
        payload["schema_version"] = 99

        with self.assertRaises(ValueError):
            SystemCheckResult.from_dict(payload)

    def test_verification_and_resolution_remain_separate_facts(self):
        finding = _finding()
        comparison = compare_results(
            _result("before", 10.0, (finding,)),
            _result("after", 20.0),
        )
        context = FindingContext(
            "before",
            finding.fingerprint,
            "a" * 64,
            "health",
            ("filesystem:/",),
        )
        run = ActionRun(
            "run-1",
            "plan-1",
            "dnf-clean-all",
            "corr",
            finding_context=context,
            state="succeeded",
            last_verified_at=15.0,
            updated_at=16.0,
            verification_result={"success": True},
        )

        view = _maintenance_outcome_views((run,), comparison)[0]

        self.assertEqual(view.verification_state, "verified")
        self.assertEqual(view.resolution_state, "resolved")

        run.last_verified_at = 25.0
        too_early = _maintenance_outcome_views((run,), comparison)[0]
        self.assertEqual(too_early.verification_state, "verified")
        self.assertEqual(too_early.resolution_state, "not_comparable")
        self.assertEqual(
            too_early.resolution_reason_code,
            "follow_up_check_required",
        )

    def test_check_again_is_offered_only_after_linked_success(self):
        finding = _finding()
        context = FindingContext(
            "before",
            finding.fingerprint,
            "a" * 64,
            "health",
            ("filesystem:/",),
        )
        signal = MagicMock()
        tab = SimpleNamespace(
            _current_run=ActionRun(
                "run-1",
                "plan-1",
                "dnf-clean-all",
                "corr",
                finding_context=context,
                state="succeeded",
            ),
            systemCheckRequested=signal,
        )

        _ActionCenterSubTab._request_follow_up_check(tab)

        signal.emit.assert_called_once()
        emitted = signal.emit.call_args.args[0]
        self.assertEqual(emitted["run_id"], "run-1")
        self.assertEqual(
            emitted["affected_resources"],
            ["filesystem:/"],
        )

        tab._current_run.state = "awaiting_reboot"
        _ActionCenterSubTab._request_follow_up_check(tab)
        signal.emit.assert_called_once()


if __name__ == "__main__":
    unittest.main()
