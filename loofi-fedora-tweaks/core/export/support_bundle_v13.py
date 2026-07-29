"""Compass support bundle with one selected troubleshooting support case."""

from __future__ import annotations

from typing import Any, Dict, cast

from core.export.support_bundle_v12 import SupportBundleV12
from core.troubleshooting.inspection import (
    MAX_EXPORTED_FINDINGS,
    MAX_EXPORTED_LINKED_RECORDS,
    MAX_EXPORTED_RELATED_CHANGES,
    TroubleshootingInspectionService,
    bounded_session_payload,
    sanitize_interface_payload,
)
from core.troubleshooting.storage import TroubleshootingSessionStore


class SupportBundleV13(SupportBundleV12):
    """Preserve v2-v12 data and add one bounded, explicit support case."""

    BUNDLE_SCHEMA = "23.0.0-compass-support-v13"

    @classmethod
    def generate_bundle(
        cls,
        target: str = "44",
        *,
        session_id: str | None = None,
        session_store: TroubleshootingSessionStore | None = None,
    ) -> Dict[str, Any]:
        bundle = super().generate_bundle(target=target)
        support_case: dict[str, Any] = {
            "schema_id": "loofi.troubleshooting-support-case",
            "schema_version": 1,
            "selection": "explicit" if session_id is not None else "none",
            "session": None,
            "comparison": None,
            "linked_records": [],
            "limits": {
                "sessions": 1,
                "findings": MAX_EXPORTED_FINDINGS,
                "related_changes": MAX_EXPORTED_RELATED_CHANGES,
                "linked_records": MAX_EXPORTED_LINKED_RECORDS,
                "comparisons": 1,
            },
            "raw_stdout_included": False,
            "raw_stderr_included": False,
            "commands_included": False,
            "collection_started_by_export": False,
        }

        if session_id is not None:
            inspection = TroubleshootingInspectionService(session_store)
            session = inspection.require(session_id)
            comparison = inspection.adjacent_comparison(session)
            support_case["session"] = bounded_session_payload(session)
            support_case["comparison"] = (
                sanitize_interface_payload(comparison.to_dict())
                if comparison is not None
                else None
            )
            support_case["linked_records"] = cls._linked_records(session)

        bundle["v"] = cls.BUNDLE_SCHEMA
        bundle["schema"] = cls.BUNDLE_SCHEMA
        bundle["support_bundle_version"] = 13
        bundle["troubleshooting_support_case"] = sanitize_interface_payload(
            support_case
        )
        return cast(Dict[str, Any], cls._redact(bundle))

    @staticmethod
    def _linked_records(session: Any) -> list[dict[str, Any]]:
        """Return bounded plan/run status for exact inert next-step actions."""
        from core.actions.stores import ActionPlanStore, ActionRunStore

        action_ids = {
            finding.next_step.target_id
            for finding in session.findings
            if finding.next_step.kind == "action"
            and finding.next_step.target_id
        }
        if not action_ids:
            return []

        records: list[tuple[float, dict[str, Any]]] = []
        for plan in ActionPlanStore().list_read_only(limit=50):
            if plan.action_id not in action_ids:
                continue
            records.append(
                (
                    plan.created_at,
                    {
                        "record_type": "plan",
                        "plan_id": plan.plan_id,
                        "action_id": plan.action_id,
                        "state": plan.state,
                        "created_at": plan.created_at,
                        "expires_at": plan.expires_at,
                        "risk_level": plan.risk_level,
                        "privileged": plan.privileged,
                    },
                )
            )
        for run in ActionRunStore().list_read_only(limit=100):
            if run.action_id not in action_ids:
                continue
            records.append(
                (
                    run.updated_at,
                    {
                        "record_type": "run",
                        "run_id": run.run_id,
                        "plan_id": run.plan_id,
                        "action_id": run.action_id,
                        "state": run.state,
                        "created_at": run.created_at,
                        "completed_at": run.completed_at,
                        "reboot_required": run.reboot_required,
                        "recovery_status": run.recovery_status,
                        "last_verified_at": run.last_verified_at,
                    },
                )
            )
        records.sort(key=lambda item: (item[0], str(item[1])), reverse=True)
        return [
            sanitize_interface_payload(payload)
            for _timestamp, payload in records[:MAX_EXPORTED_LINKED_RECORDS]
        ]
