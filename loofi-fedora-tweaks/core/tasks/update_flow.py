"""State-driven Update source cards for the v29 utility shell."""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from types import MappingProxyType
from typing import Any, Literal, Mapping, Sequence


UpdateSource = Literal["system", "flatpak", "firmware"]
UpdateStatus = Literal[
    "unchecked",
    "checking",
    "up_to_date",
    "available",
    "stale",
    "missing_tool",
    "unsupported",
    "error",
    "preparing",
    "verifying",
    "awaiting_reboot",
    "succeeded",
    "failed",
    "verification_failed",
]
UpdateButtonLabel = Literal["Check", "Update", "Continue", "Verify"]

UPDATE_SOURCES: tuple[UpdateSource, ...] = ("system", "flatpak", "firmware")


@dataclass(frozen=True)
class UpdateSourceState:
    """Persistable status for one independent update source."""

    source: UpdateSource
    status: UpdateStatus = "unchecked"
    item_count: int = 0
    checked_at: str = ""
    stale: bool = True
    reboot_required: bool = False
    run_id: str = ""
    message: str = ""
    details: tuple[str, ...] = ()
    metadata: Mapping[str, Any] = field(default_factory=dict, repr=False, compare=False)

    def __post_init__(self) -> None:
        if self.source not in UPDATE_SOURCES:
            raise ValueError(f"Unknown update source: {self.source}")
        if self.status not in {
            "unchecked", "checking", "up_to_date", "available", "stale", "missing_tool",
            "unsupported", "error", "preparing", "verifying", "awaiting_reboot", "succeeded",
            "failed", "verification_failed",
        }:
            raise ValueError(f"Unknown update status: {self.status}")
        if not isinstance(self.item_count, int) or isinstance(self.item_count, bool) or self.item_count < 0:
            raise ValueError("Update item_count must be a non-negative integer.")
        object.__setattr__(self, "details", tuple(str(item) for item in self.details if str(item).strip()))
        object.__setattr__(self, "metadata", MappingProxyType(dict(self.metadata)))

    @property
    def has_updates(self) -> bool:
        return self.status in {"available", "stale"} and self.item_count > 0

    @property
    def freshness(self) -> str:
        if self.stale or self.status in {"unchecked", "checking"}:
            return "stale"
        return "fresh"

    def with_status(self, status: UpdateStatus, **changes: Any) -> "UpdateSourceState":
        return replace(self, status=status, **changes)

    def to_dict(self) -> dict[str, Any]:
        return {
            "source": self.source,
            "status": self.status,
            "item_count": self.item_count,
            "checked_at": self.checked_at,
            "stale": self.stale,
            "freshness": self.freshness,
            "reboot_required": self.reboot_required,
            "run_id": self.run_id,
            "message": self.message,
            "details": list(self.details),
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True)
class UpdateCTA:
    """The one primary action exposed for a source card."""

    label: UpdateButtonLabel
    enabled: bool
    action: str
    reason: str = ""

    @property
    def primary(self) -> bool:
        return True

    def to_dict(self) -> dict[str, Any]:
        return {
            "label": self.label,
            "enabled": self.enabled,
            "action": self.action,
            "reason": self.reason,
            "primary": True,
        }


def update_cta(state: UpdateSourceState) -> UpdateCTA:
    """Resolve exactly one state-driven CTA without starting an operation."""

    if state.status == "checking":
        return UpdateCTA("Check", False, "check", "A source check is already running.")
    if state.status == "preparing":
        return UpdateCTA("Update", False, "update", state.message or "An update is already being prepared.")
    if state.status in {"verifying", "verification_failed"}:
        return UpdateCTA("Verify", True, "verify", state.message or "Verify the resulting source state.")
    if state.status == "awaiting_reboot" or state.reboot_required and state.status not in {"unchecked", "checking", "available"}:
        return UpdateCTA("Continue", True, "continue", state.message or "Continue after the required reboot.")
    if state.status == "available" and state.item_count > 0 and not state.stale:
        return UpdateCTA("Update", True, "update", state.message or "Apply the reviewed updates.")
    if state.status == "up_to_date" and not state.stale:
        return UpdateCTA("Check", True, "check", "Check again for newer updates.")
    if state.status in {"unsupported", "missing_tool"}:
        return UpdateCTA("Check", False, "check", state.message or "This source cannot be checked on this system.")
    # Unchecked, stale, error, and an available-but-stale cache all require a
    # fresh check before an update can be offered.
    return UpdateCTA("Check", True, "check", state.message or "Refresh this source before updating.")


def state_driven_cta(state: UpdateSourceState) -> UpdateCTA:
    """Readable alias for UI and CLI adapters."""

    return update_cta(state)


@dataclass(frozen=True)
class UpdateOverviewState:
    """Exactly three independent source cards and their state transitions."""

    sources: tuple[UpdateSourceState, ...] = field(
        default_factory=lambda: tuple(UpdateSourceState(source) for source in UPDATE_SOURCES)
    )

    def __post_init__(self) -> None:
        by_source: dict[str, UpdateSourceState] = {}
        for source in self.sources:
            if source.source in by_source:
                raise ValueError(f"Duplicate update source: {source.source}")
            by_source[source.source] = source
        missing = [source for source in UPDATE_SOURCES if source not in by_source]
        if missing:
            raise ValueError(f"Update overview is missing sources: {', '.join(missing)}")
        object.__setattr__(
            self,
            "sources",
            tuple(by_source[source] for source in UPDATE_SOURCES),
        )

    def source(self, source: UpdateSource | str) -> UpdateSourceState:
        key = str(source)
        return next(item for item in self.sources if item.source == key)

    @classmethod
    def from_snapshot(cls, snapshot: object) -> "UpdateOverviewState":
        """Adapt the existing read-only overview snapshot into source cards."""
        values: dict[str, UpdateSourceState] = {}
        raw_sources = getattr(snapshot, "sources", ())
        raw_values = raw_sources if isinstance(raw_sources, (tuple, list)) else ()
        for raw in raw_values:
            source = str(getattr(raw, "source", "")).strip()
            if source not in UPDATE_SOURCES:
                continue
            raw_status = str(getattr(raw, "status", "unchecked"))
            status_map: dict[str, UpdateStatus] = {
                "available": "available",
                "up_to_date": "up_to_date",
                "error": "error",
                "missing_tool": "missing_tool",
                "unsupported": "unsupported",
            }
            status = status_map.get(raw_status, "unchecked")
            stale = bool(getattr(raw, "stale", True))
            if status == "available" and stale:
                status = "stale"
            items = getattr(raw, "items", ())
            values[source] = UpdateSourceState(
                source=source,  # type: ignore[arg-type]
                status=status,
                item_count=len(items) if isinstance(items, (tuple, list)) else 0,
                checked_at=str(getattr(raw, "checked_at", "") or ""),
                stale=stale,
                reboot_required=bool(getattr(raw, "reboot_required", False)),
                message=str(getattr(raw, "message", "") or getattr(raw, "error_code", "") or ""),
                metadata={"backend": str(getattr(snapshot, "backend", "") or "")},
            )
        return cls(tuple(values.get(source, UpdateSourceState(source)) for source in UPDATE_SOURCES))

    def cta(self, source: UpdateSource | str) -> UpdateCTA:
        return update_cta(self.source(source))

    def replace_source(self, state: UpdateSourceState) -> "UpdateOverviewState":
        return UpdateOverviewState(tuple(state if item.source == state.source else item for item in self.sources))

    def to_dict(self) -> dict[str, Any]:
        return {"sources": [item.to_dict() for item in self.sources]}


def validate_update_overview(state: UpdateOverviewState | Sequence[UpdateSourceState]) -> list[str]:
    """Return contract errors for adapters importing source snapshots."""

    errors: list[str] = []
    values = tuple(state.sources if isinstance(state, UpdateOverviewState) else state)
    if len(values) != len(UPDATE_SOURCES):
        errors.append("update overview must contain exactly system, flatpak, and firmware sources")
    seen = [item.source for item in values]
    if len(seen) != len(set(seen)):
        errors.append("update sources must be unique")
    for source in UPDATE_SOURCES:
        if source not in seen:
            errors.append(f"missing update source: {source}")
    return errors


__all__ = [
    "UPDATE_SOURCES",
    "UpdateButtonLabel",
    "UpdateCTA",
    "UpdateOverviewState",
    "UpdateSource",
    "UpdateSourceState",
    "UpdateStatus",
    "state_driven_cta",
    "update_cta",
    "validate_update_overview",
]
