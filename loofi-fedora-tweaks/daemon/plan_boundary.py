"""Plan-only mutation boundary for unattended daemon callers."""

from __future__ import annotations

from typing import Any, Mapping

from core.actions import ActionCenterOrchestrator
from core.fedora_release_policy import FEDORA_RELEASE_POLICY


def create_plan(
    action_id: str,
    parameters: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Create a durable plan; daemon callers can never confirm or apply it."""
    plan = ActionCenterOrchestrator().plan(
        action_id,
        dict(parameters or {}),
        target=FEDORA_RELEASE_POLICY.stable_target,
    )
    return {
        "schema_version": 3,
        "plan_only": True,
        "auto_apply": False,
        "requires_interactive_confirmation": True,
        "plan": plan.to_dict(),
    }


def create_manual_plan(operation: str, parameters: Mapping[str, Any] | None = None) -> dict[str, Any]:
    """Persist unsupported daemon mutations as honest manual-only plans."""
    normalized = "-".join(operation.strip().lower().replace("_", "-").split())
    return create_plan(f"daemon-{normalized}", parameters)
