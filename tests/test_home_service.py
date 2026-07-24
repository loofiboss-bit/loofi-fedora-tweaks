"""Tests for the PyQt-free canonical Home composition."""

from __future__ import annotations

import unittest
from types import SimpleNamespace

from core.actions.contracts import (
    ActionPlan,
    ActionRun,
    FindingContext,
    PolicyDecision,
)
from core.home import HomeService, Recommendation, select_primary_recommendation
from core.observability.snapshot import HealthSnapshot
from core.system_check.models import (
    FindingEvidence,
    SystemCheckResult,
    SystemFinding,
)


class _ListSource:
    last_error = ""

    def __init__(self, values=(), error: Exception | None = None):
        self.values = list(values)
        self.error = error
        self.read_only_calls = 0

    def load(self):
        if self.error:
            raise self.error
        return list(self.values)

    def list(self, *, limit=None):
        if self.error:
            raise self.error
        return list(self.values[-limit:] if limit else self.values)

    def list_read_only(self, *, limit=None):
        self.read_only_calls += 1
        if self.error:
            raise self.error
        return list(self.values[-limit:] if limit else self.values)


class _StateSource:
    def __init__(self, findings=(), error: Exception | None = None):
        self.findings = list(findings)
        self.error = error

    def run(self):
        if self.error:
            raise self.error
        return {"status": "healthy" if not self.findings else "error", "findings": self.findings}


class _HistorySource:
    def __init__(self, entries=()):
        self.entries = list(entries)

    def get_recent(self, count=1):
        return self.entries[:count]


class _NotificationSource:
    def __init__(self, entries=()):
        self.entries = list(entries)

    def get_recent(self, limit=1):
        return self.entries[:limit]


def _snapshot(now: float, **overrides) -> HealthSnapshot:
    values = {
        "timestamp": now,
        "app_version": "14.0.0",
        "app_codename": "Helm",
        "fedora_target": "44",
        "atomic": False,
        "daily_maintenance": {"cards": []},
        "action_center_summary": {},
    }
    values.update(overrides)
    return HealthSnapshot(**values)


def _check_snapshot(
    check_id: str,
    completed_at: float,
    findings=(),
) -> HealthSnapshot:
    return HealthSnapshot.from_system_check(
        SystemCheckResult(
            check_id,
            "system-check-quick-v1",
            "completed",
            False,
            completed_at - 1,
            completed_at,
            tuple(findings),
            (),
            (),
            ("maintenance",),
        )
    )


def _disk_finding() -> SystemFinding:
    return SystemFinding.build(
        finding_id="root-disk-pressure",
        category="storage",
        severity="attention",
        title="Root filesystem needs attention",
        summary="Root usage is high.",
        evidence=FindingEvidence.from_mapping(
            "maintenance",
            {"root_usage_percent": 92.0, "state": "warning"},
            collected_at=90_000.0,
        ),
        applicable_variants=frozenset({"traditional", "atomic"}),
        freshness_state="fresh",
        affected_resources=("filesystem:/",),
        route_id="maintenance:cleanup",
        manual_guidance="Review reclaimable data.",
        manual_reason_code="disk-review",
    )


def _service(
    *, now=100_000.0, snapshots=(), findings=(), plans=(), runs=(), history=(), notifications=(), snapshot_error=None
):
    return HomeService(
        snapshot_store=_ListSource(snapshots, snapshot_error),
        state_source=_StateSource(findings),
        plan_store=_ListSource(plans),
        run_store=_ListSource(runs),
        history_source=_HistorySource(history),
        notification_source=_NotificationSource(notifications),
        clock=lambda: now,
    )


class TestRecommendationOrdering(unittest.TestCase):
    def test_order_is_deterministic_and_matches_phase_five_contract(self):
        kinds = [
            "no_action", "action_center_review", "repeated_health", "missing_backup",
            "pending_updates", "failed_update", "disk_pressure", "pending_reboot",
            "action_run_review", "state_integrity",
        ]
        recommendations = [Recommendation(kind, kind, kind, kind, "settings") for kind in kinds]

        selected = select_primary_recommendation(reversed(recommendations))

        self.assertIsNotNone(selected)
        self.assertEqual(selected.kind, "state_integrity")


class TestHomeServiceStates(unittest.TestCase):
    def test_fresh_empty_signal_snapshot_reports_good(self):
        summary = _service(snapshots=[_snapshot(100_000.0)]).summary()

        self.assertEqual(summary.data_state, "fresh")
        self.assertEqual(summary.overall_state, "good")
        self.assertEqual(summary.primary_recommendation.kind, "no_action")
        self.assertEqual(len(summary.common_tasks), 4)
        self.assertEqual(
            [(item.id, item.state) for item in summary.status_items],
            [
                ("health", "good"),
                ("updates", "unknown"),
                ("storage", "unknown"),
                ("recovery", "unknown"),
            ],
        )

    def test_explicit_saved_payloads_drive_four_truthful_status_areas(self):
        snapshot = _snapshot(
            100_000.0,
            daily_maintenance={
                "cards": [{"id": "system-updates", "state": "current", "summary": "Up to date"}],
            },
            package_manager_health_summary={"state": "healthy", "summary": "Package manager healthy"},
            disk_usage_summary={"state": "good", "summary": "Disk use is healthy"},
            rollback_snapshot_availability={"state": "available", "summary": "Recovery point available"},
        )

        summary = _service(snapshots=[snapshot]).summary()

        self.assertEqual(
            [(item.id, item.state) for item in summary.status_items],
            [
                ("health", "good"),
                ("updates", "good"),
                ("storage", "good"),
                ("recovery", "good"),
            ],
        )

    def test_stale_snapshot_never_promotes_unsignaled_status_to_good(self):
        snapshot = _snapshot(
            1.0,
            disk_usage_summary={"state": "good", "summary": "Previously healthy"},
        )

        summary = _service(snapshots=[snapshot]).summary()

        self.assertTrue(all(item.state != "good" for item in summary.status_items))
        self.assertEqual(summary.status_items[2].state, "unknown")

    def test_stale_snapshot_is_explicit_without_collecting(self):
        summary = _service(snapshots=[_snapshot(1.0)]).summary()

        self.assertEqual(summary.data_state, "stale")
        self.assertEqual(summary.primary_recommendation.kind, "stale_data")

    def test_source_error_is_contained_in_error_state(self):
        summary = _service(snapshot_error=OSError("unreadable")).summary()

        self.assertEqual(summary.data_state, "error")
        self.assertEqual(summary.overall_state, "attention")
        self.assertIn("unreadable", summary.source_errors[0])

    def test_snapshot_collection_error_is_not_reported_as_healthy(self):
        snapshot = _snapshot(100_000.0, collection_errors=["package probe failed"])

        summary = _service(snapshots=[snapshot]).summary()

        self.assertEqual(summary.data_state, "error")
        self.assertEqual(summary.primary_recommendation.kind, "source_error")

    def test_no_saved_sources_returns_empty_unknown_state(self):
        summary = _service().summary()

        self.assertEqual(summary.data_state, "empty")
        self.assertEqual(summary.overall_state, "attention")
        self.assertEqual(summary.primary_recommendation.kind, "first_health_review")
        self.assertEqual(summary.primary_recommendation.route_id, "maintenance:health-timeline")
        self.assertIsNone(summary.last_checked_at)
        self.assertEqual(summary.freshness_state, "unavailable")
        self.assertTrue(summary.check_now_available)

    def test_last_checked_and_freshness_follow_latest_saved_snapshot(self):
        summary = _service(snapshots=[_snapshot(100_000.0)]).summary()

        self.assertEqual(summary.last_checked_at.timestamp(), 100_000.0)
        self.assertEqual(summary.freshness_state, "fresh")

        stale = _service(snapshots=[_snapshot(1.0)]).summary()
        self.assertEqual(stale.freshness_state, "stale")

    def test_nested_system_check_finding_drives_home_without_execution(self):
        snapshot = _snapshot(
            100_000.0,
            daily_maintenance={
                "cards": [],
                "system_check": {
                    "state": "completed",
                    "findings": [{
                        "finding_id": "root-disk-pressure",
                        "fingerprint": "disk-fingerprint",
                        "title": "Root filesystem needs attention",
                        "summary": "Root usage is 96 percent.",
                        "severity": "critical",
                        "route_id": "maintenance:cleanup",
                        "action_id": "",
                    }],
                    "source_errors": [],
                },
            },
        )

        summary = _service(snapshots=[snapshot]).summary()

        self.assertEqual(summary.primary_recommendation.kind, "disk_pressure")
        self.assertEqual(summary.primary_recommendation.severity, "critical")
        self.assertEqual(summary.primary_recommendation.route_id, "maintenance:cleanup")
        self.assertEqual(summary.last_check_state, "completed")

    def test_partial_system_check_names_unavailable_source_and_is_not_good(self):
        snapshot = _snapshot(
            100_000.0,
            collection_errors=["maintenance: collector-timeout"],
            daily_maintenance={
                "cards": [],
                "system_check": {
                    "state": "partial",
                    "findings": [],
                    "source_errors": [{
                        "source_id": "maintenance",
                        "reason_code": "collector-timeout",
                    }],
                },
            },
        )

        summary = _service(snapshots=[snapshot]).summary()

        self.assertEqual(summary.data_state, "error")
        self.assertNotEqual(summary.overall_state, "good")
        self.assertEqual(summary.primary_recommendation.kind, "system_check_partial")
        self.assertIn("maintenance", summary.primary_recommendation.summary)
        self.assertEqual(summary.last_check_state, "partial")

    def test_critical_state_integrity_is_first(self):
        snapshot = _snapshot(
            100_000.0,
            daily_maintenance={"cards": [{"id": "system-updates", "state": "warning", "summary": "Updates available"}]},
        )
        finding = {"severity": "error", "summary": "State schema is corrupt"}

        summary = _service(snapshots=[snapshot], findings=[finding]).summary()

        self.assertEqual(summary.overall_state, "critical")
        self.assertEqual(summary.primary_recommendation.kind, "state_integrity")
        self.assertLessEqual(len(summary.attention_items), 3)

    def test_interrupted_action_run_links_to_action_center_without_execution(self):
        run = ActionRun("run-1", "plan-1", "dnf-clean-all", "corr", state="interrupted", updated_at=99_000.0)

        summary = _service(snapshots=[_snapshot(100_000.0)], runs=[run]).summary()

        self.assertEqual(summary.primary_recommendation.kind, "action_run_review")
        self.assertEqual(summary.primary_recommendation.route_id, "maintenance:action-center")
        self.assertIn("interrupted", summary.primary_recommendation.summary)

    def test_verified_link_requires_a_later_check_before_resolution(self):
        finding = _disk_finding()
        context = FindingContext(
            "check-before",
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
            updated_at=99_000.0,
            last_verified_at=99_000.0,
            verification_result={"success": True},
        )

        summary = _service(
            snapshots=[
                _check_snapshot("check-before", 90_000.0, (finding,)),
                _check_snapshot("check-too-early", 98_000.0),
            ],
            runs=[run],
        ).summary()

        self.assertEqual(
            summary.primary_recommendation.kind,
            "resolution_check",
        )

        resolved = _service(
            snapshots=[
                _check_snapshot("check-before", 90_000.0, (finding,)),
                _check_snapshot("check-after", 100_000.0),
            ],
            runs=[run],
        ).summary()

        self.assertEqual(resolved.primary_recommendation.kind, "no_action")

    def test_awaiting_reboot_is_separate_from_resolution(self):
        finding = _disk_finding()
        run = ActionRun(
            "run-reboot",
            "plan-reboot",
            "atomic-update",
            "corr",
            finding_context=FindingContext(
                "check-before",
                finding.fingerprint,
                "b" * 64,
                "health",
                ("rpm-ostree-deployment",),
            ),
            state="awaiting_reboot",
            reboot_required=True,
            updated_at=99_000.0,
        )

        summary = _service(
            snapshots=[_check_snapshot("check-before", 90_000.0, (finding,))],
            runs=[run],
        ).summary()

        self.assertEqual(summary.primary_recommendation.kind, "pending_reboot")
        self.assertIn("reboot", summary.primary_recommendation.summary.lower())

    def test_ready_plan_and_snapshot_candidates_are_counted_for_review_only(self):
        plan = ActionPlan(
            "plan-1", "dnf-clean-all", {}, "44", "digest", ["dnf", "clean", "all"],
            PolicyDecision(True, "ok", "ok"), "low", True, "explicit", "guidance", False,
            state="ready", created_at=90_000.0, expires_at=101_000.0,
        )
        snapshot = _snapshot(100_000.0, action_center_summary={"candidate_count": 3})

        summary = _service(snapshots=[snapshot], plans=[plan]).summary()

        self.assertEqual(summary.primary_recommendation.kind, "action_center_review")
        self.assertEqual(summary.primary_recommendation.count, 3)

    def test_recent_change_is_single_and_never_undone_by_composition(self):
        entry = SimpleNamespace(id="change-1", timestamp="2026-07-18T09:00:00", description="Changed theme", undo_command=["gsettings"])

        summary = _service(snapshots=[_snapshot(100_000.0)], history=[entry]).summary()

        self.assertEqual(summary.recent_change.id, "change-1")
        self.assertTrue(summary.recent_change.undo_available)

    def test_newer_notification_reuses_single_read_only_activity_slot(self):
        entry = SimpleNamespace(id="change-1", timestamp="1970-01-02T00:00:00+00:00", description="Changed theme", undo_command=[])
        notification = SimpleNamespace(id="notice-1", timestamp=90_000.0, title="Agent failed", message="Review the saved error")

        summary = _service(
            snapshots=[_snapshot(100_000.0)],
            history=[entry],
            notifications=[notification],
        ).summary()

        self.assertEqual(summary.recent_change.id, "notification:notice-1")
        self.assertEqual(summary.recent_change.description, "Agent failed: Review the saved error")
        self.assertFalse(summary.recent_change.undo_available)


if __name__ == "__main__":
    unittest.main()
