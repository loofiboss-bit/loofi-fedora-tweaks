"""Action Center v4 finding-context trust-boundary tests."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock

from core.actions import (
    ActionCenterOrchestrator,
    ActionPlanIntegrityError,
    ActionPlanRejectedError,
    ActionPlanStore,
    ActionRunStore,
    FindingContext,
)
from core.actions.contracts import ActionDefinition, PolicyDecision
from core.actions.catalog import ActionCatalog
from core.executor.action_result import ActionResult
from core.system_check.handoff import (
    FindingActionReview,
    FindingHandoffError,
)


class Runtime:
    def __init__(self):
        self.preflight_calls = 0

    def is_atomic(self):
        return False

    def package_manager(self):
        return "dnf"

    def fedora_version(self):
        return "44"

    def boot_id(self):
        return "boot-1"

    def package_manager_busy(self):
        return False

    def failed_services(self):
        return True, [], ""

    def fstrim_support(self):
        return True, {"fstrim_available": True, "discard_supported": True}, ""

    def execute_read_only(self, vector, *, action_id, timeout=30):
        return ActionResult.ok("healthy", action_id=action_id)


class Resolver:
    def __init__(self, review):
        self.review = review
        self.calls = []

    def resolve(self, **context):
        self.calls.append(context)
        return self.review


def _context() -> FindingContext:
    return FindingContext(
        "check-1",
        "a" * 64,
        "b" * 64,
        "health",
        ("filesystem:/",),
    )


class TestActionCenterSteward(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        root = Path(self.temp.name)
        self.runtime = Runtime()
        self.facade = MagicMock()
        self.render_calls = 0

        def render(_parameters, _runtime):
            self.render_calls += 1
            return ["fstrim", "-av"]

        def preflight(_parameters, runtime):
            runtime.preflight_calls += 1
            return PolicyDecision(True, "preflight_ok", "Ready.")

        definition = ActionDefinition(
            id="fixture-safe-action",
            capability_id="fixture.safe",
            title="Fixture safe action",
            description="Fixture.",
            parameter_schema={},
            risk_level="low",
            privileged=False,
            confirmation_policy="explicit",
            recovery_guidance="No recovery needed.",
            rollback_supported=True,
            command_renderer=render,
            preflight_checker=preflight,
            verifier=lambda _run, _plan, _runtime: ActionResult.ok("verified"),
            affected_resources=("fixture",),
        )
        review = FindingActionReview(
            "fixture-safe-action",
            (),
            _context(),
        )
        self.resolver = Resolver(review)
        ids = iter(f"id-{index}" for index in range(20))
        self.orchestrator = ActionCenterOrchestrator(
            facade=self.facade,
            catalog=ActionCatalog([definition]),
            plan_store=ActionPlanStore(root / "plans.json"),
            run_store=ActionRunStore(root / "runs.jsonl"),
            lease_path=root / "lease",
            runtime=self.runtime,
            clock=lambda: 1000.0,
            id_factory=lambda: next(ids),
            finding_handoff=self.resolver,
        )

    def tearDown(self):
        for run_id in list(self.orchestrator._held_leases):
            self.orchestrator.interrupt_run(run_id, "test-cleanup")
        self.temp.cleanup()

    def _plan(self):
        return self.orchestrator.plan_from_finding(
            check_result_id="check-1",
            finding_fingerprint="a" * 64,
            origin_route="health",
            expected_action_id="fixture-safe-action",
        )

    def test_context_is_linked_without_bypassing_fresh_preflight(self):
        plan = self._plan()

        self.assertEqual(plan.finding_context, _context())
        self.assertEqual(self.render_calls, 1)
        self.assertEqual(self.runtime.preflight_calls, 1)

        prepared = self.orchestrator.prepare_run(plan.plan_id, confirmed=True)
        run = self.orchestrator.get_run(prepared.run_id)

        self.assertEqual(prepared.command, ("fstrim", "-av"))
        self.assertEqual(self.render_calls, 2)
        self.assertEqual(self.runtime.preflight_calls, 2)
        self.assertEqual(run.finding_context, plan.finding_context)

    def test_tampered_context_invalidates_plan_integrity(self):
        plan = self._plan()
        plan.finding_context = FindingContext(
            "check-1",
            "c" * 64,
            "b" * 64,
            "health",
            ("filesystem:/",),
        )
        self.orchestrator.plan_store.save(plan)

        with self.assertRaises(ActionPlanIntegrityError):
            self.orchestrator.prepare_run(plan.plan_id, confirmed=True)

    def test_mismatched_action_and_missing_confirmation_fail_closed(self):
        with self.assertRaises(FindingHandoffError) as mismatch:
            self.orchestrator.plan_from_finding(
                check_result_id="check-1",
                finding_fingerprint="a" * 64,
                origin_route="health",
                expected_action_id="different-action",
            )
        self.assertEqual(mismatch.exception.reason_code, "finding_action_mismatch")
        self.assertEqual(self.orchestrator.plan_store.list(), [])

        plan = self._plan()
        with self.assertRaises(ActionPlanRejectedError) as unconfirmed:
            self.orchestrator.prepare_run(plan.plan_id, confirmed=False)
        self.assertEqual(
            unconfirmed.exception.decision.reason_code,
            "confirmation_required",
        )
        self.facade.execute.assert_not_called()

    def test_plan_without_context_keeps_v18_behavior(self):
        plan = self.orchestrator.plan("fixture-safe-action")
        path = self.orchestrator.plan_store.path
        payload = json.loads(path.read_text(encoding="utf-8"))
        payload["schema_version"] = 3
        path.write_text(json.dumps(payload), encoding="utf-8")

        self.assertIsNone(plan.finding_context)
        prepared = self.orchestrator.prepare_run(plan.plan_id, confirmed=True)
        self.assertEqual(prepared.action_id, "fixture-safe-action")
        self.assertEqual(
            json.loads(path.read_text(encoding="utf-8"))["schema_version"],
            4,
        )


if __name__ == "__main__":
    unittest.main()
