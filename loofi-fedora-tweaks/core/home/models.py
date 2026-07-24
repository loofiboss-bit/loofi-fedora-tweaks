"""Immutable, UI-independent models for the v15 Home summary."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Literal

HomeOverallState = Literal["good", "attention", "critical", "unknown"]
HomeDataState = Literal["fresh", "stale", "error", "empty"]
HomeFreshnessState = Literal["fresh", "stale", "unavailable"]
HomeCheckState = Literal["completed", "partial", "cancelled", "failed"]
AttentionSeverity = Literal["info", "attention", "critical"]
HomeStatusState = Literal["good", "attention", "critical", "unknown"]
HomeStatusId = Literal["health", "updates", "storage", "recovery"]


@dataclass(frozen=True)
class Recommendation:
    """The single highest-value next step shown on Home."""

    id: str
    kind: str
    title: str
    summary: str
    route_id: str
    severity: AttentionSeverity = "attention"
    count: int = 1


@dataclass(frozen=True)
class AttentionItem:
    """A bounded secondary signal below the primary recommendation."""

    id: str
    title: str
    summary: str
    route_id: str
    severity: AttentionSeverity = "attention"


@dataclass(frozen=True)
class HomeTask:
    """One common, navigation-only task shortcut."""

    id: str
    title: str
    description: str
    route_id: str
    icon_id: str


@dataclass(frozen=True)
class RecentChange:
    """The latest saved activity; Home never mutates or executes its undo."""

    id: str
    description: str
    occurred_at: datetime | None
    undo_available: bool


@dataclass(frozen=True)
class HomeStatus:
    """One truthful status derived from already-saved Home sources."""

    id: HomeStatusId
    title: str
    state: HomeStatusState
    summary: str
    route_id: str


@dataclass(frozen=True)
class HomeSummary:
    """Complete, bounded payload consumed by the canonical Home UI."""

    overall_state: HomeOverallState
    data_state: HomeDataState
    summary: str
    generated_at: datetime
    primary_recommendation: Recommendation | None
    attention_items: tuple[AttentionItem, ...]
    common_tasks: tuple[HomeTask, ...]
    recent_change: RecentChange | None
    source_errors: tuple[str, ...] = ()
    status_items: tuple[HomeStatus, ...] = ()
    last_checked_at: datetime | None = None
    freshness_state: HomeFreshnessState = "unavailable"
    last_check_state: HomeCheckState | None = None
    check_now_available: bool = True

    def __post_init__(self) -> None:
        if len(self.attention_items) > 3:
            raise ValueError("Home may show at most three attention items")
        if len(self.common_tasks) > 4:
            raise ValueError("Home may show at most four common tasks")
        status_ids = tuple(item.id for item in self.status_items)
        if len(status_ids) > 4 or len(set(status_ids)) != len(status_ids):
            raise ValueError("Home status items must contain at most four unique areas")
