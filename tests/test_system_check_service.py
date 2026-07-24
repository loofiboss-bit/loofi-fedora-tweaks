"""Orchestration tests for the closed, read-only System Check profile."""

from __future__ import annotations

import json
import tempfile
import threading
import unittest
from pathlib import Path
from types import SimpleNamespace

from core.actions.stores import ActionPlanStore, ActionRunStore
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
