"""Read-only authenticated Action Center API contract tests."""

from unittest import TestCase
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient


class TestActionCenterApi(TestCase):
    def test_action_center_plan_read_requires_authentication(self):
        from utils.api_server import APIServer

        response = TestClient(APIServer().app).get("/api/action-center/plans/plan-1")
        self.assertIn(response.status_code, {401, 403})

    @patch("api.routes.action_center.ActionPlanStore")
    def test_get_plan_uses_stable_envelope(self, store_cls):
        from api.routes.action_center import get_action_plan

        policy = MagicMock()
        policy.to_dict.return_value = {"allowed": True, "reason_code": "ready"}
        plan = MagicMock(policy_decision=policy)
        plan.to_dict.return_value = {"plan_id": "plan-1", "state": "ready"}
        store_cls.return_value.get.return_value = plan

        payload = get_action_plan("plan-1", _auth="token")

        self.assertEqual(payload["schema_version"], 1)
        self.assertTrue(payload["read_only"])
        self.assertEqual(payload["plan"]["plan_id"], "plan-1")
        self.assertEqual(payload["policy_decision"]["reason_code"], "ready")

    @patch("api.routes.action_center.ActionRunStore")
    def test_get_run_excludes_raw_process_output(self, store_cls):
        from api.routes.action_center import get_action_run

        run = MagicMock()
        run.to_dict.return_value = {
            "run_id": "run-1",
            "execution_result": {"success": True, "stdout": "private", "stderr": "private"},
            "verification_result": {"success": False, "stdout": "private", "stderr": "private"},
        }
        store_cls.return_value.get.return_value = run

        payload = get_action_run("run-1", _auth="token")

        self.assertEqual(payload["schema_version"], 1)
        self.assertTrue(payload["read_only"])
        self.assertNotIn("stdout", payload["run"]["execution_result"])
        self.assertNotIn("stderr", payload["run"]["verification_result"])
