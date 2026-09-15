"""Curated Tune profile metadata for the v29 Fedora Utility."""

from __future__ import annotations

from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any, Literal, Mapping

from .bundles import BUNDLE_SCHEMA_VERSION, TaskBundle


PROFILE_SCHEMA_VERSION = 1
TuneLevel = Literal["minimal", "recommended", "power_user"]


@dataclass(frozen=True)
class TuneProfile:
    """An editable, reviewable preset of profile-eligible task IDs."""

    id: str
    title: str
    description: str
    level: TuneLevel
    task_ids: tuple[str, ...]
    version: int = PROFILE_SCHEMA_VERSION
    editable: bool = True
    review_required: bool = True
    failure_policy: Literal["stop"] = "stop"
    automatic_retry: bool = False
    automatic_rollback: bool = False
    automatic_reboot: bool = False
    metadata: Mapping[str, Any] = field(default_factory=dict, repr=False, compare=False)

    def __post_init__(self) -> None:
        for value, field_name in ((self.id, "profile id"), (self.title, "profile title"), (self.description, "profile description")):
            if not str(value).strip():
                raise ValueError(f"{field_name} must not be empty.")
        if self.version != PROFILE_SCHEMA_VERSION:
            raise ValueError(f"Unsupported Tune profile schema: {self.version}")
        if self.level not in {"minimal", "recommended", "power_user"}:
            raise ValueError(f"Invalid Tune profile level: {self.level}")
        if self.failure_policy != "stop":
            raise ValueError("Tune profiles must stop after the first unexpected failure.")
        task_ids = tuple(str(item).strip() for item in self.task_ids if str(item).strip())
        if len(task_ids) != len(set(task_ids)):
            raise ValueError(f"Tune profile {self.id} contains duplicate task IDs.")
        object.__setattr__(self, "task_ids", task_ids)
        object.__setattr__(self, "metadata", MappingProxyType(dict(self.metadata)))
        if self.automatic_retry or self.automatic_rollback or self.automatic_reboot:
            raise ValueError("Tune profiles cannot enable automatic retry, rollback, or reboot.")

    @property
    def item_ids(self) -> tuple[str, ...]:
        return self.task_ids

    @property
    def bundle_id(self) -> str:
        return f"tune-profile:{self.id}"

    def to_bundle(self) -> TaskBundle:
        """Return the corresponding stop-on-error reviewed change set."""
        return TaskBundle(
            id=self.bundle_id,
            title=self.title,
            description=self.description,
            task_ids=self.task_ids,
            failure_policy="stop",
            version=BUNDLE_SCHEMA_VERSION,
            review_required=self.review_required,
            metadata={"profile_id": self.id, "profile_version": self.version},
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.version,
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "level": self.level,
            "task_ids": list(self.task_ids),
            "item_ids": list(self.task_ids),
            "editable": self.editable,
            "review_required": self.review_required,
            "failure_policy": self.failure_policy,
            "automatic_retry": False,
            "automatic_rollback": False,
            "automatic_reboot": False,
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "TuneProfile":
        task_ids = payload.get("task_ids", payload.get("item_ids", ()))
        if not isinstance(task_ids, (list, tuple)):
            raise ValueError("Tune profile task_ids must be a collection.")
        return cls(
            id=str(payload.get("id", "")),
            title=str(payload.get("title", "")),
            description=str(payload.get("description", "")),
            level=str(payload.get("level", "minimal")),  # type: ignore[arg-type]
            task_ids=tuple(str(item) for item in task_ids),
            version=int(payload.get("schema_version", PROFILE_SCHEMA_VERSION)),
            editable=bool(payload.get("editable", True)),
            review_required=bool(payload.get("review_required", True)),
            failure_policy="stop",
            automatic_retry=bool(payload.get("automatic_retry", False)),
            automatic_rollback=bool(payload.get("automatic_rollback", False)),
            automatic_reboot=bool(payload.get("automatic_reboot", False)),
            metadata=payload.get("metadata", {}) if isinstance(payload.get("metadata", {}), Mapping) else {},
        )


ProfileDescriptor = TuneProfile


def default_tune_profiles() -> tuple[TuneProfile, ...]:
    """Return the three product presets.

    The task IDs are resolved by :class:`TaskCatalog`; profile metadata stays
    independent from action callables.  All selected tasks are low-risk,
    implemented, and independently verifiable catalog entries.
    """

    return (
        TuneProfile(
            id="tune:minimal",
            title="Minimal",
            description="A small set of low-risk maintenance checks for a clean Fedora baseline.",
            level="minimal",
            task_ids=("tune:storage-trim",),
        ),
        TuneProfile(
            id="tune:recommended",
            title="Recommended",
            description="The balanced low-risk maintenance set for everyday Fedora use.",
            level="recommended",
            task_ids=("tune:storage-trim", "tune:package-cache"),
        ),
        TuneProfile(
            id="tune:power-user",
            title="Power User",
            description="The full reviewed low-risk tuning set; edit it before applying changes.",
            level="power_user",
            task_ids=("tune:storage-trim", "tune:package-cache"),
        ),
    )


def all_tune_profiles() -> tuple[TuneProfile, ...]:
    return default_tune_profiles()


def get_tune_profile(profile_id: str) -> TuneProfile | None:
    return next((profile for profile in all_tune_profiles() if profile.id == str(profile_id)), None)


__all__ = [
    "PROFILE_SCHEMA_VERSION",
    "ProfileDescriptor",
    "TuneLevel",
    "TuneProfile",
    "all_tune_profiles",
    "default_tune_profiles",
    "get_tune_profile",
]
