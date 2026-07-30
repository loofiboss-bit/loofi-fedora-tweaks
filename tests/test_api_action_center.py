"""Authenticated closed-planning and read-only Action Center API tests."""

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

        self.assertEqual(payload["schema_version"], 3)
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

        self.assertEqual(payload["schema_version"], 3)
        self.assertTrue(payload["read_only"])
        self.assertNotIn("stdout", payload["run"]["execution_result"])
        self.assertNotIn("stderr", payload["run"]["verification_result"])

    @patch("api.routes.action_center.ActionCenterOrchestrator")
    def test_post_plan_creates_review_plan_without_apply(self, orchestrator_cls):
        from api.routes.action_center import ActionPlanRequest, create_action_plan

        policy = MagicMock()
        policy.to_dict.return_value = {"allowed": True, "reason_code": "ready"}
        plan = MagicMock(
            plan_id="plan-1",
            action_id="dnf-clean-all",
            state="ready",
            recovery_guidance="Retry after package work completes.",
        )
        plan.to_dict.return_value = {
            "plan_id": "plan-1",
            "action_id": "dnf-clean-all",
            "state": "ready",
        }
        orchestrator_cls.return_value.plan.return_value = plan

        payload = create_action_plan(
            ActionPlanRequest(definition_id="dnf-clean-all", parameters={}),
            _auth="token",
        )

        self.assertEqual(payload["schema_version"], 4)
        self.assertEqual(payload["plan_summary"]["plan_id"], "plan-1")
        self.assertTrue(payload["plan_summary"]["review_required"])
        self.assertFalse(payload["plan_summary"]["auto_apply"])
        orchestrator_cls.return_value.plan.assert_called_once_with(
            "dnf-clean-all",
            {},
        )
        orchestrator_cls.return_value.apply.assert_not_called()

    def test_post_plan_requires_authentication(self):
        from utils.api_server import APIServer

        response = TestClient(APIServer().app).post(
            "/api/action-center/plans",
            json={"definition_id": "dnf-clean-all", "parameters": {}},
        )

        self.assertIn(response.status_code, {401, 403})

    @patch("api.routes.action_center.ActionCenterOrchestrator")
    def test_post_plan_http_route_returns_created_plan(self, orchestrator_cls):
        from utils.api_server import APIServer
        from utils.auth import AuthManager

        plan = MagicMock(
            plan_id="plan-http",
            action_id="dnf-clean-all",
            state="ready",
            recovery_guidance="Retry later.",
        )
        plan.to_dict.return_value = {
            "plan_id": "plan-http",
            "action_id": "dnf-clean-all",
            "state": "ready",
        }
        orchestrator_cls.return_value.plan.return_value = plan
        server = APIServer()
        server.app.dependency_overrides[
            AuthManager.verify_bearer_token
        ] = lambda: "test-token"

        response = TestClient(server.app).post(
            "/api/action-center/plans",
            json={"definition_id": "dnf-clean-all", "parameters": {}},
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["plan_summary"]["plan_id"], "plan-http")
        orchestrator_cls.return_value.apply.assert_not_called()

    @patch("api.routes.action_center.ActionCatalog")
    def test_post_plan_rejects_unknown_definition(self, catalog_cls):
        from api.routes.action_center import ActionPlanRequest, create_action_plan
        from fastapi import HTTPException

        catalog_cls.return_value.get.return_value = None

        with self.assertRaises(HTTPException) as rejected:
            create_action_plan(
                ActionPlanRequest(definition_id="unknown-action", parameters={}),
                _auth="token",
            )

        self.assertEqual(rejected.exception.status_code, 404)

    @patch("api.routes.action_center.ActionCenterOrchestrator")
    def test_post_plan_rejects_invalid_parameters_before_persistence(
        self,
        orchestrator_cls,
    ):
        from api.routes.action_center import ActionPlanRequest, create_action_plan
        from fastapi import HTTPException

        with self.assertRaises(HTTPException) as rejected:
            create_action_plan(
                ActionPlanRequest(
                    definition_id="vacuum-journal",
                    parameters={"days": 99},
                ),
                _auth="token",
            )

        self.assertEqual(rejected.exception.status_code, 422)
        orchestrator_cls.return_value.plan.assert_not_called()

    def test_post_plan_rejects_open_ended_command_fields(self):
        from api.routes.action_center import ActionPlanRequest
        from pydantic import ValidationError

        with self.assertRaises(ValidationError):
            ActionPlanRequest.model_validate(
                {
                    "definition_id": "dnf-clean-all",
                    "parameters": {},
                    "command": ["pkexec", "dnf", "clean", "all"],
                }
            )
