"""Read-only restoration offers derived from verified, bounded action history."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence, Any

from core.actions.contracts import ActionRun, ActionRuntime
from core.tweak_commands import valid_value, values_equal
from .tweaks import Tweak, TweakState


@dataclass(frozen=True)
class TweakRestoreOffer:
    source_run_id: str = ""
    before: str = ""
    after: str = ""
    message: str = ""


def read_tweak_runs(runtime: ActionRuntime) -> tuple[tuple[ActionRun, ...], str]:
    """Read without migration; unavailable or corrupt history grants no authority."""
    reader = getattr(runtime, "tweak_runs", None)
    if not callable(reader):
        return (), ""
    try:
        runs = reader()
        if not isinstance(runs, (list, tuple)) or any(not isinstance(run, ActionRun) for run in runs):
            raise ValueError("Invalid tweak history.")
        return tuple(runs), ""
    except (OSError, RuntimeError, TypeError, ValueError):
        return (), "Restore is unavailable because change history could not be read safely."


def restoration_for(tweak: Tweak, state: TweakState, runs: Sequence[ActionRun]) -> TweakRestoreOffer:
    """Only the latest attempt for this resource can offer a one-step restore."""
    relevant = [run for run in runs if run.action_id in {tweak.action_id, f"restore-{tweak.id}"} or f"tweak:{tweak.id}" in run.affected_resources]
    if not relevant:
        return TweakRestoreOffer()
    latest = relevant[-1]
    if latest.action_id == f"restore-{tweak.id}" and latest.state == "succeeded":
        return TweakRestoreOffer(message="The previous change has already been restored.")
    if latest.action_id != tweak.action_id or latest.state != "succeeded":
        return TweakRestoreOffer(message="Restore is unavailable after a later incomplete or unsuccessful change attempt.")
    verification = latest.verification_result or {}
    execution = latest.execution_result or {}
    data = verification.get("data")
    record: Any = data.get("tweak_change") if isinstance(data, dict) else None
    if execution.get("success") is not True or verification.get("success") is not True or not isinstance(record, dict):
        return TweakRestoreOffer(message="This change has no verified restore information.")
    if type(record.get("version")) is not int or record["version"] != 1 or record.get("tweak_id") != tweak.id or record.get("kind") != "change":
        return TweakRestoreOffer(message="This change has unsupported restore information.")
    before, after = record.get("before"), record.get("after")
    requested = latest.parameters.get("value")
    if not isinstance(before, str) or not isinstance(after, str) or not isinstance(requested, str) or not valid_value(tweak.id, before) or not values_equal(tweak.id, after, requested):
        return TweakRestoreOffer(message="The saved restore values could not be validated.")
    if values_equal(tweak.id, before, after):
        return TweakRestoreOffer()
    if state.status != "ready":
        return TweakRestoreOffer(message="Read the current setting successfully before restoring it.")
    if not values_equal(tweak.id, state.value, after):
        return TweakRestoreOffer(message="This setting changed outside Loofi. Restore is blocked to preserve its current value.")
    if tweak.id in {"kde-color", "power-profile"} and before not in {value for value, _label in state.choices}:
        return TweakRestoreOffer(message="The previous color scheme or power profile is no longer available.")
    return TweakRestoreOffer(latest.run_id, before, after)
