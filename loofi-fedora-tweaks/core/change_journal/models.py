"""Immutable, privacy-bounded contracts for the Trusted Change Journal."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field, replace
from types import MappingProxyType
from typing import Any, Literal, Mapping

from core.privacy import redact_payload, redact_text

CHANGE_JOURNAL_SCHEMA = "loofi.change-journal/v1"

ChangeSource = Literal[
    "action_center",
    "dnf5",
    "rpm_ostree",
    "flatpak",
    "fwupd",
    "loofi_app",
    "session",
]
SourceAvailability = Literal["available", "partial", "unavailable"]
RecoveryKind = Literal["none", "manual_guidance", "action_center"]
PrivacyLevel = Literal["public", "redacted", "sensitive"]


def stable_event_id(source: str, source_id: str) -> str:
    """Build a non-reversible stable identifier from one source-owned ID."""
    digest = hashlib.sha256(f"{source}\0{source_id}".encode("utf-8")).hexdigest()
    return f"{source}:{digest[:24]}"


def _frozen_facts(values: Mapping[str, Any]) -> Mapping[str, Any]:
    return MappingProxyType(dict(redact_payload(dict(values))))


@dataclass(frozen=True)
class RecoveryCapability:
    """Closed recovery metadata; never an executable vector or callback."""

    kind: RecoveryKind = "none"
    action_id: str | None = None
    parameters: Mapping[str, Any] = field(default_factory=dict)
    guidance: str = ""

    def __post_init__(self) -> None:
        action_id = str(self.action_id or "").strip()
        if self.kind == "action_center" and not action_id:
            raise ValueError("Action Center recovery requires a registered action ID.")
        if self.kind != "action_center" and action_id:
            raise ValueError("Only Action Center recovery may carry an action ID.")
        if self.kind != "action_center" and self.parameters:
            raise ValueError("Only Action Center recovery may carry parameters.")
        object.__setattr__(self, "action_id", action_id or None)
        object.__setattr__(self, "parameters", _frozen_facts(self.parameters))
        object.__setattr__(self, "guidance", redact_text(self.guidance, limit=500))

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "action_id": self.action_id,
            "parameters": dict(self.parameters),
            "guidance": self.guidance,
        }


@dataclass(frozen=True)
class ChangeEvent:
    """One normalized, inert change record from a trusted local source."""

    event_id: str
    source: ChangeSource
    occurred_at: float
    actor_class: str
    summary: str
    resources: tuple[str, ...] = ()
    before_facts: Mapping[str, Any] = field(default_factory=dict)
    after_facts: Mapping[str, Any] = field(default_factory=dict)
    state: str = "recorded"
    reboot_required: bool = False
    correlation_ids: tuple[str, ...] = ()
    privacy_level: PrivacyLevel = "redacted"
    recovery: RecoveryCapability = field(default_factory=RecoveryCapability)

    def __post_init__(self) -> None:
        if not self.event_id or len(self.event_id) > 160:
            raise ValueError("Change events require a bounded event ID.")
        if self.occurred_at < 0:
            raise ValueError("Change event timestamp cannot be negative.")
        resources = tuple(
            dict.fromkeys(
                redact_text(str(resource), limit=160)
                for resource in self.resources[:32]
                if str(resource).strip()
            )
        )
        correlations = tuple(
            dict.fromkeys(str(item)[:160] for item in self.correlation_ids[:32])
        )
        object.__setattr__(self, "actor_class", str(self.actor_class)[:64])
        object.__setattr__(self, "summary", redact_text(self.summary, limit=500))
        object.__setattr__(self, "resources", resources)
        object.__setattr__(self, "before_facts", _frozen_facts(self.before_facts))
        object.__setattr__(self, "after_facts", _frozen_facts(self.after_facts))
        object.__setattr__(self, "state", str(self.state)[:64])
        object.__setattr__(self, "correlation_ids", correlations)

    def with_correlations(self, values: tuple[str, ...]) -> "ChangeEvent":
        return replace(self, correlation_ids=values)

    def to_dict(self) -> dict[str, Any]:
        return {
            "event_id": self.event_id,
            "source": self.source,
            "occurred_at": self.occurred_at,
            "actor_class": self.actor_class,
            "summary": self.summary,
            "resources": list(self.resources),
            "before_facts": dict(self.before_facts),
            "after_facts": dict(self.after_facts),
            "state": self.state,
            "reboot_required": self.reboot_required,
            "correlation_ids": list(self.correlation_ids),
            "privacy_level": self.privacy_level,
            "recovery": self.recovery.to_dict(),
        }


@dataclass(frozen=True)
class ChangeSourceStatus:
    source: ChangeSource
    availability: SourceAvailability
    collected_at: float
    error_code: str = ""
    message: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "source": self.source,
            "availability": self.availability,
            "collected_at": self.collected_at,
            "error_code": self.error_code,
            "message": redact_text(self.message, limit=300),
        }


@dataclass(frozen=True)
class ChangeJournalSnapshot:
    events: tuple[ChangeEvent, ...]
    sources: tuple[ChangeSourceStatus, ...]
    generated_at: float
    truncated: bool = False
    schema: str = CHANGE_JOURNAL_SCHEMA

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": self.schema,
            "generated_at": self.generated_at,
            "truncated": self.truncated,
            "events": [event.to_dict() for event in self.events],
            "sources": [source.to_dict() for source in self.sources],
        }
