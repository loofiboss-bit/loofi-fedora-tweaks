"""Curated v29 task catalog and capability-aware discovery.

The catalog is the product-facing projection of the existing audited action
definitions.  It deliberately contains no command vectors or executable
callbacks.  The operation controller owns execution; this module only answers
which user-facing tasks should be discoverable, runnable, or presented as
safe guidance for the current platform.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Sequence, cast

from core.catalog_models import CapabilityState, FedoraVariant

from .contracts import (
    RebootPolicy,
    TaskArea,
    TaskDescriptor,
    TaskExecutionMode,
    TaskParameter,
    TaskStep,
)
from .profiles import TuneProfile, all_tune_profiles


ALL_VARIANTS = frozenset({FedoraVariant.TRADITIONAL, FedoraVariant.ATOMIC})
TRADITIONAL_VARIANT = frozenset({FedoraVariant.TRADITIONAL})
ATOMIC_VARIANT = frozenset({FedoraVariant.ATOMIC})


@dataclass(frozen=True)
class TaskContext:
    """Immutable host facts used by task visibility and capability policy."""

    variant: FedoraVariant = FedoraVariant.UNKNOWN
    capabilities: frozenset[str] = frozenset()
    pending_reboot: bool | None = None
    online: bool | None = None

    @classmethod
    def from_platform_profile(cls, profile: object) -> "TaskContext":
        """Build context from the canonical immutable ``PlatformProfile``.

        Unknown and bootc backends remain unknown here.  A task cannot become
        runnable merely because a legacy-looking attribute is present on a
        test double or plugin object.
        """

        from core.platform.profile import DeploymentBackend

        raw_backend = getattr(profile, "deployment_backend", DeploymentBackend.UNKNOWN)
        raw_backend = getattr(raw_backend, "value", raw_backend)
        try:
            backend = DeploymentBackend("dnf5" if raw_backend == "dnf" else raw_backend)
        except (TypeError, ValueError):
            backend = DeploymentBackend.UNKNOWN
        raw_atomic = bool(getattr(profile, "is_atomic", False))
        if backend is DeploymentBackend.DNF5 and not raw_atomic:
            variant = FedoraVariant.TRADITIONAL
        elif backend is DeploymentBackend.RPM_OSTREE and raw_atomic:
            variant = FedoraVariant.ATOMIC
        else:
            variant = FedoraVariant.UNKNOWN

        capabilities: set[str] = set()
        if backend is DeploymentBackend.DNF5:
            capabilities.add("dnf5")
        elif backend is DeploymentBackend.RPM_OSTREE:
            capabilities.add("rpm-ostree")
        elif backend is DeploymentBackend.BOOTC:
            capabilities.add("bootc")
        desktop = getattr(getattr(profile, "desktop", None), "value", getattr(profile, "desktop", "unknown"))
        session = getattr(
            getattr(profile, "session_type", None),
            "value",
            getattr(profile, "session_type", "unknown"),
        )
        if desktop and desktop != "unknown":
            capabilities.add(f"desktop:{desktop}")
        if session and session != "unknown":
            capabilities.add(f"session:{session}")
        if bool(getattr(profile, "is_fedora", False)) and backend is not DeploymentBackend.UNKNOWN:
            capabilities.add("fedora")
        return cls(
            variant=variant,
            capabilities=frozenset(capabilities),
            pending_reboot=getattr(profile, "reboot_pending", None),
        )

    @classmethod
    def from_navigation_context(cls, context: object) -> "TaskContext":
        """Adapt the existing navigation context without importing Qt/UI."""

        variant = getattr(context, "fedora_variant", FedoraVariant.UNKNOWN)
        if not isinstance(variant, FedoraVariant):
            try:
                variant = FedoraVariant(str(getattr(variant, "value", variant)))
            except (TypeError, ValueError):
                variant = FedoraVariant.UNKNOWN
        return cls(
            variant=variant,
            capabilities=frozenset(str(item) for item in getattr(context, "capabilities", ())),
        )


@dataclass(frozen=True)
class TaskEligibility:
    """Presentation outcome for one task under a host context."""

    task: TaskDescriptor
    state: CapabilityState
    reason: str
    missing_capabilities: frozenset[str] = frozenset()

    @property
    def available(self) -> bool:
        # Guidance is available as a safe instruction surface even though it
        # is deliberately not runnable by Loofi.
        return self.state in {
            CapabilityState.SUPPORTED,
            CapabilityState.READ_ONLY,
            CapabilityState.NATIVE_HANDOFF,
            CapabilityState.MANUAL_ONLY,
        }

    @property
    def runnable(self) -> bool:
        return self.state is CapabilityState.SUPPORTED and self.task.executable

    @property
    def status(self) -> str:
        return self.state.value

    def to_dict(self) -> dict[str, Any]:
        return {
            "task": self.task.to_dict(),
            "state": self.state.value,
            "status": self.state.value,
            "reason": self.reason,
            "missing_capabilities": sorted(self.missing_capabilities),
        }


@dataclass(frozen=True)
class TaskSearchResult:
    """Navigation-safe search projection with no executable callback."""

    task: TaskDescriptor
    score: int
    eligibility: TaskEligibility

    @property
    def id(self) -> str:
        return self.task.id

    @property
    def label(self) -> str:
        return self.task.title

    @property
    def route_id(self) -> str:
        return self.task.route_id

    @property
    def manual_only(self) -> bool:
        return self.task.manual_only

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "label": self.label,
            "route_id": self.route_id,
            "score": self.score,
            "manual_only": self.manual_only,
            "eligibility": self.eligibility.to_dict(),
        }


def _step(task_id: str, phase: str, title: str, description: str, *, automated: bool = True) -> TaskStep:
    return TaskStep(
        id=f"{task_id}:{phase}",
        title=title,
        description=description,
        automated=automated,
    )


def _parameters(schema: Mapping[str, Mapping[str, Any]] | None = None) -> tuple[TaskParameter, ...]:
    return tuple(
        TaskParameter(
            name=str(name),
            type=str(definition.get("type", "string")),
            description=str(definition.get("description", "")),
            required=bool(definition.get("required", False)),
            default=definition.get("default"),
        )
        for name, definition in (schema or {}).items()
    )


def _descriptor(
    *,
    task_id: str,
    title: str,
    description: str,
    area: TaskArea,
    route_id: str,
    action_id: str | None = None,
    bundle_id: str | None = None,
    risk: str = "low",
    variants: frozenset[FedoraVariant] = ALL_VARIANTS,
    capabilities: frozenset[str] = frozenset(),
    mode: TaskExecutionMode = TaskExecutionMode.EXECUTE,
    status: str = "available",
    availability: CapabilityState = CapabilityState.SUPPORTED,
    goal: str = "",
    group: str = "",
    icon: str = "",
    keywords: tuple[str, ...] = (),
    parameter_schema: Mapping[str, Mapping[str, Any]] | None = None,
    profile_id: str | None = None,
    manual_guidance: str = "",
    handoff_route_id: str | None = None,
    reboot_policy: RebootPolicy = "none",
    profile_eligible: bool = False,
    order: int = 100,
) -> TaskDescriptor:
    return TaskDescriptor(
        id=task_id,
        title=title,
        description=description,
        goal=goal or description,
        area=area,
        route_id=route_id,
        group=group,
        icon=icon,
        keywords=keywords,
        action_id=action_id,
        bundle_id=bundle_id,
        availability=availability,
        risk=risk,  # type: ignore[arg-type]
        status=status,  # type: ignore[arg-type]
        execution_mode=mode,
        parameters=_parameters(parameter_schema),
        required_capabilities=capabilities,
        supported_variants=variants,
        preflight=(_step(task_id, "preflight", "Check", "Confirm the host and task inputs are still eligible."),),
        verification=(_step(task_id, "verification", "Verify", "Verify the resulting state independently after the operation."),),
        recovery=(
            _step(
                task_id,
                "recovery",
                "Recover",
                manual_guidance or "Review the Activity record and follow the documented recovery guidance.",
                automated=False,
            ),
        ),
        manual_guidance=manual_guidance,
        handoff_route_id=handoff_route_id,
        reboot_policy=reboot_policy,
        profile_eligible=profile_eligible,
        order=order,
        metadata={"profile_id": profile_id} if profile_id else {},
    )


def _default_descriptors() -> tuple[TaskDescriptor, ...]:
    """Return the curated first-party task surfaces."""

    return (
        _descriptor(
            task_id="home:status",
            title="Review Fedora status",
            description="See the current Fedora profile, update status, and recommended next step.",
            area=TaskArea.HOME,
            route_id="home",
            mode=TaskExecutionMode.READ_ONLY,
            group="Status",
            icon="home",
            keywords=("home", "status", "profile", "overview"),
            order=0,
        ),
        _descriptor(
            task_id="install:applications",
            title="Install applications",
            description="Find trusted Fedora RPM and Flatpak applications, review the selection, and install them.",
            area=TaskArea.INSTALL,
            route_id="install",
            action_id="install-application",
            group="Applications",
            icon="install",
            keywords=("install", "apps", "applications", "rpm", "flatpak"),
            parameter_schema={
                "source": {"type": "string", "required": True},
                "package_id": {"type": "string", "required": True},
            },
            order=10,
        ),
        _descriptor(
            task_id="install:flatpaks",
            title="Install Flatpak applications",
            description="Browse and install GUI applications from the reviewed Flatpak catalog.",
            area=TaskArea.INSTALL,
            route_id="install",
            action_id="install-application",
            group="Applications",
            icon="packages-software",
            keywords=("flatpak", "flathub", "apps", "install"),
            parameter_schema={
                "source": {"type": "string", "required": True, "default": "flatpak"},
                "package_id": {"type": "string", "required": True},
            },
            order=20,
        ),
        _descriptor(
            task_id="install:repositories",
            title="Review software sources",
            description="Review Fedora, Flatpak, and third-party repository guidance before adding a trust source.",
            area=TaskArea.INSTALL,
            route_id="install",
            action_id="enable-rpm-fusion",
            group="Sources",
            icon="packages-software",
            keywords=("repositories", "repos", "rpm fusion", "flathub", "copr"),
            mode=TaskExecutionMode.GUIDANCE,
            availability=CapabilityState.MANUAL_ONLY,
            status="manual_only",
            manual_guidance="Open the repository instructions, verify the URL and signing metadata, then return to Install.",
            order=30,
        ),
        _descriptor(
            task_id="tune:storage-trim",
            title="Trim supported storage",
            description="Run the verified low-risk storage trim operation for supported filesystems.",
            area=TaskArea.TUNE,
            route_id="tune",
            action_id="fstrim-all",
            group="Storage",
            icon="storage-disk",
            keywords=("tune", "storage", "trim", "ssd", "discard"),
            profile_eligible=True,
            order=10,
        ),
        _descriptor(
            task_id="tune:package-cache",
            title="Clean package metadata cache",
            description="Clear Traditional Fedora package metadata and verify repository health.",
            area=TaskArea.TUNE,
            route_id="tune",
            action_id="dnf-clean-all",
            variants=TRADITIONAL_VARIANT,
            capabilities=frozenset({"dnf5"}),
            group="Packages",
            icon="packages-software",
            keywords=("tune", "cleanup", "cache", "dnf", "packages"),
            profile_eligible=True,
            order=20,
        ),
        _descriptor(
            task_id="tune:desktop",
            title="Review desktop settings",
            description="Open the native desktop settings for appearance and behavior changes.",
            area=TaskArea.TUNE,
            route_id="tune",
            group="Desktop",
            icon="settings",
            keywords=("tune", "desktop", "kde", "gnome", "appearance", "settings"),
            mode=TaskExecutionMode.HANDOFF,
            availability=CapabilityState.NATIVE_HANDOFF,
            status="available",
            manual_guidance="Use the native desktop settings to review and apply the selected appearance or behavior change.",
            handoff_route_id="settings:appearance",
            order=30,
        ),
        _descriptor(
            task_id="fix:system-slow",
            title="Diagnose a slow system",
            description="Collect the bounded system-slow evidence profile and review findings before choosing a repair.",
            area=TaskArea.FIX,
            route_id="fix",
            group="Performance",
            icon="hardware-performance",
            keywords=("fix", "slow", "performance", "diagnose", "system"),
            mode=TaskExecutionMode.READ_ONLY,
            profile_id="system_slow",
            order=10,
        ),
        _descriptor(
            task_id="fix:updates-failed",
            title="Diagnose failed updates",
            description="Collect the closed update-failure profile and review evidence before retrying or repairing.",
            area=TaskArea.FIX,
            route_id="fix",
            group="Updates",
            icon="update",
            keywords=("fix", "updates", "failed", "package manager", "deployment"),
            mode=TaskExecutionMode.READ_ONLY,
            profile_id="updates_failed",
            order=20,
        ),
        _descriptor(
            task_id="fix:application-failed",
            title="Diagnose an application that will not start",
            description="Collect application and Activity evidence before offering a targeted repair.",
            area=TaskArea.FIX,
            route_id="fix",
            group="Applications",
            icon="diagnostics",
            keywords=("fix", "application", "app", "start", "crash"),
            mode=TaskExecutionMode.READ_ONLY,
            parameter_schema={"application_id": {"type": "string", "required": True}},
            profile_id="application_failed",
            order=30,
        ),
        _descriptor(
            task_id="fix:network",
            title="Diagnose a network problem",
            description="Collect network and DNS evidence, then open the native settings when a manual change is needed.",
            area=TaskArea.FIX,
            route_id="fix",
            group="Network",
            icon="network-connectivity",
            keywords=("fix", "network", "wifi", "dns", "internet"),
            mode=TaskExecutionMode.HANDOFF,
            availability=CapabilityState.NATIVE_HANDOFF,
            profile_id="network_problem",
            manual_guidance="Review the collected network evidence, then use native Network settings for the change.",
            handoff_route_id="network:connections",
            order=40,
        ),
        _descriptor(
            task_id="fix:storage",
            title="Diagnose low storage",
            description="Measure storage pressure and review reclaimable data before cleanup.",
            area=TaskArea.FIX,
            route_id="fix",
            group="Storage",
            icon="storage-disk",
            keywords=("fix", "storage", "disk", "space", "cleanup"),
            mode=TaskExecutionMode.READ_ONLY,
            profile_id="storage_pressure",
            order=50,
        ),
        _descriptor(
            task_id="fix:boot",
            title="Diagnose boot or deployment problems",
            description="Collect bounded boot, service, reboot, and deployment evidence before recovery.",
            area=TaskArea.FIX,
            route_id="fix",
            group="Boot & recovery",
            icon="restart",
            keywords=("fix", "boot", "kernel", "deployment", "recovery"),
            mode=TaskExecutionMode.READ_ONLY,
            profile_id="boot_or_deployment",
            order=60,
        ),
        _descriptor(
            task_id="update:overview",
            title="Review available updates",
            description="Check system, Flatpak, and firmware sources and review exact candidates before updating.",
            area=TaskArea.UPDATE,
            route_id="update",
            group="Sources",
            icon="update",
            keywords=("update", "updates", "check", "system", "flatpak", "firmware"),
            mode=TaskExecutionMode.READ_ONLY,
            order=0,
        ),
        _descriptor(
            task_id="update:system",
            title="Update Fedora system",
            description="Prepare the current Fedora package or deployment update without rebooting automatically.",
            area=TaskArea.UPDATE,
            route_id="update",
            action_id="update-fedora-system",
            group="Sources",
            icon="update",
            keywords=("update", "system", "dnf", "rpm ostree", "fedora"),
            risk="medium",
            reboot_policy="required",
            order=10,
        ),
        _descriptor(
            task_id="update:flatpaks",
            title="Update Flatpak applications",
            description="Apply the exact Flatpak updates discovered during the review step.",
            area=TaskArea.UPDATE,
            route_id="update",
            action_id="update-flatpaks",
            group="Sources",
            icon="packages-software",
            keywords=("update", "flatpak", "flathub", "apps"),
            order=20,
        ),
        _descriptor(
            task_id="update:firmware",
            title="Update firmware",
            description="Apply firmware updates reported by fwupd and verify device history.",
            area=TaskArea.UPDATE,
            route_id="update",
            action_id="update-firmware",
            group="Sources",
            icon="hardware-performance",
            keywords=("update", "firmware", "fwupd", "bios"),
            risk="high",
            reboot_policy="may_require",
            order=30,
        ),
        _descriptor(
            task_id="activity:history",
            title="Review Activity & Recovery",
            description="Review in-progress, attention-needed, and historical task results with recovery guidance.",
            area=TaskArea.ACTIVITY,
            route_id="activity",
            group="History",
            icon="history",
            keywords=("activity", "history", "recovery", "changes", "journal"),
            mode=TaskExecutionMode.READ_ONLY,
            order=0,
        ),
    )


_DEFAULT_TASKS = _default_descriptors()


def _area_for_action(action_id: str) -> TaskArea:
    value = str(action_id)
    if value.startswith("update-"):
        return TaskArea.UPDATE
    if value.startswith("install-") or value.startswith("remove-") or value.startswith("enable-flathub"):
        return TaskArea.INSTALL
    if value.startswith(("restart-", "restore-", "recover-", "rollback-")):
        return TaskArea.FIX
    if value.startswith(("configure-", "set-", "apply-", "disable-", "allow-", "block-", "start-", "enroll-", "generate-")):
        return TaskArea.TUNE
    return TaskArea.ACTIVITY


def _guidance_for_action(definition: object) -> TaskDescriptor:
    """Project one manual-only ActionDefinition into safe guidance metadata."""

    action_id = str(getattr(definition, "id", ""))
    title = str(getattr(definition, "title", action_id))
    description = str(getattr(definition, "description", "This operation remains guided manual work."))
    recovery = str(getattr(definition, "recovery_guidance", "Review the action manually before applying it."))
    supported: frozenset[FedoraVariant] = frozenset()
    for raw_variant in getattr(definition, "supported_variants", ("traditional", "atomic")):
        try:
            supported = supported | frozenset({FedoraVariant(str(getattr(raw_variant, "value", raw_variant)))})
        except (TypeError, ValueError):
            continue
    if not supported:
        supported = ALL_VARIANTS
    risk = str(getattr(getattr(definition, "risk_level", "medium"), "value", getattr(definition, "risk_level", "medium")))
    mode = TaskExecutionMode.GUIDANCE
    area = _area_for_action(action_id)
    task_id = f"guidance:{action_id}"
    return _descriptor(
        task_id=task_id,
        title=title,
        description=description,
        area=area,
        route_id=area.value,
        action_id=action_id,
        risk=risk,
        variants=frozenset(supported),
        mode=mode,
        availability=CapabilityState.MANUAL_ONLY,
        status="manual_only",
        group="Guidance",
        icon="info",
        keywords=(action_id, title, description),
        parameter_schema=getattr(definition, "parameter_schema", {}),
        manual_guidance=recovery,
        order=900,
    )


def _action_guidance_tasks() -> tuple[TaskDescriptor, ...]:
    try:
        from core.actions.catalog import ActionCatalog

        definitions = ActionCatalog().list()
    except (ImportError, OSError, RuntimeError, TypeError, ValueError):
        return ()
    return tuple(
        _guidance_for_action(definition)
        for definition in definitions
        if getattr(definition, "operation_class", "host") == "manual_only"
    )


class TaskCatalog:
    """Immutable-in-practice collection of v29 task descriptors."""

    def __init__(
        self,
        descriptors: Sequence[TaskDescriptor] | None = None,
        *,
        include_action_guidance: bool = True,
    ) -> None:
        if descriptors is None:
            selected = list(_DEFAULT_TASKS)
            if include_action_guidance:
                selected.extend(_action_guidance_tasks())
        else:
            selected = list(descriptors)
        by_id: dict[str, TaskDescriptor] = {}
        for descriptor in selected:
            if not isinstance(descriptor, TaskDescriptor):
                raise TypeError("TaskCatalog descriptors must be TaskDescriptor values.")
            if descriptor.id in by_id:
                raise ValueError(f"Duplicate task descriptor: {descriptor.id}")
            by_id[descriptor.id] = descriptor
        self._descriptors = tuple(sorted(by_id.values(), key=lambda item: (cast(TaskArea, item.area).value, item.order, item.id)))
        self._by_id = by_id

    def all(self) -> tuple[TaskDescriptor, ...]:
        return self._descriptors

    def list(self) -> tuple[TaskDescriptor, ...]:
        return self.all()

    def get(self, task_id: str) -> TaskDescriptor | None:
        return self._by_id.get(str(task_id))

    def resolve(self, task_id_or_alias: str) -> TaskDescriptor | None:
        key = " ".join(str(task_id_or_alias or "").strip().casefold().replace("_", " ").split())
        if not key:
            return None
        exact = self._by_id.get(str(task_id_or_alias).strip())
        if exact is not None:
            return exact
        return next(
            (
                descriptor
                for descriptor in self._descriptors
                if key in {
                    descriptor.id.casefold(),
                    descriptor.title.casefold(),
                    descriptor.route_id.casefold(),
                    *(" ".join(item.casefold().replace("_", " ").split()) for item in descriptor.keywords),
                }
            ),
            None,
        )

    def by_area(self, area: TaskArea | str) -> tuple[TaskDescriptor, ...]:
        normalized = area if isinstance(area, TaskArea) else TaskArea(str(area))
        return tuple(item for item in self._descriptors if item.area is normalized)

    def eligibility(self, task: TaskDescriptor | str, context: TaskContext | None = None) -> TaskEligibility:
        descriptor = task if isinstance(task, TaskDescriptor) else self.get(str(task))
        if descriptor is None:
            raise KeyError(f"Unknown task: {task}")
        if not descriptor.discoverable or descriptor.status == "retired":
            return TaskEligibility(descriptor, CapabilityState.UNAVAILABLE, "This task is not discoverable.")
        if descriptor.manual_only:
            return TaskEligibility(descriptor, CapabilityState.MANUAL_ONLY, "This task is available as guidance only.")
        if descriptor.execution_mode is TaskExecutionMode.HANDOFF:
            return TaskEligibility(descriptor, CapabilityState.NATIVE_HANDOFF, "Continue in the native system settings.")
        if descriptor.execution_mode is TaskExecutionMode.READ_ONLY:
            # Read-only diagnostics and Activity remain safe even when package
            # mutation capabilities are unknown, unless they declare a
            # concrete missing capability.
            if context is None:
                return TaskEligibility(descriptor, CapabilityState.READ_ONLY, "Read-only task.")
            missing = descriptor.required_capabilities - context.capabilities
            if missing:
                return TaskEligibility(
                    descriptor,
                    CapabilityState.UNAVAILABLE,
                    "Required read-only capability is unavailable.",
                    frozenset(missing),
                )
            return TaskEligibility(descriptor, CapabilityState.READ_ONLY, "Read-only task.")
        if context is None:
            # Absence of immutable host facts is not permission to mutate.
            # Callers may still discover the descriptor, but an executable
            # task stays unavailable until a verified PlatformProfile is
            # adapted into TaskContext.
            return TaskEligibility(
                descriptor,
                CapabilityState.UNAVAILABLE,
                "Host capabilities are not verified; execution is blocked.",
            )
        if context.pending_reboot is True and descriptor.reboot_policy != "none":
            return TaskEligibility(descriptor, CapabilityState.PENDING_REBOOT, "Complete the pending reboot before continuing.")
        if context.variant is FedoraVariant.UNKNOWN:
            return TaskEligibility(descriptor, CapabilityState.UNAVAILABLE, "Fedora deployment backend is unknown; execution is blocked.")
        if context.variant not in descriptor.supported_variants:
            return TaskEligibility(descriptor, CapabilityState.UNAVAILABLE, "This task is not supported on the current Fedora variant.")
        missing = descriptor.required_capabilities - context.capabilities
        if missing:
            return TaskEligibility(
                descriptor,
                CapabilityState.UNAVAILABLE,
                "Required capability is unavailable.",
                frozenset(missing),
            )
        return TaskEligibility(descriptor, cast(CapabilityState, descriptor.availability), "Task is ready for a fresh preflight.")

    def eligible(self, context: TaskContext | None = None) -> tuple[TaskEligibility, ...]:
        return tuple(self.eligibility(item, context) for item in self._descriptors if item.discoverable)

    def normal(self, context: TaskContext | None = None) -> tuple[TaskDescriptor, ...]:
        """Return normal-surface tasks while omitting manual-only guidance."""
        return tuple(item for item in self._descriptors if not item.manual_only and item.discoverable)

    def runnable(self, context: TaskContext | None = None) -> tuple[TaskDescriptor, ...]:
        """Return only executable tasks allowed by the supplied facts."""
        return tuple(
            item
            for item in self._descriptors
            if item.discoverable and self.eligibility(item, context).runnable
        )

    def guidance(self, context: TaskContext | None = None) -> tuple[TaskDescriptor, ...]:
        """Return manual-only tasks so the UI can offer honest instructions."""
        return tuple(item for item in self._descriptors if item.manual_only and item.discoverable)

    def search(
        self,
        query: str = "",
        *,
        area: TaskArea | str | None = None,
        context: TaskContext | None = None,
        include_guidance: bool = True,
        include_unavailable: bool = True,
        limit: int | None = None,
    ) -> tuple[TaskDescriptor, ...]:
        """Search by user goal, title, route, and keywords.

        Search is token based and order independent.  Guidance is included by
        default, but a caller building a runnable normal view can disable it.
        """

        normalized = " ".join(str(query or "").casefold().split())
        candidates = self._descriptors
        if area is not None:
            normalized_area = area if isinstance(area, TaskArea) else TaskArea(str(area))
            candidates = tuple(item for item in candidates if item.area is normalized_area)
        scored: list[tuple[int, TaskDescriptor]] = []
        for item in candidates:
            if not item.discoverable or (item.manual_only and not include_guidance):
                continue
            eligibility = self.eligibility(item, context)
            if not include_unavailable and eligibility.state is CapabilityState.UNAVAILABLE:
                continue
            fields = (
                item.id,
                item.title,
                item.goal,
                item.description,
                item.route_id,
                item.group,
                *item.keywords,
            )
            field_text = tuple(value.casefold() for value in fields)
            tokens = tuple(token for token in normalized.split() if token)
            if tokens and not all(any(token in field for field in field_text) for token in tokens):
                continue
            score = 1
            if normalized:
                # Rank from token hits rather than the raw query phrase so
                # ``flatpak install`` and ``install flatpak`` are equivalent.
                tokens = tuple(token for token in normalized.split() if token)
                title = item.title.casefold()
                goal = item.goal.casefold()
                description = item.description.casefold()
                score += sum(50 if token in title else 30 if token in goal else 20 if token in description else 10 for token in tokens)
                if all(token in title for token in tokens):
                    score += 20
            if item.manual_only:
                score -= 2
            scored.append((score, item))
        scored.sort(key=lambda pair: (-pair[0], pair[1].order, pair[1].id))
        results = tuple(item for _score, item in scored)
        return results if limit is None else results[: max(0, int(limit))]

    def search_results(
        self,
        query: str = "",
        *,
        area: TaskArea | str | None = None,
        context: TaskContext | None = None,
        include_guidance: bool = True,
        include_unavailable: bool = True,
        limit: int | None = None,
    ) -> tuple[TaskSearchResult, ...]:
        descriptors = self.search(
            query,
            area=area,
            context=context,
            include_guidance=include_guidance,
            include_unavailable=include_unavailable,
            limit=limit,
        )
        normalized = " ".join(str(query or "").casefold().split())
        output: list[TaskSearchResult] = []
        for descriptor in descriptors:
            score = 1
            if normalized:
                tokens = tuple(token for token in normalized.split() if token)
                title = descriptor.title.casefold()
                goal = descriptor.goal.casefold()
                description = descriptor.description.casefold()
                score += sum(
                    50 if token in title else 30 if token in goal else 20 if token in description else 10
                    for token in tokens
                )
                if all(token in title for token in tokens):
                    score += 20
            output.append(TaskSearchResult(descriptor, score, self.eligibility(descriptor, context)))
        return tuple(output)

    def profiles(self) -> tuple[TuneProfile, ...]:
        """Return presets whose IDs are validated against this catalog."""
        profiles: list[TuneProfile] = []
        for profile in all_tune_profiles():
            missing = [task_id for task_id in profile.task_ids if self.get(task_id) is None]
            ineligible: list[str] = []
            for task_id in profile.task_ids:
                task = self.get(task_id)
                if task is not None and not task.profile_eligible:
                    ineligible.append(task_id)
            if missing or ineligible:
                continue
            profiles.append(profile)
        return tuple(profiles)


def all_tasks() -> tuple[TaskDescriptor, ...]:
    return TaskCatalog().all()


def get_task(task_id: str) -> TaskDescriptor | None:
    return TaskCatalog().get(task_id)


def search_tasks(query: str = "", **kwargs: Any) -> tuple[TaskDescriptor, ...]:
    return TaskCatalog().search(query, **kwargs)


def validate_task_catalog(catalog: TaskCatalog | None = None) -> list[str]:
    """Return structural contract errors for CI and release gates."""

    selected = catalog or TaskCatalog()
    errors: list[str] = []
    ids = [item.id for item in selected.all()]
    for item in selected.all():
        if item.execution_mode is TaskExecutionMode.EXECUTE and not item.action_id and not item.bundle_id:
            errors.append(f"task {item.id} has no execution reference")
        if item.manual_only and item.executable:
            errors.append(f"manual task {item.id} is executable")
        if item.status != "retired" and (not item.preflight or not item.verification or not item.recovery):
            errors.append(f"task {item.id} lacks lifecycle metadata")
        if item.profile_eligible and (item.risk == "high" or item.manual_only):
            errors.append(f"profile-eligible task {item.id} violates profile safety policy")
    if len(ids) != len(set(ids)):
        errors.append("task IDs are not unique")
    return errors


__all__ = [
    "ALL_VARIANTS",
    "ATOMIC_VARIANT",
    "TRADITIONAL_VARIANT",
    "TaskCatalog",
    "TaskContext",
    "TaskEligibility",
    "TaskSearchResult",
    "all_tasks",
    "get_task",
    "search_tasks",
    "validate_task_catalog",
]
