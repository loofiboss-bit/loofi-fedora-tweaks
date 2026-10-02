"""Orchestration tests for the closed, read-only System Check profile."""

from __future__ import annotations

import json
import tempfile
import threading
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

from core.actions.stores import ActionPlanStore, ActionRunStore
from core.diagnostics.daily_maintenance import MaintenanceCard
from core.system_check.models import FindingEvidence, SystemFinding
from core.system_check.service import CollectorSpec, SystemCheckService


class _TraditionalSystem:
    @staticmethod
    def is_atomic():
        return False

    @staticmethod
    def has_pending_deployment():
        return False


class _MemoryTimeline:
    def __init__(self):
        self.snapshots = []

    def append(self, snapshot):
        self.snapshots.append(snapshot)
        return snapshot


class _HealthyStateDoctor:
    @staticmethod
    def run():
        return {"findings": []}


class _CleanMaintenance:
    @staticmethod
    def collect_quick():
        return SimpleNamespace(atomic=False, cards=())


class _CleanReclaim:
    @staticmethod
    def analyze():
        return SimpleNamespace(atomic=False, categories=())


class _EmptyStore:
    @staticmethod
    def list_read_only():
        return []


class TestSystemCheckService(unittest.TestCase):
    def _service(self, collectors, timeline=None):
        return SystemCheckService(
            collectors=collectors,
            timeline_store=timeline or _MemoryTimeline(),
            system_manager=_TraditionalSystem,
        )

    def test_clean_fixture_completes_without_findings(self):
        timeline = _MemoryTimeline()
        service = self._service(
            (CollectorSpec("clean", 1.0, lambda _atomic, _at: ()),),
            timeline,
        )

        result = service.run()

        self.assertEqual(result.state, "completed")
        self.assertEqual(result.findings, ())
        self.assertEqual(result.completed_sources, ("clean",))
        self.assertEqual(result.profile_id, "system-check-fixture-v1")
        self.assertEqual(len(timeline.snapshots), 1)

    def test_production_quick_profile_is_closed_and_composes_existing_collectors(self):
        service = SystemCheckService(
            timeline_store=_MemoryTimeline(),
            state_doctor=_HealthyStateDoctor(),
            maintenance_service=_CleanMaintenance(),
            reclaim_service=_CleanReclaim(),
            plan_store=_EmptyStore(),
            run_store=_EmptyStore(),
            system_manager=_TraditionalSystem,
        )

        result = service.run(persist=False)

        self.assertEqual(result.profile_id, "system-check-quick-v1")
        self.assertEqual(
            result.completed_sources,
            (
                "action-center",
                "maintenance",
                "pending-reboot",
                "state-integrity",
                "storage-reclaim",
            ),
        )
        self.assertEqual(result.findings, ())

    def test_one_failed_collector_is_partial_not_false_healthy(self):
        def fail(_atomic, _at):
            raise RuntimeError("probe unavailable")

        service = self._service((
            CollectorSpec("clean", 1.0, lambda _atomic, _at: ()),
            CollectorSpec("failed", 1.0, fail),
        ))

        result = service.run(persist=False)

        self.assertEqual(result.state, "partial")
        self.assertEqual(result.completed_sources, ("clean",))
        self.assertEqual(result.source_errors[0].source_id, "failed")

    def test_progress_names_sources_elapsed_time_and_partial_failure(self):
        updates = []

        def fail(_atomic, _at):
            raise RuntimeError("probe unavailable")

        service = self._service((
            CollectorSpec("clean", 1.0, lambda _atomic, _at: ()),
            CollectorSpec("failed", 1.0, fail),
        ))

        result = service.run(persist=False, progress_callback=updates.append)

        self.assertEqual(result.state, "partial")
        self.assertTrue(any(update.source_id == "clean" for update in updates))
        self.assertTrue(any(update.source_id == "failed" for update in updates))
        self.assertTrue(all(update.elapsed_seconds >= 0.0 for update in updates))
        self.assertEqual(updates[-1].percentage, 100)
        self.assertEqual(updates[-1].unavailable_sources, ("failed",))

    def _maintenance_check(self, cards, updates=None, timeline=None):
        service = self._service((CollectorSpec("maintenance", 1.0, lambda _atomic, _at: ()),), timeline)
        service.maintenance_service = Mock()
        service.maintenance_service.collect_quick.return_value = SimpleNamespace(atomic=False, cards=cards)
        service.collectors = (CollectorSpec("maintenance", 1.0, service._collect_maintenance),)
        return service.run(progress_callback=updates.append if updates is not None else None)

    def test_root_disk_thresholds_use_real_df_usage(self):
        for percentage, severity in ((89, None), (90, "attention"), (95, "critical"), (96, "critical")):
            with self.subTest(percentage=percentage):
                card = MaintenanceCard("disk-usage", "Disk Usage", "success", "Root filesystem usage is available.", details=f"/dev/root 100G 96G 4G {percentage}% /")
                result = self._maintenance_check([card])
                self.assertEqual(result.state, "completed")
                self.assertEqual(result.source_errors, ())
                if severity is None:
                    self.assertEqual(result.findings, ())
                else:
                    self.assertEqual(result.findings[0].finding_id, "root-disk-pressure")
                    self.assertEqual(result.findings[0].severity, severity)
                    self.assertEqual(result.findings[0].evidence.facts_dict()["root_usage_percent"], percentage)

    def test_valid_findings_survive_multiple_errors_in_same_collector(self):
        updates = []
        timeline = _MemoryTimeline()
        cards = [
            MaintenanceCard("disk-usage", "Disk Usage", "success", "Review usage", details="96% /"),
            MaintenanceCard("failed-services", "Failed Services", "error", "Permission denied", error_reason_code="probe-permission-denied"),
            MaintenanceCard("package-health", "Package Health", "error", "Timed out", error_reason_code="probe-timeout"),
        ]

        result = self._maintenance_check(cards, updates, timeline)

        self.assertEqual(result.state, "partial")
        self.assertEqual(result.completed_sources, ("maintenance",))
        self.assertEqual(result.findings[0].finding_id, "root-disk-pressure")
        self.assertEqual(len(result.source_errors), 2)
        self.assertEqual({error.source_id for error in result.source_errors}, {"maintenance"})
        self.assertEqual({error.reason_code for error in result.source_errors}, {
            "failed-services-probe-permission-denied", "package-health-probe-timeout",
        })
        self.assertTrue(next(error for error in result.source_errors if error.reason_code.endswith("timeout")).timed_out)
        self.assertTrue(all(error.duration_ms >= 0 for error in result.source_errors))
        self.assertEqual(updates[-1].completed_sources, 1)
        self.assertEqual(updates[-1].percentage, 100)
        self.assertEqual(updates[-1].unavailable_sources, ("maintenance",))
        self.assertTrue(all(update.completed_sources <= update.total_sources for update in updates))
        self.assertEqual(len(timeline.snapshots), 1)
        self.assertEqual(len(timeline.snapshots[0].daily_maintenance["system_check"]["source_errors"]), 2)

    def test_failed_service_query_is_a_source_error_without_fake_finding(self):
        timeline = _MemoryTimeline()
        result = self._maintenance_check([
            MaintenanceCard("failed-services", "Failed Services", "error", "The query returned no result.", error_reason_code="probe-unavailable"),
        ], timeline=timeline)

        self.assertEqual(result.state, "failed")
        self.assertEqual(result.completed_sources, ())
        self.assertEqual(result.findings, ())
        self.assertEqual(result.source_errors[0].reason_code, "failed-services-probe-unavailable")
        self.assertEqual(timeline.snapshots, [])

    def test_invalid_disk_output_is_partial_and_does_not_hide_service_finding(self):
        result = self._maintenance_check([
            MaintenanceCard("disk-usage", "Disk Usage", "success", "Root filesystem usage is available.", details="101% /"),
            MaintenanceCard("failed-services", "Failed Services", "warning", "One failed unit", details="demo.service loaded failed failed Demo"),
        ])

        self.assertEqual(result.state, "partial")
        self.assertEqual(result.source_errors[0].reason_code, "disk-usage-probe-invalid-output")
        self.assertEqual([finding.finding_id for finding in result.findings], ["failed-service"])

    def test_maintenance_variant_conflict_remains_isolated_failure(self):
        service = self._service((CollectorSpec("maintenance", 1.0, lambda _atomic, _at: ()),))
        service.maintenance_service = Mock()
        service.maintenance_service.collect_quick.return_value = SimpleNamespace(atomic=True, cards=[])
        service.collectors = (CollectorSpec("maintenance", 1.0, service._collect_maintenance),)
        result = service.run(persist=False)
        self.assertEqual(result.state, "failed")
        self.assertEqual(result.source_errors[0].reason_code, "collector-failed")

    def test_collector_timeout_is_partial_and_bounded(self):
        release = threading.Event()

        def block(_atomic, _at):
            release.wait(1.0)
            return ()

        service = self._service((
            CollectorSpec("clean", 1.0, lambda _atomic, _at: ()),
            CollectorSpec("slow", 0.02, block),
        ))

        result = service.run(persist=False)
        release.set()

        self.assertEqual(result.state, "partial")
        self.assertEqual(result.source_errors[0].reason_code, "collector-timeout")
        self.assertTrue(result.source_errors[0].timed_out)

    def test_completed_finding_has_explicit_variant_and_no_command(self):
        def find(_atomic, collected_at):
            evidence = FindingEvidence.from_mapping(
                "fixture",
                {"condition": "needs-review"},
                collected_at=collected_at,
            )
            return (SystemFinding.build(
                finding_id="fixture",
                category="fixture",
                severity="attention",
                title="Fixture",
                summary="Review fixture",
                evidence=evidence,
                applicable_variants=frozenset({"traditional"}),
                freshness_state="fresh",
                manual_guidance="Review manually.",
                manual_reason_code="fixture-review",
            ),)

        result = self._service((CollectorSpec("fixture", 1.0, find),)).run(persist=False)

        self.assertEqual(result.state, "completed")
        self.assertEqual(result.findings[0].applicable_variants, frozenset({"traditional"}))
        self.assertNotIn("command", str(result.findings[0].to_dict()))

    def test_cancellation_persists_nothing_and_cancels_pending(self):
        entered = threading.Event()
        release = threading.Event()
        cancellation = threading.Event()
        timeline = _MemoryTimeline()

        def block(_atomic, _at):
            entered.set()
            release.wait(2.0)
            return ()

        collectors = tuple(
            CollectorSpec(f"blocked-{index}", 5.0, block)
            for index in range(5)
        )
        service = self._service(collectors, timeline)
        holder = {}

        def run():
            holder["result"] = service.run(cancel_event=cancellation)

        thread = threading.Thread(target=run)
        thread.start()
        self.assertTrue(entered.wait(1.0))
        cancellation.set()
        thread.join(1.0)
        release.set()
        self.assertFalse(thread.is_alive())
        result = holder["result"]
        self.assertEqual(result.state, "cancelled")
        self.assertTrue(result.cancelled_sources)
        self.assertEqual(timeline.snapshots, [])

    def test_read_only_action_store_access_preserves_v1_bytes(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            plan_path = root / "plans.json"
            run_path = root / "runs.jsonl"
            plan_payload = {
                "schema_version": 1,
                "plans": [{
                    "plan_id": "plan-1",
                    "action_id": "dnf-clean-all",
                    "parameters": {},
                    "target": "traditional",
                    "digest": "digest",
                    "preview": ["dnf", "clean", "all"],
                    "policy_decision": {
                        "allowed": False,
                        "reason_code": "manual",
                        "explanation": "Review",
                    },
                    "risk_level": "low",
                    "privileged": True,
                    "confirmation_policy": "explicit",
                    "recovery_guidance": "Review",
                    "rollback_supported": True,
                }],
            }
            plan_path.write_text(json.dumps(plan_payload), encoding="utf-8")
            run_path.write_text("", encoding="utf-8")
            before = plan_path.read_bytes()

            plans = ActionPlanStore(plan_path).list_read_only()
            runs = ActionRunStore(run_path).list_read_only()

            self.assertEqual(len(plans), 1)
            self.assertEqual(runs, [])
            self.assertEqual(plan_path.read_bytes(), before)


if __name__ == "__main__":
    unittest.main()
