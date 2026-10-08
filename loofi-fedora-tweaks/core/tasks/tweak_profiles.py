"""Portable user settings with immutable local review and sequential authority."""
from __future__ import annotations

import hashlib
import json
import math
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from subprocess import TimeoutExpired
from typing import Callable, Iterable

from core.actions.operation_controller import OperationController
from core.actions.orchestrator import ActionCenterError
from core.actions.tweak_operations import activate_verified_tweak, activation_parameters
from core.actions.tweak_operations import cursor_notification_parameters, notify_verified_cursor_change
from core.actions.contracts import ActionDefinition, ActionRuntime
from core.executor.action_result import ActionResult
from core.fedora_release_policy import FEDORA_RELEASE_POLICY
from core.state.atomic_io import atomic_write_json
from core.tasks.tweaks import BY_ID, _profile_desktop, allowed_value, command_for, read_tweak, snapshot
from core.tweak_commands import values_equal

SCHEMA = "loofi.tweak-profile/v1"
MAX_BYTES = 64 * 1024
REVIEW_TTL = 30 * 60


@dataclass(frozen=True)
class TweakProfile:
    name: str
    desktop: str
    settings: tuple[tuple[str, str], ...]

    def to_dict(self) -> dict:
        return {"schema": SCHEMA, "name": self.name, "desktop": self.desktop,
                "settings": [{"id": key, "value": value} for key, value in self.settings]}


@dataclass(frozen=True)
class ProfileExport:
    profile: TweakProfile
    omitted: tuple[tuple[str, str], ...]

    def to_dict(self) -> dict:
        return {"profile": self.profile.to_dict(), "omitted": [{"id": key, "reason": reason} for key, reason in self.omitted]}


@dataclass(frozen=True)
class ProfileReviewEntry:
    id: str
    title: str
    before: str
    value: str
    status: str
    message: str = ""
    action_id: str = ""
    definition_fingerprint: str = ""
    command: tuple[str, ...] = ()


@dataclass(frozen=True)
class ProfileReview:
    name: str
    desktop: str
    entries: tuple[ProfileReviewEntry, ...]
    created_at: float
    target: str = FEDORA_RELEASE_POLICY.stable_target

    def to_dict(self) -> dict:
        return {"schema": "loofi.tweak-profile-review/v1", "name": self.name, "desktop": self.desktop,
                "created_at": self.created_at, "expires_at": self.created_at + REVIEW_TTL,
                "target": self.target, "entries": [asdict(item) for item in self.entries]}


@dataclass(frozen=True)
class ProfileEntryResult:
    id: str
    status: str
    message: str
    run_id: str = ""


@dataclass(frozen=True)
class ProfileResult:
    status: str
    entries: tuple[ProfileEntryResult, ...]
    message: str

    @property
    def success(self) -> bool:
        return self.status == "succeeded"

    def to_dict(self) -> dict:
        return {"schema": "loofi.tweak-profile-result/v1", "status": self.status,
                "message": self.message, "entries": [asdict(item) for item in self.entries]}


def _unique_object(pairs: list[tuple[str, object]]) -> dict:
    result: dict = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Profile contains duplicate JSON keys.")
        result[key] = value
    return result


def parse_profile(data: bytes) -> TweakProfile:
    """Validate a small, closed portable format; no commands or restore history."""
    if len(data) > MAX_BYTES:
        raise ValueError("Profile exceeds the 64 KiB size limit.")
    try:
        payload = json.loads(data.decode("utf-8"), object_pairs_hook=_unique_object)
    except (UnicodeDecodeError, json.JSONDecodeError, RecursionError) as exc:
        raise ValueError("Profile is not valid UTF-8 JSON.") from exc
    if not isinstance(payload, dict) or set(payload) != {"schema", "name", "desktop", "settings"}:
        raise ValueError("Profile must contain only schema, name, desktop and settings.")
    if payload["schema"] != SCHEMA:
        raise ValueError("Unsupported profile format or future version.")
    name = payload["name"]
    if not isinstance(name, str) or not name.strip() or len(name) > 120 or any(ord(c) < 32 for c in name):
        raise ValueError("Profile name must contain 1–120 printable characters.")
    if payload["desktop"] not in ("gnome", "kde"):
        raise ValueError("Profile desktop must be GNOME or KDE.")
    rows = payload["settings"]
    if not isinstance(rows, list) or len(rows) > 128:
        raise ValueError("Profile settings must be a list of at most 128 entries.")
    entries: list[tuple[str, str]] = []
    seen: set[str] = set()
    for row in rows:
        if not isinstance(row, dict) or set(row) != {"id", "value"}:
            raise ValueError("Each profile setting must contain only id and value.")
        key, value = row["id"], row["value"]
        if (not isinstance(key, str) or not key or len(key) > 128 or any(c not in "abcdefghijklmnopqrstuvwxyz0123456789-" for c in key)
                or not isinstance(value, str) or not value or len(value) > 128 or any(ord(c) < 32 for c in value)):
            raise ValueError("Invalid profile setting identifier or value.")
        if key in seen:
            raise ValueError("Profile contains duplicate setting identifiers.")
        seen.add(key)
        entries.append((key, value))
    return TweakProfile(name, payload["desktop"], tuple(entries))


def load_profile(path: Path) -> TweakProfile:
    with Path(path).open("rb") as stream:
        return parse_profile(stream.read(MAX_BYTES + 1))


def save_profile(path: Path, profile: TweakProfile) -> None:
    payload = profile.to_dict()
    parse_profile(json.dumps(payload).encode("utf-8"))
    atomic_write_json(Path(path), payload, keep_backup=False)


def export_profile(name: str, profile: object, runtime: ActionRuntime, selected_ids: Iterable[str] | None = None,
                   *, is_cancelled: Callable[[], bool] | None = None) -> ProfileExport:
    desktop = _profile_desktop(profile)
    if desktop not in ("gnome", "kde"):
        raise ValueError("A supported Fedora GNOME or KDE desktop is required.")
    selected = set(selected_ids) if selected_ids is not None else None
    entries: list[tuple[str, str]] = []
    omitted: list[tuple[str, str]] = []
    states = snapshot(profile, runtime, is_cancelled=is_cancelled)
    seen = {state.tweak.id for state in states}
    if selected is not None:
        omitted.extend((key, "Unknown or unavailable on this desktop.") for key in sorted(selected - seen))
    for state in states:
        tweak = state.tweak
        if selected is not None and tweak.id not in selected:
            continue
        if tweak.system_wide or tweak.privileged:
            omitted.append((tweak.id, "System-wide settings are not portable."))
        elif state.status != "ready":
            omitted.append((tweak.id, state.message or "Current value is unavailable."))
        elif not allowed_value(tweak, state.value, state.choices):
            omitted.append((tweak.id, "Custom value is outside the current supported choices."))
        else:
            entries.append((tweak.id, state.value))
    if is_cancelled and is_cancelled():
        raise ValueError("Profile export cancelled; no profile was saved.")
    result = TweakProfile(name, desktop, tuple(entries))
    parse_profile(json.dumps(result.to_dict()).encode("utf-8"))
    return ProfileExport(result, tuple(omitted))


def _definition_fingerprint(definition: ActionDefinition) -> str:
    return hashlib.sha256(json.dumps(definition.to_dict(), sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def review_profile(profile: TweakProfile, controller: OperationController, *, is_cancelled: Callable[[], bool] | None = None,
                   clock: Callable[[], float] = time.time) -> ProfileReview:
    """Read a review without persisting an Action Center plan for each row."""
    profile = parse_profile(json.dumps(profile.to_dict()).encode("utf-8"))
    runtime = controller.orchestrator.runtime
    host = runtime.platform_profile()
    if _profile_desktop(host) != profile.desktop:
        raise ValueError("Profiles can only be loaded on the same supported desktop environment.")
    deadline = time.monotonic() + 20.0
    cancelled = is_cancelled or (lambda: False)

    def reader(vector: list[str], *, action_id: str, timeout: int = 8) -> ActionResult:
        remaining = deadline - time.monotonic()
        if cancelled() or remaining <= 0:
            return ActionResult.fail("Profile inspection cancelled or its time limit was reached.")
        return runtime.execute_read_only(vector, action_id=action_id, timeout=min(float(timeout), remaining))

    entries: list[ProfileReviewEntry] = []
    for key, value in profile.settings:
        tweak = BY_ID.get(key)
        if tweak is None or tweak.system_wide or tweak.privileged or tweak.desktop != profile.desktop:
            entries.append(ProfileReviewEntry(key, key, "", value, "unavailable", "Unknown or non-portable setting."))
            continue
        state = read_tweak(tweak, host, reader)
        definition = controller.orchestrator.catalog.get(tweak.action_id)
        if state.status != "ready" or definition is None:
            entries.append(ProfileReviewEntry(key, tweak.title, state.value, value, "unavailable", state.message or "Action is unavailable."))
        elif not allowed_value(tweak, value, state.choices):
            entries.append(ProfileReviewEntry(key, tweak.title, state.value, value, "invalid", "Target is not a current supported choice."))
        else:
            command = tuple(command_for(tweak, value))
            entries.append(ProfileReviewEntry(key, tweak.title, state.value, value,
                                              "unchanged" if values_equal(key, state.value, value) else "ready",
                                              action_id=tweak.action_id, definition_fingerprint=_definition_fingerprint(definition), command=command))
    if cancelled():
        raise ValueError("Profile review cancelled; no settings were changed.")
    return ProfileReview(profile.name, profile.desktop, tuple(entries), clock())


def apply_profile(review: ProfileReview, controller: OperationController, *, confirmed: bool,
                  selected_ids: Iterable[str] | None = None, is_cancelled: Callable[[], bool] | None = None,
                  clock: Callable[[], float] = time.time) -> ProfileResult:
    """Confirm the local review, then prepare only one matching action at a time."""
    if not confirmed:
        return ProfileResult("confirmation_required", (), "Review the profile and explicitly confirm its changes.")
    selected = set(selected_ids) if selected_ids is not None else {entry.id for entry in review.entries if entry.status == "ready"}
    if not selected <= {entry.id for entry in review.entries if entry.status == "ready"}:
        return ProfileResult("blocked", (), "Only available changed entries from the review may be selected.")
    results: list[ProfileEntryResult] = []
    stopped = ""
    final = "succeeded"
    runtime = controller.orchestrator.runtime
    for entry in review.entries:
        if entry.id not in selected:
            results.append(ProfileEntryResult(entry.id, "skipped", entry.message or "Not selected or already matches."))
            continue
        if stopped:
            results.append(ProfileEntryResult(entry.id, "not_started", stopped))
            continue
        try:
            now = clock()
            if is_cancelled and is_cancelled():
                final, stopped = "cancelled", "Profile cancelled; remaining settings were not changed."
            elif not math.isfinite(review.created_at) or now < review.created_at or now >= review.created_at + REVIEW_TTL:
                final, stopped = "blocked", "The profile review expired. Load and review it again."
            elif _profile_desktop(runtime.platform_profile()) != review.desktop:
                final, stopped = "blocked", "The desktop changed after review."
            else:
                tweak = BY_ID.get(entry.id)
                definition = controller.orchestrator.catalog.get(entry.action_id)
                if (tweak is None or tweak.system_wide or tweak.privileged or tweak.action_id != entry.action_id or definition is None
                        or _definition_fingerprint(definition) != entry.definition_fingerprint
                        or tuple(command_for(tweak, entry.value)) != entry.command):
                    final, stopped = "blocked", "The setting action changed after review."
                else:
                    state = read_tweak(tweak, runtime.platform_profile(), runtime.execute_read_only)
                    if state.status != "ready" or not values_equal(entry.id, state.value, entry.before) or not allowed_value(tweak, entry.value, state.choices):
                        final, stopped = "blocked", "The current setting or supported choices changed after review."
                    else:
                        ticket = controller.prepare(entry.action_id, {"value": entry.value}, target=review.target)
                        facts = ticket.plan.policy_decision.facts
                        if (ticket.blocked or tuple(ticket.plan.preview) != entry.command
                                or not values_equal(entry.id, str(facts.get("current", "")), entry.before)
                                or facts.get("requested") != entry.value):
                            final, stopped = "blocked", "The prepared action no longer matches the approved profile review."
                        elif is_cancelled and is_cancelled():
                            final, stopped = "cancelled", "Profile cancelled before this setting was changed."
                        else:
                            outcome = controller.confirm(ticket, confirmed=True)
                            if outcome.status == "prepared":
                                outcome = controller.run(outcome)
                                if outcome.status == "verifying":
                                    outcome = controller.verify(outcome)
                            message = outcome.message
                            entry_status = "succeeded" if outcome.success else outcome.status
                            if outcome.success and activation_parameters(outcome):
                                activation = activate_verified_tweak(controller, outcome)
                                message = activation.message
                                if not activation.session_verified:
                                    final, stopped = "verification_failed", message
                                    entry_status = "verification_failed"
                            if outcome.success and cursor_notification_parameters(outcome):
                                notification = notify_verified_cursor_change(controller, outcome)
                                message = notification.message
                                if not notification.notification_sent:
                                    final, stopped = "failed", message
                                    entry_status = "failed"
                            if not outcome.success:
                                final, stopped = outcome.status, message
                            results.append(ProfileEntryResult(entry.id, entry_status, message, outcome.run_id))
                            continue
        except (ActionCenterError, OSError, RuntimeError, TypeError, ValueError, TimeoutExpired) as exc:
            final, stopped = "failed", str(exc)
        results.append(ProfileEntryResult(entry.id, final, stopped))
    return ProfileResult(final, tuple(results), stopped or "Selected settings were independently verified. Previous values remain in Activity.")
