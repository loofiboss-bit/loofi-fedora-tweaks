"""Support bundle with bounded System Check resolution evidence."""

from __future__ import annotations

from typing import Any, Dict, cast

from core.export.support_bundle_v10 import SupportBundleV10


class SupportBundleV11(SupportBundleV10):
    """Preserve v10 diagnostics and add privacy-safe before/after evidence."""

    BUNDLE_SCHEMA = "19.0.0-steward-support-v11"

    @classmethod
    def generate_bundle(cls, target: str = "44") -> Dict[str, Any]:
        from core.actions.stores import ActionPlanStore, ActionRunStore
        from core.observability.timeline import HealthTimelineStore
        from core.system_check.comparison import (
            latest_comparison,
            results_from_snapshots,
        )

        bundle = super().generate_bundle(target=target)
        snapshots = HealthTimelineStore().load()
        results = results_from_snapshots(snapshots)
        comparison = latest_comparison(snapshots)
        plans = {
            plan.plan_id: plan
            for plan in ActionPlanStore().list_read_only(limit=50)
        }
        linked_runs: list[dict[str, Any]] = []
        for run in ActionRunStore().list_read_only(limit=100):
            context = run.finding_context
            if context is None:
                continue
            plan = plans.get(run.plan_id)
            verification = run.verification_result or {}
            linked_runs.append(
                {
                    "run_id": run.run_id,
                    "plan_id": run.plan_id,
                    "action_id": run.action_id,
                    "run_state": run.state,
                    "plan_state": plan.state if plan is not None else None,
                    "check_result_id": context.check_result_id,
                    "finding_fingerprint": context.finding_fingerprint,
                    "evidence_digest": context.evidence_digest,
                    "origin_route": context.origin_route,
                    "affected_resources": list(context.affected_resources),
                    "verification": {
                        "success": bool(verification.get("success", False)),
                        "message": str(verification.get("message", "")),
                        "timestamp": verification.get("timestamp"),
                    },
                    "reboot_required": run.reboot_required,
                    "recovery_status": run.recovery_status,
                    "last_verified_at": run.last_verified_at,
                    "updated_at": run.updated_at,
                }
            )

        bundle["v"] = cls.BUNDLE_SCHEMA
        bundle["schema"] = cls.BUNDLE_SCHEMA
        bundle["support_bundle_version"] = 11
        bundle["system_check"] = {
            "schema_version": 1,
            "results": [
                cls._bounded_result(result.to_dict())
                for result in results[-2:]
            ],
            "comparison": comparison.to_dict() if comparison is not None else None,
            "linked_maintenance": linked_runs[-25:],
            "raw_command_output_included": False,
            "collection_started_by_export": False,
        }
        return cast(Dict[str, Any], cls._redact(bundle))

    @staticmethod
    def _bounded_result(payload: dict[str, Any]) -> dict[str, Any]:
        """Bound support evidence without changing the persisted result."""
        bounded = dict(payload)
        bounded["findings"] = list(payload.get("findings", []))[:50]
        bounded["source_errors"] = list(payload.get("source_errors", []))[:10]
        durations = payload.get("source_durations_ms", {})
        bounded["source_durations_ms"] = (
            dict(list(durations.items())[:10])
            if isinstance(durations, dict)
            else {}
        )
        bounded["completed_sources"] = list(
            payload.get("completed_sources", [])
        )[:10]
        bounded["cancelled_sources"] = list(
            payload.get("cancelled_sources", [])
        )[:10]
        return bounded
