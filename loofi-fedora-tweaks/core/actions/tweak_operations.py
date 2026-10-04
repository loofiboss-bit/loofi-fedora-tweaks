"""Shared presentation-neutral follow-up for verified KWin setting operations."""

from __future__ import annotations

from dataclasses import dataclass
from subprocess import TimeoutExpired

from core.actions.orchestrator import ActionCenterError

from core.actions.operation_controller import OperationController, OperationOutcome
from core.tweak_commands import KWIN_RUNTIME_KEYS

ACTIVATION_ACTION_ID = "activate-kwin-tweak"
ACTIVATION_WARNING = "Saved and verified; application in the current session is unverified."


@dataclass(frozen=True)
class TweakActivationResult:
    saved_verified: bool
    session_verified: bool
    message: str
    outcome: OperationOutcome | None = None


def activation_parameters(outcome: OperationOutcome) -> dict[str, str] | None:
    """Return a closed follow-up request only for a successful supported write."""
    if not outcome.success or not outcome.run_id:
        return None
    tweak_id = outcome.action_id.removeprefix("set-").removeprefix("restore-")
    if tweak_id not in KWIN_RUNTIME_KEYS or outcome.action_id not in {f"set-{tweak_id}", f"restore-{tweak_id}"}:
        return None
    return {"tweak_id": tweak_id, "source_run_id": outcome.run_id}


def activation_result(source_outcome: OperationOutcome, activation_outcome: OperationOutcome | None) -> TweakActivationResult:
    """Keep successful saved changes distinct from failed runtime activation."""
    verified = bool(activation_outcome and activation_outcome.success)
    message = "Saved and verified; applied and verified in the current Plasma session." if verified else ACTIVATION_WARNING
    if not source_outcome.success:
        message = source_outcome.message
    elif activation_outcome and not verified:
        verification = (activation_outcome.run.verification_result or {}) if activation_outcome.run else {}
        reason = (activation_outcome.result.message if activation_outcome.result else "") or str(verification.get("message", "")) or activation_outcome.message
        if reason:
            message += " " + reason
    return TweakActivationResult(source_outcome.success, verified, message, activation_outcome)


def activate_verified_tweak(controller: OperationController, outcome: OperationOutcome) -> TweakActivationResult:
    """Synchronous CLI/worker adapter; GUI may use the same parameters asynchronously."""
    parameters = activation_parameters(outcome)
    if parameters is None:
        return TweakActivationResult(outcome.success, False, outcome.message)
    try:
        ticket = controller.prepare(ACTIVATION_ACTION_ID, parameters)
        if ticket.blocked:
            return TweakActivationResult(True, False, ACTIVATION_WARNING + " " + ticket.plan.policy_decision.explanation)
        activated = controller.confirm(ticket, confirmed=True)
        if activated.status == "prepared":
            activated = controller.run(activated, timeout=8)
            if activated.status == "verifying":
                activated = controller.verify(activated)
        return activation_result(outcome, activated)
    except (ActionCenterError, OSError, RuntimeError, TypeError, ValueError, TimeoutExpired) as exc:
        return TweakActivationResult(True, False, ACTIVATION_WARNING + " " + str(exc))
