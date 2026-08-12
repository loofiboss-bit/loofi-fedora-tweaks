"""Read-only source adapters for the Trusted Change Journal."""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Mapping, Protocol, Sequence

from core.actions.stores import ActionPlanStore, ActionRunStore
from core.change_journal.models import (
    ChangeEvent,
    ChangeSource,
    ChangeSourceStatus,
    RecoveryCapability,
    stable_event_id,
)
from core.executor.command_facade import CommandFacade
from services.system.system import cached_which
from utils.history import HistoryManager, HistoryVersionError

SOURCE_TIMEOUT = 15


@dataclass(frozen=True)
class SourceResult:
    events: tuple[ChangeEvent, ...]
    status: ChangeSourceStatus


class ChangeSourceAdapter(Protocol):
    source: ChangeSource

    def collect(self, *, since: float | None = None) -> SourceResult:
        ...


def _timestamp(value: Any) -> float:
    if isinstance(value, (int, float)):
        return max(0.0, float(value))
    text = str(value or "").strip()
    if not text:
        return 0.0
    try:
        return max(0.0, float(text))
    except ValueError:
        try:
            return max(0.0, datetime.fromisoformat(text.replace("Z", "+00:00")).timestamp())
        except ValueError:
            return 0.0


class JSONCommandSource:
    """Base adapter executing one classified read-only JSON command."""

    source: ChangeSource
    binary: str
    vector: tuple[str, ...]

    def __init__(
        self,
        *,
        facade: CommandFacade | None = None,
        clock: Any = time.time,
    ):
        self.facade = facade or CommandFacade()
        self.clock = clock

    def collect(self, *, since: float | None = None) -> SourceResult:
        collected_at = float(self.clock())
        if cached_which(self.binary) is None:
            return SourceResult(
                (),
                ChangeSourceStatus(
                    self.source,
                    "unavailable",
                    collected_at,
                    "tool_unavailable",
                    f"{self.binary} is not installed.",
                ),
            )
        result = self.facade.execute(
            self.vector,
            timeout=SOURCE_TIMEOUT,
            action_id=f"change-journal:{self.source}",
        )
        if not result.success:
            return SourceResult(
                (),
                ChangeSourceStatus(
                    self.source,
                    "unavailable",
                    collected_at,
                    "source_failed",
                    result.stderr or result.message,
                ),
            )
        try:
            payload = json.loads(result.stdout or "[]")
            events = tuple(
                event
                for event in self._parse(payload)
                if since is None or event.occurred_at >= since
            )
        except (json.JSONDecodeError, TypeError, ValueError, KeyError) as exc:
            return SourceResult(
                (),
                ChangeSourceStatus(
                    self.source,
                    "partial",
                    collected_at,
                    "invalid_payload",
                    str(exc),
                ),
            )
        return SourceResult(
            events,
            ChangeSourceStatus(self.source, "available", collected_at),
        )

    def _parse(self, payload: Any) -> Sequence[ChangeEvent]:
        raise NotImplementedError


class DNF5HistorySource(JSONCommandSource):
    source: ChangeSource = "dnf5"
    binary = "dnf5"
    vector = ("dnf5", "history", "list", "--json")

    def _parse(self, payload: Any) -> Sequence[ChangeEvent]:
        if not isinstance(payload, list):
            raise ValueError("DNF5 history must be a JSON array.")
        events: list[ChangeEvent] = []
        for raw in payload:
            if not isinstance(raw, Mapping):
                continue
            transaction_id = int(raw.get("id", 0))
            if transaction_id <= 0:
                continue
            altered = max(0, int(raw.get("altered_count", 0)))
            status = str(raw.get("status", "unknown"))
            recovery = RecoveryCapability()
            if status.lower() in {"ok", "success", "succeeded"}:
                recovery = RecoveryCapability(
                    "action_center",
                    "dnf5-history-undo",
                    {"transaction_id": transaction_id},
                    "Prepare an offline undo plan after fresh package and rpmdb checks.",
                )
            events.append(
                ChangeEvent(
                    event_id=stable_event_id("dnf5", str(transaction_id)),
                    source="dnf5",
                    occurred_at=_timestamp(raw.get("end_time") or raw.get("start_time")),
                    actor_class="system" if int(raw.get("user_id", -1)) == 0 else "user",
                    summary=f"DNF transaction {transaction_id} changed {altered} package items.",
                    resources=("package-manager", "rpmdb"),
                    after_facts={
                        "transaction_id": transaction_id,
                        "altered_count": altered,
                        "releasever": raw.get("releasever", ""),
                    },
                    state=status,
                    recovery=recovery,
                )
            )
        return events


class RpmOstreeHistorySource(JSONCommandSource):
    source: ChangeSource = "rpm_ostree"
    binary = "rpm-ostree"
    vector = ("rpm-ostree", "status", "--json")

    def _parse(self, payload: Any) -> Sequence[ChangeEvent]:
        if not isinstance(payload, Mapping):
            raise ValueError("rpm-ostree status must be a JSON object.")
        deployments = payload.get("deployments", [])
        if not isinstance(deployments, list):
            raise ValueError("rpm-ostree deployments must be a JSON array.")
        rollback = next(
            (
                item
                for item in deployments
                if isinstance(item, Mapping) and not bool(item.get("booted", False))
            ),
            None,
        )
        events: list[ChangeEvent] = []
        for index, raw in enumerate(deployments):
            if not isinstance(raw, Mapping):
                continue
            checksum = str(raw.get("checksum", "") or raw.get("id", "") or index)
            booted = bool(raw.get("booted", False))
            staged = bool(raw.get("staged", False))
            recovery = RecoveryCapability()
            if booted and isinstance(rollback, Mapping):
                rollback_checksum = str(
                    rollback.get("checksum", "") or rollback.get("id", "")
                )
                if rollback_checksum:
                    recovery = RecoveryCapability(
                        "action_center",
                        "rpm-ostree-rollback",
                        {
                            "expected_deployment": checksum,
                            "rollback_deployment": rollback_checksum,
                        },
                        "Stage the existing rollback deployment and verify it after reboot.",
                    )
            events.append(
                ChangeEvent(
                    event_id=stable_event_id("rpm_ostree", checksum),
                    source="rpm_ostree",
                    occurred_at=_timestamp(raw.get("timestamp")),
                    actor_class="system",
                    summary=(
                        "Booted rpm-ostree deployment."
                        if booted
                        else "Staged rpm-ostree deployment."
                        if staged
                        else "Available rpm-ostree deployment."
                    ),
                    resources=("rpm-ostree-deployment", checksum),
                    after_facts={
                        "checksum": checksum,
                        "version": raw.get("version", ""),
                        "origin": raw.get("origin", ""),
                        "booted": booted,
                        "staged": staged,
                    },
                    state="booted" if booted else "staged" if staged else "available",
                    reboot_required=staged,
                    recovery=recovery,
                )
            )
        return events


class FlatpakHistorySource(JSONCommandSource):
    source: ChangeSource = "flatpak"
    binary = "flatpak"
    vector = ("flatpak", "history", "--json", "--reverse")

    def _parse(self, payload: Any) -> Sequence[ChangeEvent]:
        if not isinstance(payload, list):
            raise ValueError("Flatpak history must be a JSON array.")
        events: list[ChangeEvent] = []
        for index, raw in enumerate(payload):
            if not isinstance(raw, Mapping):
                continue
            reference = str(raw.get("ref", "") or raw.get("application", "") or "unknown")
            change = str(raw.get("change", "change") or "change")
            source_id = ":".join(
                (
                    str(raw.get("time", "")),
                    change,
                    reference,
                    str(raw.get("commit", "")),
                    str(index),
                )
            )
            events.append(
                ChangeEvent(
                    event_id=stable_event_id("flatpak", source_id),
                    source="flatpak",
                    occurred_at=_timestamp(raw.get("time")),
                    actor_class="user" if raw.get("user") else "system",
                    summary=f"Flatpak {change}: {reference}",
                    resources=("flatpak", reference),
                    before_facts={"commit": raw.get("old-commit", "")},
                    after_facts={
                        "commit": raw.get("commit", ""),
                        "installation": raw.get("installation", ""),
                        "remote": raw.get("remote", ""),
                    },
                    state=change,
                    recovery=RecoveryCapability(
                        "manual_guidance",
                        guidance="Review the exact ref and available commits before changing it.",
                    ),
                )
            )
        return events


class FwupdHistorySource(JSONCommandSource):
    source: ChangeSource = "fwupd"
    binary = "fwupdmgr"
    vector = ("fwupdmgr", "get-history", "--json")

    def _parse(self, payload: Any) -> Sequence[ChangeEvent]:
        devices = payload.get("Devices", []) if isinstance(payload, Mapping) else payload
        if not isinstance(devices, list):
            raise ValueError("fwupd history must contain a Devices array.")
        events: list[ChangeEvent] = []
        for index, raw in enumerate(devices):
            if not isinstance(raw, Mapping):
                continue
            device_id = str(raw.get("DeviceId", "") or raw.get("Guid", "") or index)
            name = str(raw.get("Name", "") or "Firmware device")
            version = str(raw.get("Version", "") or "")
            events.append(
                ChangeEvent(
                    event_id=stable_event_id("fwupd", f"{device_id}:{version}:{index}"),
                    source="fwupd",
                    occurred_at=_timestamp(raw.get("Created") or raw.get("Modified")),
                    actor_class="system",
                    summary=f"Firmware history: {name}",
                    resources=("firmware", device_id),
                    after_facts={"name": name, "version": version},
                    state=str(raw.get("UpdateState", "recorded")),
                    reboot_required=bool(raw.get("NeedsReboot", False)),
                    recovery=RecoveryCapability(
                        "manual_guidance",
                        guidance="Firmware rollback is not automated; review vendor and fwupd guidance.",
                    ),
                )
            )
        return events


class ActionCenterHistorySource:
    source: ChangeSource = "action_center"

    def __init__(
        self,
        *,
        plan_store: ActionPlanStore | None = None,
        run_store: ActionRunStore | None = None,
        clock: Any = time.time,
    ):
        self.plan_store = plan_store or ActionPlanStore()
        self.run_store = run_store or ActionRunStore()
        self.clock = clock

    def collect(self, *, since: float | None = None) -> SourceResult:
        collected_at = float(self.clock())
        try:
            plans = self.plan_store.list_read_only()
            runs = self.run_store.list_read_only()
            plan_by_id = {plan.plan_id: plan for plan in plans}
            events: list[ChangeEvent] = []
            for run in runs:
                plan = plan_by_id.get(run.plan_id)
                resources = tuple(plan.affected_resources) if plan else ("host-system",)
                event = ChangeEvent(
                    event_id=stable_event_id("action_center", f"run:{run.run_id}"),
                    source="action_center",
                    occurred_at=run.updated_at or run.created_at,
                    actor_class="user",
                    summary=f"Action Center run: {run.action_id}",
                    resources=resources,
                    before_facts={},
                    after_facts={
                        "expected": {
                            "action_id": run.action_id,
                            "risk_level": plan.risk_level if plan else "unknown",
                            "reboot_policy": plan.reboot_policy if plan else "unknown",
                            "affected_resources": list(resources),
                        },
                        "plan_id": run.plan_id,
                        "run_id": run.run_id,
                        "action_id": run.action_id,
                        "execution": _safe_result(run.execution_result),
                        "verification": _safe_result(run.verification_result),
                        "recovery": {
                            "status": run.recovery_status,
                            "rollback_supported": bool(plan.rollback_supported) if plan else False,
                        },
                    },
                    state=run.state,
                    reboot_required=bool(getattr(run, "reboot_required", False)) or run.state == "awaiting_reboot",
                )
                if since is None or event.occurred_at >= since:
                    events.append(event)
            return SourceResult(
                tuple(events),
                ChangeSourceStatus(self.source, "available", collected_at),
            )
        except (OSError, RuntimeError, TypeError, ValueError) as exc:
            return SourceResult(
                (),
                ChangeSourceStatus(
                    self.source,
                    "partial",
                    collected_at,
                    "state_read_failed",
                    str(exc),
                ),
            )


def _safe_result(result: Mapping[str, Any] | None) -> dict[str, Any]:
    """Keep journal evidence typed while excluding raw output and vectors."""
    if not isinstance(result, Mapping):
        return {}
    return {
        key: result[key]
        for key in ("success", "message", "exit_code", "needs_reboot", "verification_state")
        if key in result
    }


class LoofiHistorySource:
    source: ChangeSource = "loofi_app"

    def __init__(
        self,
        *,
        history: HistoryManager | None = None,
        clock: Any = time.time,
    ):
        self.history = history or HistoryManager()
        self.clock = clock

    def collect(self, *, since: float | None = None) -> SourceResult:
        collected_at = float(self.clock())
        try:
            events: list[ChangeEvent] = []
            for entry in self.history.get_recent(50):
                occurred_at = _timestamp(entry.timestamp)
                if since is not None and occurred_at < since:
                    continue
                recovery = RecoveryCapability()
                if entry.recovery_action_id:
                    recovery = RecoveryCapability(
                        "action_center",
                        entry.recovery_action_id,
                        entry.recovery_parameters,
                        "Create a fresh reviewed Action Center plan.",
                    )
                events.append(
                    ChangeEvent(
                        event_id=stable_event_id("loofi_app", entry.id),
                        source="loofi_app",
                        occurred_at=occurred_at,
                        actor_class="user",
                        summary=entry.description,
                        resources=("loofi-app-state",),
                        state="recorded",
                        recovery=recovery,
                    )
                )
            return SourceResult(
                tuple(events),
                ChangeSourceStatus(self.source, "available", collected_at),
            )
        except HistoryVersionError as exc:
            return SourceResult(
                (),
                ChangeSourceStatus(
                    self.source,
                    "unavailable",
                    collected_at,
                    "future_schema",
                    str(exc),
                ),
            )
        except (OSError, RuntimeError, TypeError, ValueError) as exc:
            return SourceResult(
                (),
                ChangeSourceStatus(
                    self.source,
                    "partial",
                    collected_at,
                    "state_read_failed",
                    str(exc),
                ),
            )


def default_sources() -> tuple[ChangeSourceAdapter, ...]:
    return (
        ActionCenterHistorySource(),
        DNF5HistorySource(),
        RpmOstreeHistorySource(),
        FlatpakHistorySource(),
        FwupdHistorySource(),
        LoofiHistorySource(),
    )
