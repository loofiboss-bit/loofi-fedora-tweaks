"""Interrupted cleanup preserves observed refs without rewriting failure state."""
from unittest.mock import patch

from core.change_journal.sources import _safe_result
from core.executor.action_result import ActionResult
from services.software.flatpak_maintenance import RefRecord, UnusedSnapshot
from test_action_center_v14 import OrchestratorFixture

REF = "runtime/org.example.Unused/x86_64/stable"
OTHER = "app/org.example.Keep/x86_64/stable"


class TestCleanupObservations(OrchestratorFixture):
    @patch("core.actions.flatpak_cleanup._snapshot")
    def test_failed_execution_records_actual_removed_refs(self, snapshot):
        before = UnusedSnapshot("user", True, refs=(RefRecord(REF, "a" * 64),),
                                installed=(RefRecord(REF, "a" * 64), RefRecord(OTHER, "b" * 64)), digest="c" * 64)
        snapshot.return_value = before
        plan = self.orchestrator.plan("remove-unused-flatpaks", {
            "installation": "user", "refs": [REF], "snapshot_digest": before.digest,
        })
        prepared = self.orchestrator.prepare_run(plan.plan_id, confirmed=True, accept_no_rollback=True)
        snapshot.return_value = UnusedSnapshot("user", True, installed=(RefRecord(OTHER, "b" * 64),))
        run = self.orchestrator.complete_run(prepared.run_id, ActionResult.fail("Interrupted", exit_code=1))
        self.assertEqual(run.state, "failed")
        self.assertEqual(run.verification_result["data"]["removed_refs"], [REF])
        self.assertEqual(run.verification_attempts, 1)
        self.assertEqual(run.recovery_status, "manual-review-required")
        self.assertEqual(self.orchestrator.get_run(run.run_id).verification_result, run.verification_result)

    @patch("core.actions.flatpak_cleanup._snapshot")
    def test_interrupted_execution_retains_remaining_and_unexpected_refs(self, snapshot):
        before = UnusedSnapshot("user", True, refs=(RefRecord(REF, "a" * 64),),
                                installed=(RefRecord(REF, "a" * 64), RefRecord(OTHER, "b" * 64)), digest="c" * 64)
        snapshot.return_value = before
        plan = self.orchestrator.plan("remove-unused-flatpaks", {
            "installation": "user", "refs": [REF], "snapshot_digest": before.digest,
        })
        prepared = self.orchestrator.prepare_run(plan.plan_id, confirmed=True, accept_no_rollback=True)
        snapshot.return_value = UnusedSnapshot("user", True, installed=(RefRecord(REF, "a" * 64),))
        run = self.orchestrator.interrupt_run(prepared.run_id)
        self.assertEqual(run.state, "interrupted")
        self.assertEqual(run.verification_result["data"]["remaining_refs"], [REF])
        self.assertEqual(run.verification_result["data"]["unexpected_missing_refs"], [OTHER])

    def test_journal_preserves_only_valid_runtime_observation_fields(self):
        result = {"message": "Partial", "stdout": "secret", "data": {
            "removed_refs": [REF], "remaining_refs": [], "unexpected_missing_refs": [],
            "installation": "user", "token": "secret",
        }}
        safe = _safe_result(result, action_id="remove-unused-flatpaks")
        self.assertEqual(safe["removed_refs"], [REF])
        self.assertNotIn("secret", str(safe))
        self.assertNotIn("removed_refs", _safe_result(result))
