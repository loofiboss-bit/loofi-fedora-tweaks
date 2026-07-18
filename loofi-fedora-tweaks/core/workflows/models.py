"""Data-only models for v15 workflow presentation and navigation."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal, Mapping

WorkflowState = Literal["good", "attention", "critical", "unknown"]
RiskLevel = Literal["low", "medium", "high"]


@dataclass(frozen=True)
class ActionCenterLink:
    """Navigation-only handoff to an existing v14 Action Center definition."""

    route_id: str
    action_id: str
    label: str
    parameters: Mapping[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class ProcessPressure:
    """Bounded process evidence included in a slow-system snapshot."""

    name: str
    pid: int
    cpu_percent: float
    memory_percent: float


@dataclass(frozen=True)
class SlowSystemSnapshot:
    """Read-only facts used to explain likely system pressure."""

    cpu_percent: float | None
    memory_percent: float | None
    storage_percent: float | None
    io_wait_percent: float | None
    top_processes: tuple[ProcessPressure, ...] = ()
    failed_services: tuple[str, ...] = ()
    recurring_signals: tuple[str, ...] = ()


@dataclass(frozen=True)
class SlowSystemSummary:
    """Plain-language slow-system result with safe navigation only."""

    state: WorkflowState
    bottleneck: str
    explanation: str
    next_steps: tuple[str, ...]
    snapshot: SlowSystemSnapshot
    action_center_link: ActionCenterLink | None = None


@dataclass(frozen=True)
class ReclaimCategory:
    """One previewable reclaim category; execution stays in its trusted owner."""

    id: str
    title: str
    estimated_bytes: int | None
    risk: RiskLevel
    selected_by_default: bool
    guidance: str
    action_center_link: ActionCenterLink | None = None
    manual_only: bool = False


@dataclass(frozen=True)
class ReclaimAnalysis:
    """Read-only reclaim preview for Traditional or Atomic Fedora."""

    atomic: bool
    categories: tuple[ReclaimCategory, ...]

    @property
    def estimated_selected_bytes(self) -> int:
        return sum(
            category.estimated_bytes or 0
            for category in self.categories
            if category.selected_by_default
        )


@dataclass(frozen=True)
class WorkflowDefinition:
    """Canonical name and preferred route for one v15 workflow."""

    id: str
    title: str
    preferred_route_id: str
    aliases: tuple[str, ...] = ()
