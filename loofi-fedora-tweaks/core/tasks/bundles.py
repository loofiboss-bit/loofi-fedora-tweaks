"""Versioned task bundle contracts used by Install and Tune review flows.

Bundles describe a reviewed change set.  They do not contain commands and do
not execute anything themselves; the operation controller resolves each item
through the audited action catalog after the user confirms the review.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any, Literal, Mapping


BUNDLE_SCHEMA_VERSION = 1
BundleFailurePolicy = Literal["continue", "stop"]


def _required_text(value: object, field_name: str) -> str:
    text = str(value).strip()
    if not text:
        raise ValueError(f"{field_name} must not be empty.")
    if len(text) > 2000:
        raise ValueError(f"{field_name} is too long.")
    return text


@dataclass(frozen=True)
class TaskBundle:
    """A user-reviewed ordered collection of task IDs.

    ``continue`` is appropriate for independent application installs: one
    failed app must not hide the result of the other selected apps.  ``stop``
    is appropriate for ordered tuning changes where later steps depend on the
    earlier state.  Automatic retry, rollback, and reboot are intentionally
    represented as immutable false policy values.
    """

    id: str
    title: str
    description: str
    task_ids: tuple[str, ...]
    failure_policy: BundleFailurePolicy = "continue"
    version: int = BUNDLE_SCHEMA_VERSION
    review_required: bool = True
    automatic_retry: bool = False
    automatic_rollback: bool = False
    automatic_reboot: bool = False
    metadata: Mapping[str, Any] = field(default_factory=dict, repr=False, compare=False)

    def __post_init__(self) -> None:
        _required_text(self.id, "bundle id")
        _required_text(self.title, "bundle title")
        _required_text(self.description, "bundle description")
        if self.version != BUNDLE_SCHEMA_VERSION:
            raise ValueError(f"Unsupported task bundle schema: {self.version}")
        if self.failure_policy not in {"continue", "stop"}:
            raise ValueError(f"Invalid bundle failure policy: {self.failure_policy}")
        task_ids = tuple(str(item).strip() for item in self.task_ids if str(item).strip())
        if not task_ids:
            raise ValueError("A task bundle must contain at least one task.")
        if len(task_ids) != len(set(task_ids)):
            raise ValueError(f"Bundle {self.id} contains duplicate task IDs.")
        object.__setattr__(self, "task_ids", task_ids)
        object.__setattr__(self, "metadata", MappingProxyType(dict(self.metadata)))
        if self.automatic_retry or self.automatic_rollback or self.automatic_reboot:
            raise ValueError("Task bundles cannot enable automatic retry, rollback, or reboot.")

    @property
    def continue_on_error(self) -> bool:
        return self.failure_policy == "continue"

    @property
    def ordered(self) -> bool:
        return True

    @property
    def item_ids(self) -> tuple[str, ...]:
        """Compatibility alias for callers that call bundle items."""
        return self.task_ids

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.version,
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "task_ids": list(self.task_ids),
            "item_ids": list(self.task_ids),
            "failure_policy": self.failure_policy,
            "review_required": self.review_required,
            "automatic_retry": False,
            "automatic_rollback": False,
            "automatic_reboot": False,
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "TaskBundle":
        task_ids = payload.get("task_ids", payload.get("item_ids", ()))
        if not isinstance(task_ids, (list, tuple)):
            raise ValueError("Task bundle task_ids must be a collection.")
        return cls(
            id=str(payload.get("id", "")),
            title=str(payload.get("title", "")),
            description=str(payload.get("description", "")),
            task_ids=tuple(str(item) for item in task_ids),
            failure_policy=str(payload.get("failure_policy", "continue")),  # type: ignore[arg-type]
            version=int(payload.get("schema_version", BUNDLE_SCHEMA_VERSION)),
            review_required=bool(payload.get("review_required", True)),
            automatic_retry=bool(payload.get("automatic_retry", False)),
            automatic_rollback=bool(payload.get("automatic_rollback", False)),
            automatic_reboot=bool(payload.get("automatic_reboot", False)),
            metadata=payload.get("metadata", {}) if isinstance(payload.get("metadata", {}), Mapping) else {},
        )


# Explicit aliases keep the contract discoverable for callers using either
# "descriptor" or "selection" terminology.
TaskBundleDescriptor = TaskBundle
ChangeSet = TaskBundle


__all__ = [
    "BUNDLE_SCHEMA_VERSION",
    "BundleFailurePolicy",
    "ChangeSet",
    "TaskBundle",
    "TaskBundleDescriptor",
]
