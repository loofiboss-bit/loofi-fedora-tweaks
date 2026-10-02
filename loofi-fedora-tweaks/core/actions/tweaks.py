"""Audited definitions for state-backed tweaks and explicit one-step restoration."""

from __future__ import annotations

import re
from functools import partial
from typing import Any, Mapping

from core.actions.contracts import ActionDefinition, ActionPlan, ActionRun, ActionRuntime, PolicyDecision, VerificationDecision
from core.tasks.tweaks import TWEAKS, Tweak, allowed_value, command_for, read_tweak
from core.tasks.tweak_history import TweakRestoreOffer, read_tweak_runs, restoration_for
from core.tweak_commands import values_equal

_RUN_ID = re.compile(r"[A-Za-z0-9._:-]{1,128}\Z")


def _requested(parameters: Mapping[str, Any]) -> str:
    value = parameters.get("value")
    if not isinstance(value, str):
        raise ValueError("A supported setting value is required.")
    return value


def _restore_offer(tweak: Tweak, parameters: Mapping[str, Any], runtime: ActionRuntime) -> TweakRestoreOffer:
    source_id = parameters.get("source_run_id")
    if set(parameters) != {"source_run_id"} or not isinstance(source_id, str) or not _RUN_ID.fullmatch(source_id):
        raise ValueError("Restore requires only a valid source run ID.")
    state = read_tweak(tweak, runtime.platform_profile(), runtime.execute_read_only)
    runs, error = read_tweak_runs(runtime)
    offer = restoration_for(tweak, state, runs)
    if error or not offer.source_run_id or offer.source_run_id != source_id:
        raise ValueError(error or offer.message or "The selected change is no longer the latest restorable change.")
    return offer


def _render(tweak: Tweak, parameters: Mapping[str, Any], _runtime: ActionRuntime) -> list[str]:
    return command_for(tweak, _requested(parameters))


def _render_restore(tweak: Tweak, parameters: Mapping[str, Any], runtime: ActionRuntime) -> list[str]:
    return command_for(tweak, _restore_offer(tweak, parameters, runtime).before, restoring=True)


def _preflight(tweak: Tweak, parameters: Mapping[str, Any], runtime: ActionRuntime) -> PolicyDecision:
    state = read_tweak(tweak, runtime.platform_profile(), runtime.execute_read_only)
    if state.status != "ready":
        return PolicyDecision(False, "tweak_unavailable", state.message or "The setting is unavailable.")
    value = _requested(parameters)
    if not allowed_value(tweak, value, state.choices):
        return PolicyDecision(False, "invalid_choice", "The selected value is not available on this system.")
    return PolicyDecision(True, "tweak_ready", "The current setting and requested value were checked.", facts={"current": state.value, "requested": value})


def _preflight_restore(tweak: Tweak, parameters: Mapping[str, Any], runtime: ActionRuntime) -> PolicyDecision:
    try:
        offer = _restore_offer(tweak, parameters, runtime)
    except ValueError as exc:
        return PolicyDecision(False, "restore_unavailable", str(exc))
    return PolicyDecision(True, "restore_ready", "The saved change and current setting were checked.", facts={
        "current": offer.after, "requested": offer.before, "source_run_id": offer.source_run_id,
    })


def _verify(tweak: Tweak, run: ActionRun, plan: ActionPlan, runtime: ActionRuntime) -> VerificationDecision:
    state = read_tweak(tweak, runtime.platform_profile(), runtime.execute_read_only)
    restoring = run.action_id == f"restore-{tweak.id}"
    target = str(plan.policy_decision.facts.get("requested", "")) if restoring else str(plan.parameters.get("value", ""))
    if state.status != "ready" or not values_equal(tweak.id, state.value, target):
        return VerificationDecision.failed(state.message or "The setting did not match the requested value after applying it.")
    record = {
        "version": 1,
        "kind": "restore" if restoring else "change",
        "tweak_id": tweak.id,
        "before": str(plan.policy_decision.facts.get("current", "")),
        "after": state.value,
    }
    if restoring:
        record["source_run_id"] = str(plan.parameters["source_run_id"])
    return VerificationDecision.succeeded("The saved setting was independently read back.", value=state.value, tweak_change=record)


def tweak_action_definitions() -> list[ActionDefinition]:
    definitions: list[ActionDefinition] = []
    for tweak in TWEAKS:
        for restoring in (False, True):
            definitions.append(ActionDefinition(
                id=f"restore-{tweak.id}" if restoring else tweak.action_id,
                capability_id=f"tweaks.{tweak.id}",
                title=f"Restore {tweak.title}" if restoring else tweak.title,
                description="Restore the previous value of the latest verified Loofi change." if restoring else tweak.description,
                parameter_schema={"source_run_id" if restoring else "value": {"type": "string", "required": True}},
                risk_level="medium" if tweak.privileged else "low",
                privileged=tweak.privileged,
                confirmation_policy="explicit",
                recovery_guidance="Review the current setting; restoration is available only for the latest verified change.",
                rollback_supported=False,
                command_renderer=partial(_render_restore if restoring else _render, tweak),
                preflight_checker=partial(_preflight_restore if restoring else _preflight, tweak),
                verifier=partial(_verify, tweak),
                operation_class="host" if tweak.system_wide else "session",
                affected_resources=(f"tweak:{tweak.id}",),
                interaction_policy="confirm" if (restoring or tweak.privileged) else "automatic",
            ))
    return definitions
