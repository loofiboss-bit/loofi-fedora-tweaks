"""Audited definitions for the closed Fedora tweak controls."""

from __future__ import annotations

from functools import partial
from typing import Any, Mapping

from core.actions.contracts import ActionDefinition, ActionPlan, ActionRun, ActionRuntime, PolicyDecision, VerificationDecision
from core.tasks.tweaks import TWEAKS, Tweak, allowed_value, command_for, read_tweak


def _requested(parameters: Mapping[str, Any]) -> str:
    value = parameters.get("value")
    if not isinstance(value, str):
        raise ValueError("A supported setting value is required.")
    return value


def _render(tweak: Tweak, parameters: Mapping[str, Any], _runtime: ActionRuntime) -> list[str]:
    return command_for(tweak, _requested(parameters))


def _preflight(tweak: Tweak, parameters: Mapping[str, Any], runtime: ActionRuntime) -> PolicyDecision:
    state = read_tweak(tweak, runtime.platform_profile(), runtime.execute_read_only)
    if state.status != "ready":
        return PolicyDecision(False, "tweak_unavailable", state.message or "The setting is unavailable.")
    value = _requested(parameters)
    if not allowed_value(tweak, value, state.choices):
        return PolicyDecision(False, "invalid_choice", "The selected value is not available on this system.")
    return PolicyDecision(True, "tweak_ready", "The current setting and requested value were checked.", facts={"current": state.value, "requested": value})


def _verify(tweak: Tweak, run: ActionRun, plan: ActionPlan, runtime: ActionRuntime) -> VerificationDecision:
    state = read_tweak(tweak, runtime.platform_profile(), runtime.execute_read_only)
    target = str(plan.parameters.get("value", ""))
    if state.status != "ready" or state.value != target:
        return VerificationDecision.failed(state.message or "The setting did not match the requested value after applying it.")
    return VerificationDecision.succeeded("The setting was independently read back.", value=state.value)


def tweak_action_definitions() -> list[ActionDefinition]:
    definitions: list[ActionDefinition] = []
    for tweak in TWEAKS:
        definitions.append(
            ActionDefinition(
                id=tweak.action_id,
                capability_id=f"tweaks.{tweak.id}",
                title=tweak.title,
                description=tweak.description,
                parameter_schema={"value": {"type": "string", "required": True}},
                risk_level="low",
                privileged=False,
                confirmation_policy="explicit",
                recovery_guidance="Select the previous value if you want to restore this setting.",
                rollback_supported=False,
                command_renderer=partial(_render, tweak),
                preflight_checker=partial(_preflight, tweak),
                verifier=partial(_verify, tweak),
                operation_class="host" if tweak.system_wide else "session",
                affected_resources=(f"tweak:{tweak.id}",),
                interaction_policy="automatic",
            )
        )
    return definitions
