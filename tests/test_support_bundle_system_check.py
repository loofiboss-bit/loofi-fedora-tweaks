"""System Check support-bundle bounds, linkage, and privacy contracts."""

from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import patch

from core.actions.contracts import FindingContext
from core.export.support_bundle_v11 import SupportBundleV11
from core.observability.snapshot import HealthSnapshot
from core.system_check.models import (
    FindingEvidence,
    SystemCheckResult,
    SystemFinding,
)


def _finding() -> SystemFinding:
    return SystemFinding.build(
        finding_id="root-disk-pressure",
        category="storage",
        severity="attention",
        title="Root filesystem needs attention",
        summary=(
            "Review /home/alice/report from host=private-host "
            "at 192.168.1.44 for a@example.com token=private."
        ),
        evidence=FindingEvidence.from_mapping(
            "maintenance",
            {
                "path": "/home/alice/report",
                "address": "192.168.1.44",
                "email": "a@example.com",
                "token": "private",
            },
            collected_at=10.0,
        ),
        applicable_variants=frozenset({"traditional", "atomic"}),
        freshness_state="fresh",
        affected_resources=("filesystem:/",),
        route_id="maintenance:cleanup",
        manual_guidance="Review the path.",
        manual_reason_code="disk-review",
    )


def _snapshot(
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


class TestSupportBundleSystemCheck(unittest.TestCase):
    @patch(
        "core.export.support_bundle_v10.SupportBundleV10.generate_bundle",
        return_value={"legacy": True},
    )
    @patch("core.observability.timeline.HealthTimelineStore")
    @patch("core.actions.stores.ActionPlanStore")
    @patch("core.actions.stores.ActionRunStore")
    def test_bundle_contains_bounded_comparison_and_linked_metadata(
        self,
        run_store_cls,
        plan_store_cls,
        timeline_store_cls,
        _legacy,
    ):
        finding = _finding()
        timeline_store_cls.return_value.load.return_value = [
            _snapshot("before", 10.0, (finding,)),
            _snapshot("after", 20.0),
        ]
        plan_store_cls.return_value.list_read_only.return_value = [
            SimpleNamespace(plan_id="plan-1", state="ready")
        ]
        run_store_cls.return_value.list_read_only.return_value = [
            SimpleNamespace(
                run_id="run-1",
                plan_id="plan-1",
                action_id="dnf-clean-all",
                state="succeeded",
                finding_context=FindingContext(
                    "before",
                    finding.fingerprint,
                    "b" * 64,
                    "health",
                    ("filesystem:/",),
                ),
                verification_result={
                    "success": True,
                    "message": "Verified from 10.0.0.8 token=private",
                },
                reboot_required=False,
                recovery_status="not-required",
                last_verified_at=15.0,
                updated_at=16.0,
            )
        ]

        bundle = SupportBundleV11.generate_bundle()

        self.assertEqual(bundle["support_bundle_version"], 11)
        evidence = bundle["system_check"]
        self.assertEqual(len(evidence["results"]), 2)
        self.assertEqual(
            evidence["comparison"]["counts"]["resolved"],
            1,
        )
        self.assertEqual(
            evidence["linked_maintenance"][0]["run_id"],
            "run-1",
        )
        self.assertFalse(evidence["raw_command_output_included"])
        encoded = str(bundle)
        for private in (
            "/home/alice",
            "192.168.1.44",
            "10.0.0.8",
            "a@example.com",
            "token=private",
        ):
            with self.subTest(private=private):
                self.assertNotIn(private, encoded)

    @patch(
        "core.export.support_bundle_v10.SupportBundleV10.generate_bundle",
        return_value={},
    )
    @patch("core.observability.timeline.HealthTimelineStore")
    @patch("core.actions.stores.ActionPlanStore")
    @patch("core.actions.stores.ActionRunStore")
    def test_bundle_does_not_collect_or_migrate_state(
        self,
        run_store_cls,
        plan_store_cls,
        timeline_store_cls,
        _legacy,
    ):
        timeline_store_cls.return_value.load.return_value = []
        plan_store_cls.return_value.list_read_only.return_value = []
        run_store_cls.return_value.list_read_only.return_value = []

        bundle = SupportBundleV11.generate_bundle()

        self.assertFalse(
            bundle["system_check"]["collection_started_by_export"]
        )
        plan_store_cls.return_value.list_read_only.assert_called_once_with(
            limit=50
        )
        run_store_cls.return_value.list_read_only.assert_called_once_with(
            limit=100
        )


if __name__ == "__main__":
    unittest.main()
