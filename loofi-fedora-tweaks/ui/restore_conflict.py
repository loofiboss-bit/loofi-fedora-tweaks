"""Human-readable details for blocked setting restoration."""

from collections.abc import Callable

from core.actions.contracts import PolicyDecision


def restore_conflict_message(decision: PolicyDecision, translate: Callable[[str], str]) -> str:
    """Include the saved and observed values when drift blocks restoration."""
    message = str(getattr(decision, "explanation", ""))
    reason_code = str(getattr(decision, "reason_code", ""))
    if reason_code not in {"external-change", "restore-value-unavailable", "current-value-unknown"}:
        return message
    facts = getattr(decision, "facts", {})
    facts = facts if isinstance(facts, dict) else {}
    unknown = translate("Unknown")
    current = str(facts.get("current", "")) or unknown
    return "\n".join((
        message,
        translate("Previous value: %1").replace("%1", str(facts.get("previous", "")) or unknown),
        translate("Last verified value: %1").replace("%1", str(facts.get("last_verified", "")) or unknown),
        translate("Current value: %1").replace("%1", current),
    ))
