"""Helm support bundle with redacted Action Center evidence."""

from __future__ import annotations

from typing import Any, Dict, cast

from core.export.support_bundle_v9 import SupportBundleV9


class SupportBundleV10(SupportBundleV9):
    """Preserve prior diagnostics and add correlated plan/run status only."""

    BUNDLE_SCHEMA = "14.0.0-helm-support-v10"

    @classmethod
    def _result_status(cls, result: object) -> dict[str, Any] | None:
        if not isinstance(result, dict):
            return None
        return {
            "success": bool(result.get("success", False)),
            "message": cls._mask_text(str(result.get("message", ""))),
            "exit_code": result.get("exit_code"),
            "timestamp": result.get("timestamp"),
            "action_id": str(result.get("action_id", "")),
        }

    @classmethod
    def generate_bundle(cls, target: str = "44") -> Dict[str, Any]:
        from core.actions.stores import ActionPlanStore, ActionRunStore

        bundle = super().generate_bundle(target=target)
        plans = {plan.plan_id: plan for plan in ActionPlanStore().list(limit=50)}
        runs = ActionRunStore().list(limit=100)
        correlated: list[dict[str, Any]] = []
        for run in runs:
            plan = plans.get(run.plan_id)
            correlated.append(
                {
                    "run_id": run.run_id,
                    "plan_id": run.plan_id,
                    "correlation_id": run.correlation_id,
                    "action_id": run.action_id,
                    "run_state": run.state,
                    "plan": (
                        {
                            "state": plan.state,
                            "target": plan.target,
                            "risk_level": plan.risk_level,
                            "privileged": plan.privileged,
                            "created_at": plan.created_at,
                            "expires_at": plan.expires_at,
                            "digest": plan.digest,
                        }
                        if plan is not None
                        else None
                    ),
                    "preflight": plan.policy_decision.to_dict() if plan is not None else None,
                    "execution": cls._result_status(run.execution_result),
                    "verification": cls._result_status(run.verification_result),
                    "recovery_status": run.recovery_status,
                    "started_at": run.started_at,
                    "completed_at": run.completed_at,
                }
            )

        bundle["v"] = cls.BUNDLE_SCHEMA
        bundle["schema"] = cls.BUNDLE_SCHEMA
        bundle["support_bundle_version"] = 10
        bundle["verified_maintenance"] = {
            "schema_version": 1,
            "raw_stdout_included": False,
            "raw_stderr_included": False,
            "secrets_included": False,
            "runs": correlated,
        }
        return cast(Dict[str, Any], cls._redact(bundle))
