"""A result recheck observes an exact saved run without replaying execution."""
import unittest
from dataclasses import replace
from types import SimpleNamespace
from unittest.mock import Mock

from core.actions import ActionCatalog, ActionCenterBusyError, ActionPlanIntegrityError, ActionRun
from core.actions.contracts import VerificationDecision
from core.actions.operation_controller import OperationController
from core.actions.orchestrator import ActionCenterError
from core.executor.action_result import ActionResult
from core.change_journal.models import ChangeEvent, ChangeJournalSnapshot
from test_action_center_v14 import OrchestratorFixture
from ui.activity_recovery_tab import ActivityRecoveryTab
from core.state.atomic_io import StateBusyError, advisory_lock


class RecheckOperationTests(OrchestratorFixture):
    def make_run(self, state="interrupted"):
        self.orchestrator.catalog = ActionCatalog()
        plan = self.orchestrator.plan("dnf-clean-all")
        run = ActionRun("exact-run", plan.plan_id, plan.action_id, "exact-correlation", state=state,
                        execution_result=ActionResult.fail("Original execution failure").to_dict(),
                        completed_at=900.0, updated_at=900.0, recovery_status="manual-review-required")
        self.run_store.save(run)
        self.verifier = Mock(return_value=VerificationDecision.succeeded("Current package state verified."))
        self.preflight = Mock(side_effect=AssertionError("Recheck must not run preflight"))
        self.renderer = Mock(side_effect=AssertionError("Recheck must not render a command"))
        definition = replace(self.orchestrator.catalog.get(plan.action_id), verifier=self.verifier,
                             preflight_checker=self.preflight, command_renderer=self.renderer)
        self.orchestrator.catalog = ActionCatalog([definition])
        self.facade.reset_mock()
        return plan, run

    def test_all_terminal_rechecks_preserve_execution_state_history_and_completion(self):
        for state in ("failed", "verification_failed", "cancelled", "interrupted"):
            with self.subTest(state=state):
                _plan, original = self.make_run(state)
                observed = self.orchestrator.recheck_result(original.run_id)
                self.assertEqual(observed.state, state)
                self.assertEqual(observed.execution_result, original.execution_result)
                self.assertEqual(observed.state_history, original.state_history)
                self.assertEqual(observed.completed_at, original.completed_at)
                self.assertEqual(observed.updated_at, original.updated_at)
                self.assertTrue(observed.verification_result["success"])
                self.assertEqual(observed.verification_attempts, 1)
                self.assertEqual(observed.last_verified_at, self.now)
                self.assertEqual(self.run_store.get(original.run_id).to_dict(), observed.to_dict())
                self.verifier.assert_called_once()
                self.facade.execute.assert_not_called()
                self.preflight.assert_not_called()
                self.renderer.assert_not_called()
                again = self.orchestrator.recheck_result(original.run_id)
                self.assertEqual(again.verification_attempts, 2)

    def test_lease_prevents_observation_during_another_mutation(self):
        _plan, run = self.make_run()
        lease = advisory_lock(self.lease_path, timeout=0)
        lease.__enter__()
        try:
            with self.assertRaises(ActionCenterBusyError):
                self.orchestrator.recheck_result(run.run_id)
        finally:
            lease.__exit__(None, None, None)
        self.verifier.assert_not_called()

    def test_result_observation_runs_while_mutation_lease_is_held(self):
        _plan, run = self.make_run()

        def observe(*_args):
            with self.assertRaises(StateBusyError):
                with advisory_lock(self.lease_path, timeout=0):
                    self.fail("Verifier ran without the mutation lease")
            return VerificationDecision.failed("Current result is unknown.")

        self.verifier.side_effect = observe
        result = self.orchestrator.recheck_result(run.run_id)
        self.assertFalse(result.verification_result["success"])
        self.assertEqual(result.state, "interrupted")

    def test_corrupt_plan_and_mismatched_run_are_rejected_before_observation(self):
        plan, run = self.make_run()
        plan.digest = "invalid"
        self.plan_store.save(plan)
        with self.assertRaises(ActionPlanIntegrityError):
            self.orchestrator.recheck_result(run.run_id)
        self.verifier.assert_not_called()
        plan, run = self.make_run()
        run.parameters = {"unexpected": True}
        self.run_store.save(run)
        with self.assertRaises(ActionPlanIntegrityError):
            self.orchestrator.recheck_result(run.run_id)
        self.verifier.assert_not_called()

    def test_live_run_is_not_rechecked_or_restarted(self):
        _plan, run = self.make_run("running")
        with self.assertRaises(ActionCenterError):
            self.orchestrator.recheck_result(run.run_id)
        self.verifier.assert_not_called()
        self.facade.execute.assert_not_called()

    def test_unavailable_observation_is_recorded_without_changing_original_failure(self):
        _plan, run = self.make_run("failed")
        self.verifier.side_effect = OSError("private backend detail")
        result = self.orchestrator.recheck_result(run.run_id)
        self.assertEqual(result.state, "failed")
        self.assertFalse(result.verification_result["success"])
        self.assertNotIn("private", result.verification_result["message"])
        self.assertEqual(result.execution_result, run.execution_result)
        self.verifier.side_effect = None
        self.verifier.return_value = ActionResult.ok("Readable now")
        self.assertTrue(self.orchestrator.recheck_result(run.run_id).verification_result["success"])

    def test_controller_reports_current_verification_separately_from_original_interruption(self):
        _plan, run = self.make_run()
        outcome = OperationController(orchestrator=self.orchestrator).verify(run.run_id)
        self.assertEqual(outcome.status, "interrupted")
        self.assertFalse(outcome.success)
        self.assertTrue(outcome.data["current_state_verified"])
        self.assertTrue(outcome.data["read_only_recheck"])
        self.assertEqual(outcome.data["original_run_state"], "interrupted")
        self.assertEqual(outcome.data["execution_result"], run.execution_result)
        self.facade.execute.assert_not_called()

    def test_controller_integrity_failure_never_records_a_verification_or_retries(self):
        plan, run = self.make_run()
        plan.digest = "invalid"
        self.plan_store.save(plan)
        outcome = OperationController(orchestrator=self.orchestrator).verify(run.run_id)
        self.assertEqual(outcome.status, "interrupted")
        self.assertEqual(self.run_store.get(run.run_id).verification_attempts, 0)
        self.verifier.assert_not_called()
        self.facade.execute.assert_not_called()


class RecheckActivityTests(unittest.TestCase):
    def test_each_recorded_terminal_run_exposes_exact_result_check(self):
        for state in ("failed", "verification_failed", "cancelled", "interrupted"):
            with self.subTest(state=state):
                event = ChangeEvent(event_id="action_center:exact", source="action_center", occurred_at=100,
                                    actor_class="user", summary="Recorded operation", state=state,
                                    after_facts={"run_id": "exact-recorded-run", "verification": {"success": True}})
                tab = ActivityRecoveryTab(journal_service=SimpleNamespace())
                requests = []
                tab.runVerificationRequested.connect(requests.append)
                tab._loaded(ChangeJournalSnapshot(events=(event,), sources=(), generated_at=101))
                tab.table.selectRow(0)
                tab._render_selected()
                self.assertTrue(tab.check_result_button.isVisibleTo(tab))
                tab.check_result_button.click()
                self.assertEqual(requests, ["exact-recorded-run"])
                tab.close()
