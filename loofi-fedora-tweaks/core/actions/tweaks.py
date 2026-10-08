"""Audited definitions for state-backed tweaks and explicit one-step restoration."""

from __future__ import annotations

import re
import shutil
import time
from functools import partial
from typing import Any, Mapping

from core.actions.contracts import ActionDefinition, ActionPlan, ActionRun, ActionRuntime, PolicyDecision, VerificationDecision
from core.tasks.tweaks import TWEAKS, Tweak, allowed_value, command_for, read_tweak, read_cursor_config
from core.tasks.tweak_history import TweakRestoreOffer, read_tweak_runs, restoration_for
from core.tweak_commands import CURSOR_TWEAK_IDS, values_equal, valid_value

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
    facts = {"current": state.value, "requested": value}
    if tweak.id in CURSOR_TWEAK_IDS:
        values, error = read_cursor_config(runtime.platform_profile(), runtime.execute_read_only)
        if error or values.get(tweak.id) != state.value:
            return PolicyDecision(False, "cursor_read_unavailable", error or "The pointer settings changed during inspection.")
        counterpart = next(item for item in CURSOR_TWEAK_IDS if item != tweak.id)
        facts.update({"counterpart_id": counterpart, "counterpart_value": values[counterpart]})
    return PolicyDecision(True, "tweak_ready", "The current setting and requested value were checked.", facts=facts)


def _preflight_restore(tweak: Tweak, parameters: Mapping[str, Any], runtime: ActionRuntime) -> PolicyDecision:
    try:
        offer = _restore_offer(tweak, parameters, runtime)
    except ValueError as exc:
        return PolicyDecision(False, "restore_unavailable", str(exc))
    facts = {"current": offer.after, "requested": offer.before, "source_run_id": offer.source_run_id}
    if tweak.id in CURSOR_TWEAK_IDS:
        values, error = read_cursor_config(runtime.platform_profile(), runtime.execute_read_only)
        if error or values.get(tweak.id) != offer.after:
            return PolicyDecision(False, "cursor_read_unavailable", error or "The pointer settings changed during inspection.")
        counterpart = next(item for item in CURSOR_TWEAK_IDS if item != tweak.id)
        facts.update({"counterpart_id": counterpart, "counterpart_value": values[counterpart]})
    return PolicyDecision(True, "restore_ready", "The saved change and current setting were checked.", facts=facts)


def _verify(tweak: Tweak, run: ActionRun, plan: ActionPlan, runtime: ActionRuntime) -> VerificationDecision:
    state = read_tweak(tweak, runtime.platform_profile(), runtime.execute_read_only)
    restoring = run.action_id == f"restore-{tweak.id}"
    target = str(plan.policy_decision.facts.get("requested", "")) if restoring else str(plan.parameters.get("value", ""))
    if state.status != "ready" or not values_equal(tweak.id, state.value, target):
        return VerificationDecision.failed(state.message or "The setting did not match the requested value after applying it.")
    if tweak.id in CURSOR_TWEAK_IDS:
        values, error = read_cursor_config(runtime.platform_profile(), runtime.execute_read_only)
        counterpart = next(item for item in CURSOR_TWEAK_IDS if item != tweak.id)
        facts = plan.policy_decision.facts
        if error or not values_equal(tweak.id, values.get(tweak.id, ""), target):
            return VerificationDecision.failed(error or "The pointer setting changed during verification.")
        if facts.get("counterpart_id") != counterpart or values.get(counterpart) != facts.get("counterpart_value"):
            return VerificationDecision.failed("The other pointer setting changed unexpectedly; the saved change could not be verified.")
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
    definitions.append(kwin_activation_definition())
    definitions.append(cursor_notification_definition())
    return definitions


def _activation_source(parameters: Mapping[str, Any], runtime: ActionRuntime) -> tuple[Tweak, str]:
    """Bind session activation to the latest independently verified setting write."""
    from core.tasks.tweaks import BY_ID
    from core.tweak_commands import KWIN_RUNTIME_KEYS, valid_value

    if set(parameters) != {"tweak_id", "source_run_id"}:
        raise ValueError("Activation requires only a tweak ID and source run ID.")
    tweak_id, source_id = parameters.get("tweak_id"), parameters.get("source_run_id")
    if not isinstance(tweak_id, str) or tweak_id not in KWIN_RUNTIME_KEYS or not isinstance(source_id, str) or not _RUN_ID.fullmatch(source_id):
        raise ValueError("Unsupported session activation source.")
    tweak = BY_ID[tweak_id]
    runs, error = read_tweak_runs(runtime)
    relevant = [run for run in runs if run.action_id in {tweak.action_id, f"restore-{tweak.id}"} or f"tweak:{tweak.id}" in run.affected_resources]
    if error or not relevant:
        raise ValueError(error or "No verified setting change is available for activation.")
    latest = relevant[-1]
    data = (latest.verification_result or {}).get("data", {})
    record = data.get("tweak_change") if isinstance(data, dict) else None
    restoring = latest.action_id == f"restore-{tweak.id}"
    if (latest.run_id != source_id or latest.state != "succeeded" or latest.action_id not in {tweak.action_id, f"restore-{tweak.id}"}
            or (latest.execution_result or {}).get("success") is not True or (latest.verification_result or {}).get("success") is not True
            or not isinstance(record, dict) or type(record.get("version")) is not int or record["version"] != 1
            or record.get("tweak_id") != tweak.id or record.get("kind") != ("restore" if restoring else "change")):
        raise ValueError("The source is not the latest verified setting change.")
    target = record.get("after")
    before = record.get("before")
    if not isinstance(target, str) or not isinstance(before, str) or not valid_value(tweak.id, target) or not valid_value(tweak.id, before):
        raise ValueError("The source setting values are invalid.")
    if not restoring and not values_equal(tweak.id, target, str(latest.parameters.get("value", ""))):
        raise ValueError("The source does not match its requested setting.")
    restore_source = latest.parameters.get("source_run_id")
    if restoring and (not isinstance(restore_source, str) or not _RUN_ID.fullmatch(restore_source) or record.get("source_run_id") != restore_source):
        raise ValueError("The source restoration record is inconsistent.")
    state = read_tweak(tweak, runtime.platform_profile(), runtime.execute_read_only)
    if state.status != "ready" or not values_equal(tweak.id, state.value, target):
        raise ValueError("The saved setting changed after verification; session activation is unavailable.")
    return tweak, target


def _render_activation(parameters: Mapping[str, Any], runtime: ActionRuntime) -> list[str]:
    from core.tweak_commands import KWIN_RECONFIGURE

    _activation_source(parameters, runtime)
    return list(KWIN_RECONFIGURE)


def _preflight_activation(parameters: Mapping[str, Any], runtime: ActionRuntime) -> PolicyDecision:
    try:
        tweak, target = _activation_source(parameters, runtime)
    except ValueError as exc:
        return PolicyDecision(False, "activation_source_unavailable", str(exc))
    if not shutil.which("dbus-send") or not shutil.which("gdbus"):
        return PolicyDecision(False, "activation_tools_unavailable", "Saved and verified; application in the current session is unverified because DBus tools are unavailable.")
    return PolicyDecision(True, "activation_ready", "The saved setting and verified source run were checked.", facts={"tweak_id": tweak.id, "requested": target})


def _verify_activation(_run: ActionRun, plan: ActionPlan, runtime: ActionRuntime) -> VerificationDecision:
    import ast
    from core.tweak_commands import KWIN_RUNTIME_KEYS, KWIN_SUPPORT
    from core.tasks.tweaks import normalize_kwin_runtime_value

    try:
        tweak, target = _activation_source(plan.parameters, runtime)
    except ValueError as exc:
        return VerificationDecision.failed(str(exc))
    # Reconfigure has no reply: KWin may apply it after the first read. Only
    # valid runtime mismatches permit another read; mutations are never retried.
    deadline = time.monotonic() + 1.0
    for attempt in range(3):
        result = runtime.execute_read_only(KWIN_SUPPORT, action_id="activate-kwin-tweak-runtime-read", timeout=1)
        if not result.success or len(result.stdout) > 1024 * 1024:
            return VerificationDecision.failed("Saved and verified; application in the current session could not be read.")
        try:
            payload = ast.literal_eval(result.stdout.strip())
        except (ValueError, SyntaxError, MemoryError, RecursionError):
            return VerificationDecision.failed("KWin runtime information could not be parsed safely.")
        if not isinstance(payload, tuple) or len(payload) != 1 or not isinstance(payload[0], str):
            return VerificationDecision.failed("KWin runtime information has an unsupported format.")
        matches = re.findall(rf"(?m)^\s*{re.escape(KWIN_RUNTIME_KEYS[tweak.id])}:\s*([^\s]+)\s*$", payload[0])
        active = normalize_kwin_runtime_value(tweak.id, matches[0]) if len(matches) == 1 else ""
        if not valid_value(tweak.id, active):
            return VerificationDecision.failed("KWin's active setting could not be read safely.")
        if values_equal(tweak.id, active, target):
            return VerificationDecision.succeeded("Saved and verified; applied and verified in the current Plasma session.", session_verified=True, tweak_id=tweak.id, value=target, source_run_id=plan.parameters["source_run_id"])
        if attempt == 2 or time.monotonic() + 0.1 >= deadline:
            break
        time.sleep(0.1)
        if time.monotonic() >= deadline:
            break
    return VerificationDecision.failed("Saved and verified; KWin's active setting did not match the saved value.")


def kwin_activation_definition() -> ActionDefinition:
    return ActionDefinition(
        id="activate-kwin-tweak", capability_id="tweaks.kwin-session", title="Apply verified KWin setting",
        description="Reload KWin configuration after a verified saved setting and independently inspect its active value.",
        parameter_schema={"tweak_id": {"type": "string", "required": True}, "source_run_id": {"type": "string", "required": True}},
        risk_level="low", privileged=False, confirmation_policy="explicit", interaction_policy="automatic",
        recovery_guidance="The saved setting remains verified and can still be restored through its original change history.",
        rollback_supported=False, command_renderer=_render_activation, preflight_checker=_preflight_activation,
        verifier=_verify_activation, operation_class="session", affected_resources=("session:kwin-configuration",),
    )


def _cursor_notification_source(parameters: Mapping[str, Any], runtime: ActionRuntime) -> tuple[Tweak, str]:
    """Require the latest successful saved change, including an explicit restore."""
    from core.tasks.tweaks import BY_ID

    if set(parameters) != {"tweak_id", "source_run_id"}:
        raise ValueError("Pointer notification requires only a tweak ID and source run ID.")
    tweak_id, source_id = parameters.get("tweak_id"), parameters.get("source_run_id")
    if not isinstance(tweak_id, str) or tweak_id not in CURSOR_TWEAK_IDS or not isinstance(source_id, str) or not _RUN_ID.fullmatch(source_id):
        raise ValueError("Unsupported pointer notification source.")
    tweak = BY_ID[tweak_id]
    runs, error = read_tweak_runs(runtime)
    relevant = [run for run in runs if run.action_id in {tweak.action_id, f"restore-{tweak.id}"} or f"tweak:{tweak.id}" in run.affected_resources]
    if error or not relevant:
        raise ValueError(error or "No verified pointer setting change is available for notification.")
    latest = relevant[-1]
    data = (latest.verification_result or {}).get("data", {})
    record = data.get("tweak_change") if isinstance(data, dict) else None
    restoring = latest.action_id == f"restore-{tweak.id}"
    if (latest.run_id != source_id or latest.state != "succeeded" or latest.action_id not in {tweak.action_id, f"restore-{tweak.id}"}
            or (latest.execution_result or {}).get("success") is not True or (latest.verification_result or {}).get("success") is not True
            or not isinstance(record, dict) or type(record.get("version")) is not int or record["version"] != 1
            or record.get("tweak_id") != tweak.id or record.get("kind") != ("restore" if restoring else "change")):
        raise ValueError("The source is not the latest verified pointer setting change.")
    target, before = record.get("after"), record.get("before")
    if not isinstance(target, str) or not isinstance(before, str) or not valid_value(tweak.id, target) or not valid_value(tweak.id, before):
        raise ValueError("The source pointer setting values are invalid.")
    if not restoring and not values_equal(tweak.id, target, str(latest.parameters.get("value", ""))):
        raise ValueError("The source does not match its requested pointer setting.")
    restore_source = latest.parameters.get("source_run_id")
    if restoring and (not isinstance(restore_source, str) or not _RUN_ID.fullmatch(restore_source) or record.get("source_run_id") != restore_source):
        raise ValueError("The source pointer restoration record is inconsistent.")
    state = read_tweak(tweak, runtime.platform_profile(), runtime.execute_read_only)
    if state.status != "ready" or not values_equal(tweak.id, state.value, target):
        raise ValueError("The saved pointer setting changed after verification; notification is unavailable.")
    return tweak, target


def _render_cursor_notification(parameters: Mapping[str, Any], runtime: ActionRuntime) -> list[str]:
    from core.tweak_commands import CURSOR_NOTIFY

    _cursor_notification_source(parameters, runtime)
    return list(CURSOR_NOTIFY)


def _preflight_cursor_notification(parameters: Mapping[str, Any], runtime: ActionRuntime) -> PolicyDecision:
    try:
        tweak, target = _cursor_notification_source(parameters, runtime)
    except ValueError as exc:
        return PolicyDecision(False, "cursor_notification_source_unavailable", str(exc))
    if not shutil.which("dbus-send"):
        return PolicyDecision(False, "cursor_notification_tools_unavailable", "Saved and verified; pointer notification could not be sent because dbus-send is unavailable. Visual effect is unverified.")
    return PolicyDecision(True, "cursor_notification_ready", "The saved pointer setting and verified source run were checked.",
                          facts={"tweak_id": tweak.id, "requested": target})


def _verify_cursor_notification(run: ActionRun, plan: ActionPlan, runtime: ActionRuntime) -> VerificationDecision:
    if (run.execution_result or {}).get("success") is not True:
        return VerificationDecision.failed("Saved and verified; pointer notification was not sent. Visual effect is unverified.")
    try:
        tweak, target = _cursor_notification_source(plan.parameters, runtime)
    except ValueError as exc:
        return VerificationDecision.failed(str(exc))
    return VerificationDecision.succeeded(
        "Saved and verified; pointer change notification sent. Visual effect is unverified.",
        notification_sent=True, tweak_id=tweak.id, value=target, source_run_id=plan.parameters["source_run_id"],
    )


def cursor_notification_definition() -> ActionDefinition:
    return ActionDefinition(
        id="notify-kde-cursor-change", capability_id="tweaks.cursor-session", title="Notify verified pointer change",
        description="Send Plasma's pointer change signal after independently verifying the saved setting. Visual effect is unverified.",
        parameter_schema={"tweak_id": {"type": "string", "required": True}, "source_run_id": {"type": "string", "required": True}},
        risk_level="low", privileged=False, confirmation_policy="explicit", interaction_policy="automatic",
        recovery_guidance="The saved setting remains verified and can still be restored through its original change history.",
        rollback_supported=False, command_renderer=_render_cursor_notification, preflight_checker=_preflight_cursor_notification,
        verifier=_verify_cursor_notification, operation_class="session", affected_resources=("session:cursor-notification",),
    )
