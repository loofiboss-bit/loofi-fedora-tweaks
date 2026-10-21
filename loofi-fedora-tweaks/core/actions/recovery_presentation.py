"""Shared, read-only presentation of durable operations; never resume mutations."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping


@dataclass(frozen=True)
class RecoveryPresentation:
    state: str
    label: str
    next_action: str
    guidance: str
    outcome: str = "unknown"


def recovery_presentation(state: str, execution: Mapping | None = None,
                          verification: Mapping | None = None, *, reopened: bool = False) -> RecoveryPresentation:
    """Keep lifecycle states intact and describe only outcomes supported by evidence.

    A saved running process is interrupted when reopened. Verification failure
    alone is never proof that the mutation was rolled back or fully failed.
    """
    execution = execution if isinstance(execution, Mapping) else {}
    verification = verification if isinstance(verification, Mapping) else {}
    data = verification.get("data", {})
    data = data if isinstance(data, Mapping) else {}
    if reopened and state == "running":
        state = "interrupted"
    labels = {"running": "In progress", "verifying": "Verification pending", "awaiting_reboot": "Reboot required",
              "succeeded": "Verified success", "failed": "Operation failed", "verification_failed": "Result not verified",
              "interrupted": "Interrupted", "cancelled": "Cancelled"}
    action = "verify" if state in {"verifying", "awaiting_reboot"} else "review"
    guidance = {
        "running": "The operation is in progress. Do not start another operation on the same resources.",
        "verifying": "Check the recorded result. Verification does not repeat the operation.",
        "awaiting_reboot": "Review the required restart, then check the result after reboot.",
        "succeeded": "The recorded verification succeeded.",
        "failed": "Review the recorded failure and current state before creating a new plan.",
        "verification_failed": "The resulting system state could not be verified. Review Activity before creating a new plan.",
        "interrupted": "The operation stopped before its result was confirmed. Review current state; no operation was restarted.",
        "cancelled": "Review current state before creating a new plan; cancellation does not imply rollback.",
    }.get(state, "Saved operation state is unavailable. Review Activity; no operation was restarted.")
    outcome = "verified" if state == "succeeded" and verification.get("success") is True else "unknown"
    if state == "succeeded" and outcome != "verified":
        state = "verification_failed"
        guidance = "The saved success has no verification evidence. Review Activity before creating a new plan."
    partial = (data.get("partial") is True or data.get("evidence_status") == "partial"
               or bool(data.get("missing_packages")) or bool(data.get("failed_operations")))
    if state in {"verification_failed", "failed", "interrupted", "cancelled"} and partial and data.get("evidence_unavailable") is not True:
        outcome = "partial"
        guidance = "Only part of the intended result was verified. Review the recorded differences before creating a new plan."
    # Prefer machine-readable causes. Output matching only suggests a next step;
    # it never changes the recorded outcome or authorizes an automatic retry.
    cause_data = execution.get("data", {})
    cause_data = cause_data if isinstance(cause_data, Mapping) else {}
    code = str(cause_data.get("error_code", execution.get("error_code", ""))).casefold()
    text = " ".join(str(execution.get(key, ""))[:4000] for key in ("message", "stderr")).casefold()
    if state in {"failed", "cancelled", "interrupted"}:
        if code in {"permission_denied", "authorization_denied", "polkit_denied"} or "not authorized" in text or "permission denied" in text:
            guidance = "Authorization was denied. Review the operation and request authorization again only when ready."
        elif code in {"package_manager_busy", "package_lock", "locked"} or "another app is currently holding" in text or "lock is held" in text:
            guidance = "Another package operation holds the lock. Wait for it to finish, then create a fresh review."
        elif code in {"no_space", "disk_full"} or "no space left on device" in text:
            guidance = "Free space on the affected filesystem, check its health, then create a fresh review."
        elif code == "operation_timeout":
            guidance = "The operation reached its time limit. Check its current result in Activity before creating a new plan."
        elif code in {"network_error", "offline", "timeout"} or any(word in text for word in ("could not resolve host", "network is unreachable", "connection timed out")):
            guidance = "Check the network connection and configured source, then create a fresh review."
    return RecoveryPresentation(state, labels.get(state, "Result unavailable"), action, guidance, outcome)
