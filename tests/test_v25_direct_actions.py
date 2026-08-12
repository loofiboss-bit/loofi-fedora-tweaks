"""v25 Proof direct-action lifecycle and outcome tests."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock

from core.actions import ActionCatalog, ActionCenterOrchestrator, DirectActionService
from core.actions.contracts import ActionPlan, ActionRun, PolicyDecision
from core.actions.outcomes import OutcomeEvidenceComposer
from core.actions.stores import ActionPlanStore, ActionRunStore
from core.executor.action_result import ActionResult
from core.settings.execution import ExecutionSettings, ExecutionSettingsStore


class _Runtime:
    def __init__(self):
        self.failed = ["broken.service"]

    def is_atomic(self):
        return False

    def package_manager(self):
        return "dnf"

    def fedora_version(self):
        return "44"

    def boot_id(self):
        return "boot-test"

    def package_manager_busy(self):
        return False

    def failed_services(self):
        return True, list(self.failed), ""

    def fstrim_support(self):
        return True, {"discard_supported": True}, ""

    def execute_read_only(self, vector, *, action_id, timeout=30):
        if vector[:2] == ["systemctl", "is-active"]:
            return ActionResult.ok("active", stdout="active\n", exit_code=0, action_id=action_id)
        return ActionResult.ok("healthy", stdout="healthy\n", exit_code=0, action_id=action_id)


class _Settings:
    def __init__(self, settings=None):
        self.settings = settings or ExecutionSettings()

    def load(self):
        return self.settings


class TestV25DirectActions(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        root = Path(self.temp.name)
        self.facade = MagicMock()
        self.facade.execute.return_value = ActionResult.ok("cleaned", exit_code=0)
        self.orchestrator = ActionCenterOrchestrator(
            facade=self.facade,
            runtime=_Runtime(),
            catalog=ActionCatalog(),
            plan_store=ActionPlanStore(root / "plans.json"),
            run_store=ActionRunStore(root / "runs.jsonl"),
            lease_path=root / "lease",
            id_factory=iter([f"id-{i}" for i in range(100)]).__next__,
            recover_interrupted=False,
        )

    def tearDown(self):
        self.temp.cleanup()

    def test_low_risk_runs_through_action_center_and_independent_verify(self):
        service = DirectActionService(orchestrator=self.orchestrator, settings_store=_Settings())
        result = service.run("dnf-clean-all")
        self.assertEqual(result.status, "completed_verified")
        self.assertEqual(result.outcome.state, "verified")
        self.assertEqual(self.facade.execute.call_args.kwargs["authority"], "action_center")
        self.assertEqual(self.facade.execute.call_count, 1)

    def test_medium_risk_requires_compact_confirmation(self):
        service = DirectActionService(orchestrator=self.orchestrator, settings_store=_Settings())
        result = service.run("restart-failed-service", {"service": "broken.service"})
        self.assertEqual(result.status, "review_required")
        self.assertTrue(result.confirmation_required)
        self.facade.execute.assert_not_called()

    def test_yes_allows_medium_risk_but_not_high_risk(self):
        service = DirectActionService(orchestrator=self.orchestrator, settings_store=_Settings())
        self.facade.execute.side_effect = self._complete_failed_service
        medium = service.run("restart-failed-service", {"service": "broken.service"}, yes=True)
        high = service.run("update-firmware", yes=True)
        self.assertEqual(medium.status, "completed_verified")
        self.assertIn(high.status, {"review_required", "blocked_by_preflight"})

    def _complete_failed_service(self, *args, **kwargs):
        self.orchestrator.runtime.failed = []
        return ActionResult.ok("restarted", exit_code=0)

    def test_review_first_and_dry_run_never_execute(self):
        service = DirectActionService(
            orchestrator=self.orchestrator,
            settings_store=_Settings(ExecutionSettings(execution_mode="review_first")),
        )
        review = service.run("dnf-clean-all")
        dry_run = service.run("dnf-clean-all", dry_run=True)
        self.assertEqual(review.status, "review_required")
        self.assertEqual(dry_run.status, "preview")
        self.assertTrue(dry_run.dry_run)
        self.facade.execute.assert_not_called()

    def test_preflight_block_is_truthful_and_no_fallback_command_runs(self):
        runtime = _Runtime()
        runtime.atomic = True
        runtime.is_atomic = lambda: True
        runtime.package_manager = lambda: "rpm-ostree"
        orchestrator = ActionCenterOrchestrator(
            facade=self.facade,
            runtime=runtime,
            catalog=ActionCatalog(),
            plan_store=self.orchestrator.plan_store,
            run_store=self.orchestrator.run_store,
            lease_path=self.orchestrator.lease_path,
            recover_interrupted=False,
        )
        result = DirectActionService(orchestrator=orchestrator, settings_store=_Settings()).run("dnf-clean-all")
        self.assertEqual(result.status, "blocked_by_preflight")
        self.facade.execute.assert_not_called()

    def test_auto_verify_can_be_disabled_without_claiming_verified(self):
        service = DirectActionService(
            orchestrator=self.orchestrator,
            settings_store=_Settings(ExecutionSettings(automatically_verify=False)),
        )
        result = service.run("dnf-clean-all")
        self.assertEqual(result.status, "review_required")
        self.assertEqual(result.outcome.state, "partially_verified")

    def test_reboot_required_run_is_typed_without_claiming_final_verification(self):
        orchestrator = MagicMock()
        orchestrator.catalog = ActionCatalog()
        orchestrator.plan.return_value = self._plan()
        orchestrator.apply.return_value = ActionRun(
            run_id="run-reboot",
            plan_id="plan-proof",
            action_id="dnf-clean-all",
            correlation_id="corr-reboot",
            state="awaiting_reboot",
            reboot_required=True,
            execution_result={"success": True, "needs_reboot": True, "message": "Staged."},
        )

        result = DirectActionService(orchestrator=orchestrator, settings_store=_Settings()).run("dnf-clean-all")

        self.assertEqual(result.status, "completed_awaiting_reboot")
        self.assertEqual(result.outcome.state, "awaiting_reboot")
        self.assertEqual(result.exit_code, 0)
        orchestrator.verify.assert_not_called()

    def test_verification_failure_is_not_downgraded_to_success(self):
        orchestrator = MagicMock()
        orchestrator.catalog = ActionCatalog()
        orchestrator.plan.return_value = self._plan()
        orchestrator.apply.return_value = ActionRun(
            run_id="run-failed-verification",
            plan_id="plan-proof",
            action_id="dnf-clean-all",
            correlation_id="corr-failed",
            state="verification_failed",
            execution_result={"success": True, "message": "Executed."},
            verification_result={"success": False, "message": "Readback failed."},
        )

        result = DirectActionService(orchestrator=orchestrator, settings_store=_Settings()).run("dnf-clean-all")

        self.assertEqual(result.status, "completed_verification_failed")
        self.assertEqual(result.outcome.state, "verification_failed")
        self.assertEqual(result.exit_code, 6)

    def _plan(self) -> ActionPlan:
        return ActionPlan(
            plan_id="plan-proof",
            action_id="dnf-clean-all",
            parameters={},
            target="44",
            digest="a" * 64,
            preview=["dnf", "clean", "all"],
            policy_decision=PolicyDecision(True, "preflight_ok", "Ready."),
            risk_level="low",
            privileged=True,
            confirmation_policy="explicit",
            recovery_guidance="Review package health if needed.",
            rollback_supported=True,
            affected_resources=("package-cache",),
        )


class TestOutcomeEvidence(unittest.TestCase):
    def test_exit_zero_without_verifier_is_not_verified(self):
        from core.actions.contracts import ActionPlan, PolicyDecision

        plan = ActionPlan(
            "plan", "dnf-clean-all", {}, "44", "digest", ["dnf", "clean", "all"],
            PolicyDecision(True, "preflight_ok", "Ready."), "low", True, "explicit",
            "Review Action Center recovery guidance.", True, affected_resources=("dnf",),
        )
        summary = OutcomeEvidenceComposer().compose(plan)
        self.assertEqual(summary.state, "unverified")
        self.assertNotEqual(summary.state, "verified")


if __name__ == "__main__":
    unittest.main()
