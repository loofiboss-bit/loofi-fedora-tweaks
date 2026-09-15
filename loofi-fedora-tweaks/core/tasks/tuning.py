"""Editable Tune profile selection and bundle construction for v29."""

from __future__ import annotations

from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any, Iterable, Mapping, Sequence

from core.actions.bundles import ActionBundle, ActionBundleItem
from core.catalog_models import CapabilityState

from .catalog import TaskCatalog, TaskContext, TaskEligibility
from .contracts import TaskDescriptor
from .profiles import TuneProfile, all_tune_profiles


@dataclass(frozen=True)
class TuneSelection:
    """A reviewed, ordered selection of executable Tune tasks."""

    profile: TuneProfile
    tasks: tuple[TaskDescriptor, ...]
    context: TaskContext
    bundle: ActionBundle
    omitted: Mapping[str, str] = field(default_factory=dict, repr=False, compare=False)

    @property
    def task_ids(self) -> tuple[str, ...]:
        return tuple(task.id for task in self.tasks)

    @property
    def count(self) -> int:
        return len(self.tasks)

    @property
    def reboot_required(self) -> bool:
        return any(task.reboot_policy != "none" for task in self.tasks)

    def to_dict(self) -> dict[str, Any]:
        return {
            "profile": self.profile.to_dict(),
            "task_ids": list(self.task_ids),
            "tasks": [task.to_dict() for task in self.tasks],
            "context": {
                "variant": self.context.variant.value,
                "capabilities": sorted(self.context.capabilities),
                "pending_reboot": self.context.pending_reboot,
                "online": self.context.online,
            },
            "bundle": self.bundle.to_dict(),
            "omitted": dict(self.omitted),
            "reboot_required": self.reboot_required,
        }


class TuneCatalog:
    """Resolve safe profile presets against the current immutable context."""

    def __init__(
        self,
        *,
        task_catalog: TaskCatalog | None = None,
        profiles: Sequence[TuneProfile] | None = None,
    ) -> None:
        self.task_catalog = task_catalog or TaskCatalog()
        selected = tuple(profiles or all_tune_profiles())
        by_id: dict[str, TuneProfile] = {}
        for profile in selected:
            if profile.id in by_id:
                raise ValueError(f"Duplicate Tune profile: {profile.id}")
            by_id[profile.id] = profile
        self._profiles = tuple(selected)
        self._profiles_by_id = by_id

    def profiles(self) -> tuple[TuneProfile, ...]:
        return self._profiles

    def get_profile(self, profile_id: str) -> TuneProfile | None:
        return self._profiles_by_id.get(str(profile_id).strip())

    def profile_tasks(
        self,
        profile: TuneProfile | str,
        *,
        context: TaskContext | None = None,
    ) -> tuple[tuple[TaskDescriptor, TaskEligibility], ...]:
        selected = profile if isinstance(profile, TuneProfile) else self.get_profile(str(profile))
        if selected is None:
            raise KeyError(f"Unknown Tune profile: {profile}")
        rows: list[tuple[TaskDescriptor, TaskEligibility]] = []
        for task_id in selected.task_ids:
            task = self.task_catalog.get(task_id)
            if task is None:
                continue
            eligibility = self.task_catalog.eligibility(task, context)
            # Profiles never include read-only, handoff, manual-only, high-risk,
            # or otherwise non-executable operations.
            if not task.profile_eligible or not task.executable or task.risk not in {"none", "low"}:
                continue
            rows.append((task, eligibility))
        return tuple(rows)

    def selectable_tasks(
        self,
        profile: TuneProfile | str,
        *,
        context: TaskContext,
    ) -> tuple[tuple[TaskDescriptor, TaskEligibility], ...]:
        """Return every profile row, including unavailable rows for UI explanation."""

        return self.profile_tasks(profile, context=context)

    def build_selection(
        self,
        profile: TuneProfile | str,
        *,
        context: TaskContext,
        selected_task_ids: Iterable[str] | None = None,
        title: str | None = None,
    ) -> TuneSelection:
        selected_profile = profile if isinstance(profile, TuneProfile) else self.get_profile(str(profile))
        if selected_profile is None:
            raise KeyError(f"Unknown Tune profile: {profile}")
        profile_rows = self.profile_tasks(selected_profile, context=context)
        by_id = {task.id: (task, eligibility) for task, eligibility in profile_rows}
        requested = (
            tuple(selected_profile.task_ids)
            if selected_task_ids is None
            else tuple(str(item).strip() for item in selected_task_ids if str(item).strip())
        )
        if not requested:
            raise ValueError("Select at least one Tune operation.")
        if len(requested) != len(set(requested)):
            raise ValueError("A Tune operation can only be selected once.")

        ordered: list[TaskDescriptor] = []
        omitted: dict[str, str] = {}
        for task_id in requested:
            row = by_id.get(task_id)
            if row is None:
                task = self.task_catalog.get(task_id)
                if task is None:
                    raise ValueError(f"Unknown Tune operation: {task_id}")
                omitted[task_id] = "This operation is not part of the selected safe profile."
                continue
            task, eligibility = row
            if eligibility.state is not CapabilityState.SUPPORTED:
                omitted[task.id] = eligibility.reason
                continue
            ordered.append(task)
        if not ordered:
            details = "; ".join(f"{task_id}: {reason}" for task_id, reason in omitted.items())
            raise ValueError(f"No selected Tune operations are available. {details}".strip())

        items = tuple(
            ActionBundleItem(
                action_id=str(task.action_id or ""),
                title=task.title,
                metadata={"task_id": task.id, "profile_id": selected_profile.id},
            )
            for task in ordered
        )
        bundle = ActionBundle.tune_profile(
            items,
            title=title or selected_profile.title,
            description="Review the ordered low-risk operations before applying the Tune profile.",
            metadata={
                "profile_id": selected_profile.id,
                "profile_version": selected_profile.version,
                "variant": context.variant.value,
                "task_ids": [task.id for task in ordered],
                "omitted": dict(omitted),
            },
        )
        return TuneSelection(selected_profile, tuple(ordered), context, bundle, MappingProxyType(omitted))


def default_tune_catalog() -> TuneCatalog:
    """Return the immutable default Tune catalog facade."""

    return TuneCatalog()


def build_tune_bundle(
    profile: TuneProfile | str,
    *,
    context: TaskContext,
    selected_task_ids: Iterable[str] | None = None,
    catalog: TuneCatalog | None = None,
) -> ActionBundle:
    """Build a stop-on-error ActionBundle without executing it."""

    return (catalog or TuneCatalog()).build_selection(
        profile,
        context=context,
        selected_task_ids=selected_task_ids,
    ).bundle


__all__ = [
    "TuneCatalog",
    "TuneSelection",
    "build_tune_bundle",
    "default_tune_catalog",
]
