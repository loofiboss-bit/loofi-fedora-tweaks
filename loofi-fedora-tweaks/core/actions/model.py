"""Typed Action Center model shared by CLI, UI, and support bundles."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Literal

ActionRisk = Literal["none", "low", "medium", "high"]
ActionState = Literal[
    "planned",
    "ready",
    "needs_review",
    "blocked",
    "running",
    "succeeded",
    "failed",
    "verification_failed",
    "cancelled",
    "manual_only",
]


@dataclass(frozen=True)
class RollbackGuidance:
    """Rollback guidance surfaced before medium/high-risk actions."""

    mechanism: str
    summary: str
    command_preview: list[str] = field(default_factory=list)
    supported: bool = False

    def to_dict(self) -> dict[str, object]:
        return {
            "mechanism": self.mechanism,
            "summary": self.summary,
            "command_preview": list(self.command_preview),
            "supported": self.supported,
        }


@dataclass
class ActionCenterItem:
    """Previewable, queueable action representation."""

    id: str
    title: str
    source: str
    description: str
    risk_level: ActionRisk = "none"
    privilege: str = "none"
    command_preview: list[str] = field(default_factory=list)
    rollback_hint: str = "No rollback guidance is required for this read-only action."
    rollback_guidance: RollbackGuidance | None = None
    manual_only: bool = False
    confirmation_required: bool = False
    verification_command: list[str] = field(default_factory=list)
    state: ActionState = "planned"
    output_summary: str = ""
    verification_result: str = ""
    timestamp: float = field(default_factory=time.time)
    correlation_id: str = ""
    dedupe_key: str = ""
    why_this_matters: str = ""
    safe_next_step: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def privileged(self) -> bool:
        return self.privilege == "pkexec"

    @property
    def executable(self) -> bool:
        return bool(self.command_preview) and not self.manual_only

    def to_dict(self) -> dict[str, object]:
        return {
            "id": self.id,
            "title": self.title,
            "source": self.source,
            "description": self.description,
            "risk_level": self.risk_level,
            "privilege": self.privilege,
            "command_preview": list(self.command_preview),
            "rollback_hint": self.rollback_hint,
            "rollback_guidance": self.rollback_guidance.to_dict() if self.rollback_guidance else None,
            "manual_only": self.manual_only,
            "confirmation_required": self.confirmation_required,
            "verification_command": list(self.verification_command),
            "state": self.state,
            "output_summary": self.output_summary,
            "verification_result": self.verification_result,
            "timestamp": self.timestamp,
            "correlation_id": self.correlation_id or self.id,
            "dedupe_key": self.dedupe_key or self.id,
            "why_this_matters": self.why_this_matters,
            "safe_next_step": self.safe_next_step,
            "metadata": dict(self.metadata),
        }
