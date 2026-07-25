"""Authenticated, read-only v17 Action Center API routes."""

from __future__ import annotations

from typing import Any, cast

from core.actions.stores import ActionPlanStore, ActionRunStore
from fastapi import APIRouter, Depends, HTTPException, Query
from utils.auth import AuthManager

router = APIRouter(prefix="/api/action-center", tags=["action-center"])


def _run_status(run: Any) -> dict[str, Any]:
    """Expose status fields while keeping captured process output private."""
    payload = cast(dict[str, Any], run.to_dict())
    for key in ("execution_result", "verification_result"):
        result = payload.get(key)
        if isinstance(result, dict):
            result.pop("stdout", None)
            result.pop("stderr", None)
    return payload


@router.get("/plans")
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


@router.get("/plans/{plan_id}")
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


@router.get("/runs")
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


@router.get("/runs/{run_id}")
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
