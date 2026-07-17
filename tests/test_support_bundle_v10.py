"""Helm support bundle privacy and correlation tests."""

from unittest import TestCase
from unittest.mock import MagicMock, patch

from core.export.support_bundle_v10 import SupportBundleV10


class TestSupportBundleV10(TestCase):
    @patch("core.export.support_bundle_v9.SupportBundleV9.generate_bundle", return_value={"legacy": True})
    @patch("core.actions.stores.ActionPlanStore.list")
    @patch("core.actions.stores.ActionRunStore.list")
    def test_v10_correlates_status_without_process_output(self, list_runs, list_plans, _legacy):
        policy = MagicMock()
        policy.to_dict.return_value = {"allowed": True, "reason_code": "ready"}
        plan = MagicMock(
            plan_id="plan-1",
            state="ready",
            target="44",
            risk_level="medium",
            privileged=True,
            created_at=10.0,
            expires_at=20.0,
            digest="digest",
            policy_decision=policy,
        )
        run = MagicMock(
            run_id="run-1",
            plan_id="plan-1",
            correlation_id="run-1",
            action_id="restart-failed-service",
            state="verification_failed",
            execution_result={
                "success": True,
                "message": "command finished token=private-value",
                "exit_code": 0,
                "stdout": "secret stdout",
                "stderr": "secret stderr",
            },
            verification_result={"success": False, "message": "still failed", "exit_code": 3},
            recovery_status="manual-review-required",
            started_at=11.0,
            completed_at=12.0,
        )
        list_plans.return_value = [plan]
        list_runs.return_value = [run]

        bundle = SupportBundleV10.generate_bundle()

        self.assertTrue(bundle["legacy"])
        self.assertEqual(bundle["support_bundle_version"], 10)
        evidence = bundle["verified_maintenance"]["runs"][0]
        self.assertEqual(evidence["run_id"], "run-1")
        self.assertEqual(evidence["preflight"]["reason_code"], "ready")
        self.assertNotIn("stdout", evidence["execution"])
        self.assertNotIn("stderr", evidence["execution"])
        self.assertNotIn("private-value", str(bundle))
