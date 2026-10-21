"""A resolved transaction and its visible facts share one observation."""

import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

from core.actions.catalog import ActionCatalog
from core.actions.contracts import ActionDefinition, PolicyDecision, VerificationDecision
from core.actions.orchestrator import ActionCenterOrchestrator, ActionPlanRejectedError
from core.actions.stores import ActionPlanStore, ActionRunStore
from core.executor.action_result import ActionResult


class EvidenceRendererTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        root = Path(self.temp.name)
        self.preflight = Mock(return_value=PolicyDecision(True, "ready", "Reviewed", facts={"revision": 1}))
        self.renderer = Mock(return_value=["dnf5", "clean", "all"])
        self.legacy_renderer = Mock(side_effect=AssertionError("Must use reviewed evidence"))
        self.definition = ActionDefinition(
            id="dnf-clean-all", capability_id="maintenance.dnf.clean", title="Clean cache", description="Test resolved evidence",
            parameter_schema={}, risk_level="low", privileged=False, confirmation_policy="explicit", recovery_guidance="No rollback",
            rollback_supported=False, command_renderer=self.legacy_renderer, preflight_checker=self.preflight,
            verifier=lambda *_args: VerificationDecision.succeeded("Verified"), evidence_renderer=self.renderer,
        )
        runtime = SimpleNamespace(fedora_version=lambda: "44", is_atomic=lambda: False, package_manager=lambda: "dnf5")
        self.facade = Mock()
        self.facade.preview.return_value = ActionResult.ok("Preview", exit_code=0)
        self.orchestrator = ActionCenterOrchestrator(
            facade=self.facade, catalog=ActionCatalog([self.definition]), runtime=runtime,
            plan_store=ActionPlanStore(root / "plans.json"), run_store=ActionRunStore(root / "runs.jsonl"),
            lease_path=root / "lease", recover_interrupted=False,
        )

    def tearDown(self):
        for run_id in list(self.orchestrator._held_leases):
            self.orchestrator.interrupt_run(run_id, "test-cleanup")
        self.temp.cleanup()

    def test_initial_preview_uses_exact_preflight_without_requery(self):
        plan = self.orchestrator.plan("dnf-clean-all")
        self.assertTrue(plan.policy_decision.allowed)
        self.preflight.assert_called_once()
        self.assertIs(self.renderer.call_args.args[2], plan.policy_decision)
        self.assertEqual(plan.preview, ["dnf5", "clean", "all"])
        self.legacy_renderer.assert_not_called()

    def test_saved_preview_does_not_replace_reviewed_evidence(self):
        plan = self.orchestrator.plan("dnf-clean-all")
        self.preflight.return_value = PolicyDecision(True, "ready", "Different", facts={"revision": 2})
        self.orchestrator.preview(plan.plan_id)
        self.assertEqual(self.preflight.call_count, 1)
        self.assertEqual(self.renderer.call_args.args[2].facts, {"revision": 1})
        self.facade.execute.assert_not_called()

    def test_execution_requires_fresh_matching_evidence(self):
        plan = self.orchestrator.plan("dnf-clean-all")
        prepared = self.orchestrator.prepare_run(plan.plan_id, confirmed=True)
        self.assertEqual(self.preflight.call_count, 2)
        self.assertEqual(prepared.command, ("dnf5", "clean", "all"))
        self.legacy_renderer.assert_not_called()

    def test_changed_evidence_cannot_execute_previously_approved_vector(self):
        plan = self.orchestrator.plan("dnf-clean-all")
        self.preflight.return_value = PolicyDecision(True, "ready", "Reviewed", facts={"revision": 2})
        with self.assertRaises(ActionPlanRejectedError) as caught:
            self.orchestrator.prepare_run(plan.plan_id, confirmed=True)
        self.assertEqual(caught.exception.decision.reason_code, "system_drift")
        self.facade.execute.assert_not_called()

    def test_denied_recheck_never_renders_or_executes(self):
        plan = self.orchestrator.plan("dnf-clean-all")
        self.renderer.reset_mock()
        self.preflight.return_value = PolicyDecision(False, "unavailable", "Installation disappeared")
        with self.assertRaises(ActionPlanRejectedError) as caught:
            self.orchestrator.prepare_run(plan.plan_id, confirmed=True)
        self.assertEqual(caught.exception.decision.reason_code, "unavailable")
        self.renderer.assert_not_called()
        self.facade.execute.assert_not_called()

    def update_plan(self):
        verifier = Mock(return_value=VerificationDecision.succeeded("Observed reviewed commits", results=[
            {"installation": "user", "ref": "app/org.example.Editor/x86_64/stable", "status": "verified"},
        ]))
        self.orchestrator.catalog = ActionCatalog([replace(self.definition, id="update-flatpaks", verifier=verifier)])
        plan = self.orchestrator.plan("update-flatpaks")
        return self.orchestrator.prepare_run(plan.plan_id, confirmed=True), verifier

    def test_failed_update_retains_readback_without_becoming_success(self):
        prepared, verifier = self.update_plan()
        run = self.orchestrator.complete_run(prepared.run_id, ActionResult.fail("Partial failure", exit_code=1))
        self.assertEqual(run.state, "failed")
        verifier.assert_called_once()
        self.assertEqual(run.verification_result["data"]["results"][0]["status"], "verified")
        self.assertEqual(run.verification_attempts, 1)

    def test_cancelled_update_retains_readback_without_becoming_success(self):
        prepared, verifier = self.update_plan()
        run = self.orchestrator.complete_run(prepared.run_id, ActionResult.fail("Cancelled", exit_code=126))
        self.assertEqual(run.state, "cancelled")
        verifier.assert_called_once()
        self.assertTrue(run.verification_result)

    def test_interrupted_update_retains_readback_without_becoming_success(self):
        prepared, verifier = self.update_plan()
        run = self.orchestrator.interrupt_run(prepared.run_id)
        self.assertEqual(run.state, "interrupted")
        verifier.assert_called_once()
        self.assertTrue(run.verification_result)
