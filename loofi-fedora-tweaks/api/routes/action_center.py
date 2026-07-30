"""Authenticated Action Center planning and read-only status routes."""

from __future__ import annotations

from typing import Any, cast

from core.actions import ActionCatalog, ActionCenterOrchestrator
from core.actions.catalog import validate_parameters
from core.actions.stores import ActionPlanStore, ActionRunStore
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field
from utils.auth import AuthManager


class ActionPlanRequest(BaseModel):
    """Closed catalog request; arbitrary commands are never accepted."""

    model_config = ConfigDict(extra="forbid")

    definition_id: str = Field(min_length=1, max_length=128)
    parameters: dict[str, Any] = Field(default_factory=dict)


def create_action_plan(
    request: ActionPlanRequest,
    _auth: str = Depends(AuthManager.verify_bearer_token),
):
    """Create a review plan for one exact catalog definition without applying it."""
    catalog = ActionCatalog()
    definition = catalog.get(request.definition_id)
    if definition is None:
        raise HTTPException(status_code=404, detail="Unknown Action Center definition")
    parameter_decision = validate_parameters(definition, request.parameters)
    if not parameter_decision.allowed:
        raise HTTPException(
            status_code=422,
            detail={
                "reason_code": parameter_decision.reason_code,
                "message": parameter_decision.explanation,
            },
        )
    try:
        plan = ActionCenterOrchestrator(catalog=catalog).plan(
            request.definition_id,
            request.parameters,
        )
    except (TypeError, ValueError) as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    return {
        "schema_version": 4,
        "plan": plan.to_dict(),
        "plan_summary": {
            "plan_id": plan.plan_id,
            "state": plan.state,
            "definition_id": plan.action_id,
            "review_required": True,
            "auto_apply": False,
            "next_action": (
                f"loofi-fedora-tweaks --cli action-center apply {plan.plan_id} --confirm"
                if plan.state != "blocked"
                else plan.recovery_guidance
            ),
        },
    }


def _run_status(run: Any) -> dict[str, Any]:
    """Expose status fields while keeping captured process output private."""
    payload = cast(dict[str, Any], run.to_dict())
    for key in ("execution_result", "verification_result"):
        result = payload.get(key)
        if isinstance(result, dict):
            result.pop("stdout", None)
            result.pop("stderr", None)
    return payload


def list_action_plans(
    limit: int = Query(default=25, ge=1, le=50),
    _auth: str = Depends(AuthManager.verify_bearer_token),
):
    """Return bounded plan metadata; this endpoint never executes actions."""
    plans = ActionPlanStore().list(limit=limit)
    return {
        "schema_version": 3,
        "read_only": True,
        "plans": [plan.to_dict() for plan in plans],
    }


def get_action_plan(
    plan_id: str,
    _auth: str = Depends(AuthManager.verify_bearer_token),
):
    """Return one persisted Action Center plan."""
    plan = ActionPlanStore().get(plan_id)
    if plan is None:
        raise HTTPException(status_code=404, detail="Action Center plan not found")
    return {
        "schema_version": 3,
        "read_only": True,
        "plan": plan.to_dict(),
        "policy_decision": plan.policy_decision.to_dict(),
    }


def list_action_runs(
    limit: int = Query(default=25, ge=1, le=100),
    _auth: str = Depends(AuthManager.verify_bearer_token),
):
    """Return bounded execution and verification status metadata."""
    runs = ActionRunStore().list(limit=limit)
    return {
        "schema_version": 3,
        "read_only": True,
        "runs": [_run_status(run) for run in runs],
    }


def get_action_run(
    run_id: str,
    _auth: str = Depends(AuthManager.verify_bearer_token),
):
    """Return one persisted Action Center run without raw process output."""
    run = ActionRunStore().get(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Action Center run not found")
    return {
        "schema_version": 3,
        "read_only": True,
        "run": _run_status(run),
    }


def get_action_center_router() -> APIRouter:
    r = APIRouter(prefix="/api/action-center", tags=["action-center"])
    r.add_api_route("/plans", list_action_plans, methods=["GET"])
    r.add_api_route("/plans", create_action_plan, methods=["POST"], status_code=201)
    r.add_api_route("/plans/{plan_id}", get_action_plan, methods=["GET"])
    r.add_api_route("/runs", list_action_runs, methods=["GET"])
    r.add_api_route("/runs/{run_id}", get_action_run, methods=["GET"])
    return r


router = get_action_center_router()
