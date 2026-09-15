"""PyQt-free product contracts for the v29 Fedora Utility task catalog.

The task catalog is deliberately a product layer, not an execution registry.
It describes what a user can discover, what a task needs from the host, and
how a result is verified or recovered.  Execution authority remains with the
audited Action Center definitions and the v29 operation controller.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from types import MappingProxyType
from typing import Any, Mapping, Literal, cast

from core.catalog_models import CapabilityState, FedoraVariant, RiskLevel


TASK_DESCRIPTOR_SCHEMA_VERSION = 1


class TaskArea(str, Enum):
    """The five primary utility surfaces plus the durable activity surface."""

    HOME = "home"
    INSTALL = "install"
    TUNE = "tune"
    FIX = "fix"
    UPDATE = "update"
    ACTIVITY = "activity"


# ``TaskKind`` is the readable type-alias name used by catalog consumers.
TaskKind = TaskArea


class TaskExecutionMode(str, Enum):
    """How a task is entered from the product surface."""

    EXECUTE = "execute"
    READ_ONLY = "read_only"
    GUIDANCE = "guidance"
    HANDOFF = "handoff"


TaskStatus = Literal[
    "available",
    "blocked",
    "needs_review",
    "in_progress",
    "succeeded",
    "failed",
    "verification_failed",
    "pending_reboot",
    "manual_only",
    "retired",
]

RebootPolicy = Literal["none", "may_require", "required"]


def _non_empty(value: object, field_name: str) -> str:
    text = str(value).strip()
    if not text:
        raise ValueError(f"{field_name} must not be empty.")
    return text


def _bounded_text(value: object, field_name: str, *, maximum: int = 2000) -> str:
    text = str(value).strip()
    if len(text) > maximum:
        raise ValueError(f"{field_name} exceeds the {maximum}-character limit.")
    return text


@dataclass(frozen=True)
class TaskParameter:
    """A bounded, presentation-safe task parameter description.

    This is intentionally compatible with the ``parameter_schema`` shape of
    an ``ActionDefinition`` while keeping callables and command vectors out of
    product metadata.
    """

    name: str
    type: str
    description: str = ""
    required: bool = False
    default: Any = None

    def __post_init__(self) -> None:
        _non_empty(self.name, "parameter name")
        if self.type not in {"string", "integer", "boolean", "object", "array"}:
            raise ValueError(f"Unsupported task parameter type: {self.type}")
        _bounded_text(self.description, "parameter description")

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "name": self.name,
            "type": self.type,
            "description": self.description,
            "required": self.required,
        }
        if self.default is not None:
            payload["default"] = self.default
        return payload

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "TaskParameter":
        return cls(
            name=str(payload.get("name", "")),
            type=str(payload.get("type", "string")),
            description=str(payload.get("description", "")),
            required=bool(payload.get("required", False)),
            default=payload.get("default"),
        )


# A common alias makes the contract pleasant to consume from both the GUI and
# CLI without forcing either surface to know the historical ActionDefinition
# spelling.
ParameterSpec = TaskParameter


@dataclass(frozen=True)
class TaskStep:
    """One human-readable lifecycle step owned by the task definition."""

    id: str
    title: str
    description: str
    automated: bool = True
    required: bool = True

    def __post_init__(self) -> None:
        _non_empty(self.id, "task step id")
        _non_empty(self.title, "task step title")
        _non_empty(self.description, "task step description")
        _bounded_text(self.title, "task step title", maximum=200)
        _bounded_text(self.description, "task step description")

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "automated": self.automated,
            "required": self.required,
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "TaskStep":
        return cls(
            id=str(payload.get("id", "")),
            title=str(payload.get("title", "")),
            description=str(payload.get("description", "")),
            automated=bool(payload.get("automated", True)),
            required=bool(payload.get("required", True)),
        )


# ``TaskCheck`` reads naturally for callers building preflight and
# verification lists; it remains the exact same immutable contract.
TaskCheck = TaskStep


@dataclass(frozen=True)
class TaskDescriptor:
    """Immutable metadata for one user-facing Fedora task.

    A descriptor may point at one audited action or at a versioned bundle.  A
    guidance or handoff descriptor can retain a stable historical action ID,
    but its ``execution_mode`` makes it impossible to mistake it for an
    executable operation.
    """

    id: str
    title: str
    description: str
    area: TaskArea | str
    route_id: str
    goal: str = ""
    group: str = ""
    icon: str = ""
    keywords: tuple[str, ...] = ()
    action_id: str | None = None
    bundle_id: str | None = None
    availability: CapabilityState | str = CapabilityState.SUPPORTED
    risk: RiskLevel = "low"
    status: TaskStatus = "available"
    execution_mode: TaskExecutionMode | str = TaskExecutionMode.EXECUTE
    parameters: tuple[TaskParameter, ...] = ()
    required_capabilities: frozenset[str] = frozenset()
    supported_variants: frozenset[FedoraVariant] = frozenset(
        {FedoraVariant.TRADITIONAL, FedoraVariant.ATOMIC}
    )
    preflight: tuple[TaskStep, ...] = ()
    verification: tuple[TaskStep, ...] = ()
    recovery: tuple[TaskStep, ...] = ()
    manual_guidance: str = ""
    handoff_route_id: str | None = None
    reboot_policy: RebootPolicy = "none"
    discoverable: bool = True
    profile_eligible: bool = False
    order: int = 100
    metadata: Mapping[str, Any] = field(default_factory=dict, repr=False, compare=False)

    def __post_init__(self) -> None:
        _non_empty(self.id, "task id")
        _non_empty(self.title, "task title")
        _non_empty(self.description, "task description")
        _non_empty(self.route_id, "task route id")
        _bounded_text(self.title, "task title", maximum=200)
        _bounded_text(self.description, "task description")
        _bounded_text(self.group, "task group", maximum=120)

        area = self.area if isinstance(self.area, TaskArea) else TaskArea(str(self.area))
        object.__setattr__(self, "area", area)
        availability = (
            self.availability
            if isinstance(self.availability, CapabilityState)
            else CapabilityState(str(self.availability))
        )
        object.__setattr__(self, "availability", availability)
        execution_mode = (
            self.execution_mode
            if isinstance(self.execution_mode, TaskExecutionMode)
            else TaskExecutionMode(str(self.execution_mode))
        )
        object.__setattr__(self, "execution_mode", execution_mode)

        if self.risk not in {"none", "low", "medium", "high"}:
            raise ValueError(f"Invalid task risk: {self.risk}")
        if self.status not in {
            "available",
            "blocked",
            "needs_review",
            "in_progress",
            "succeeded",
            "failed",
            "verification_failed",
            "pending_reboot",
            "manual_only",
            "retired",
        }:
            raise ValueError(f"Invalid task status: {self.status}")
        if self.reboot_policy not in {"none", "may_require", "required"}:
            raise ValueError(f"Invalid task reboot policy: {self.reboot_policy}")

        params = tuple(
            item if isinstance(item, TaskParameter) else TaskParameter.from_dict(item)
            for item in self.parameters
        )
        parameter_names = tuple(item.name for item in params)
        if len(parameter_names) != len(set(parameter_names)):
            raise ValueError(f"Task {self.id} has duplicate parameter names.")
        object.__setattr__(self, "parameters", params)

        steps = ("preflight", "verification", "recovery")
        for field_name in steps:
            raw_steps = tuple(getattr(self, field_name))
            normalized_steps = tuple(
                item if isinstance(item, TaskStep) else TaskStep.from_dict(item)
                for item in raw_steps
            )
            step_ids = tuple(item.id for item in normalized_steps)
            if len(step_ids) != len(set(step_ids)):
                raise ValueError(f"Task {self.id} has duplicate {field_name} step IDs.")
            object.__setattr__(self, field_name, normalized_steps)

        variants = frozenset(
            item if isinstance(item, FedoraVariant) else FedoraVariant(str(item))
            for item in self.supported_variants
        )
        if not variants:
            raise ValueError(f"Task {self.id} must declare at least one Fedora variant.")
        object.__setattr__(self, "supported_variants", variants)

        capabilities = frozenset(str(item).strip() for item in self.required_capabilities if str(item).strip())
        object.__setattr__(self, "required_capabilities", capabilities)
        object.__setattr__(self, "keywords", tuple(str(item).strip() for item in self.keywords if str(item).strip()))
        object.__setattr__(self, "metadata", MappingProxyType(dict(self.metadata)))

        if self.execution_mode is TaskExecutionMode.EXECUTE and not (self.action_id or self.bundle_id):
            raise ValueError(f"Executable task {self.id} needs an action_id or bundle_id.")
        if self.execution_mode is TaskExecutionMode.GUIDANCE and not self.manual_guidance:
            raise ValueError(f"Guidance task {self.id} needs manual_guidance.")
        if self.execution_mode is TaskExecutionMode.HANDOFF and not self.handoff_route_id:
            raise ValueError(f"Handoff task {self.id} needs handoff_route_id.")
        if self.availability is CapabilityState.MANUAL_ONLY and self.execution_mode is TaskExecutionMode.EXECUTE:
            raise ValueError(f"Manual-only task {self.id} cannot be executable.")
        if self.status == "manual_only" and self.execution_mode is TaskExecutionMode.EXECUTE:
            raise ValueError(f"Manual-only status cannot be executable for {self.id}.")

        # Active tasks must promise all three lifecycle surfaces.  Read-only
        # tasks use the same contract so the UI never reaches an unexplained
        # dead end when a probe or verification fails.
        if self.status != "retired":
            for field_name in steps:
                if not getattr(self, field_name):
                    raise ValueError(f"Active task {self.id} needs {field_name} metadata.")

    @property
    def kind(self) -> str:
        """Return the stable string form used by search and CLI payloads."""
        return cast(TaskArea, self.area).value

    @property
    def owner_page(self) -> str:
        """Human-facing alias for the owning route/page."""
        return self.route_id

    @property
    def owner_route_id(self) -> str:
        return self.route_id

    @property
    def owner_route(self) -> str:
        """Alias used by navigation adapters that call the page a route."""
        return self.route_id

    @property
    def summary(self) -> str:
        return self.goal or self.description

    @property
    def risk_level(self) -> RiskLevel:
        return self.risk

    @property
    def capability_state(self) -> CapabilityState:
        return cast(CapabilityState, self.availability)

    @property
    def manual_only(self) -> bool:
        # Native handoffs are still first-class normal tasks.  They are not
        # executable by Loofi, but unlike manual-only guidance they have a
        # deterministic destination and should remain visible on the owning
        # landing page.
        return self.execution_mode is TaskExecutionMode.GUIDANCE or self.availability is CapabilityState.MANUAL_ONLY or self.status == "manual_only"

    @property
    def executable(self) -> bool:
        return self.execution_mode is TaskExecutionMode.EXECUTE and not self.manual_only

    @property
    def parameter_schema(self) -> Mapping[str, Mapping[str, Any]]:
        """Project parameters into the familiar action-schema shape."""
        return MappingProxyType(
            {
                item.name: {
                    "type": item.type,
                    "required": item.required,
                    **({"description": item.description} if item.description else {}),
                    **({"default": item.default} if item.default is not None else {}),
                }
                for item in self.parameters
            }
        )

    @property
    def verification_steps(self) -> tuple[TaskStep, ...]:
        return self.verification

    @property
    def recovery_steps(self) -> tuple[TaskStep, ...]:
        return self.recovery

    @property
    def preflight_steps(self) -> tuple[TaskStep, ...]:
        return self.preflight

    @property
    def recovery_guidance(self) -> str:
        return " ".join(step.description for step in self.recovery)

    def supports(self, *, variant: FedoraVariant, capabilities: frozenset[str] = frozenset()) -> bool:
        """Return whether immutable host facts satisfy the task policy."""
        if variant is FedoraVariant.UNKNOWN or variant not in self.supported_variants:
            return False
        return self.required_capabilities.issubset(capabilities)

    def to_dict(self) -> dict[str, Any]:
        """Serialize only stable primitive metadata; never execution code."""
        return {
            "schema_version": TASK_DESCRIPTOR_SCHEMA_VERSION,
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "goal": self.goal,
            "area": cast(TaskArea, self.area).value,
            "kind": cast(TaskArea, self.area).value,
            "route_id": self.route_id,
            "owner_page": self.route_id,
            "group": self.group,
            "icon": self.icon,
            "keywords": list(self.keywords),
            "action_id": self.action_id,
            "bundle_id": self.bundle_id,
            "availability": cast(CapabilityState, self.availability).value,
            "capability_state": cast(CapabilityState, self.availability).value,
            "risk": self.risk,
            "risk_level": self.risk,
            "status": self.status,
            "execution_mode": cast(TaskExecutionMode, self.execution_mode).value,
            "parameters": [item.to_dict() for item in self.parameters],
            "parameter_schema": {key: dict(value) for key, value in self.parameter_schema.items()},
            "required_capabilities": sorted(self.required_capabilities),
            "supported_variants": sorted(item.value for item in self.supported_variants),
            "preflight": [item.to_dict() for item in self.preflight],
            "verification": [item.to_dict() for item in self.verification],
            "recovery": [item.to_dict() for item in self.recovery],
            "manual_guidance": self.manual_guidance,
            "handoff_route_id": self.handoff_route_id,
            "reboot_policy": self.reboot_policy,
            "discoverable": self.discoverable,
            "profile_eligible": self.profile_eligible,
            "order": self.order,
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "TaskDescriptor":
        schema_version = int(payload.get("schema_version", TASK_DESCRIPTOR_SCHEMA_VERSION))
        if schema_version != TASK_DESCRIPTOR_SCHEMA_VERSION:
            raise ValueError(f"Unsupported task descriptor schema: {schema_version}")
        raw_parameters = payload.get("parameters", [])
        if not isinstance(raw_parameters, (list, tuple)):
            raise ValueError("Task descriptor parameters must be a collection.")
        return cls(
            id=str(payload.get("id", "")),
            title=str(payload.get("title", "")),
            description=str(payload.get("description", "")),
            goal=str(payload.get("goal", "")),
            group=str(payload.get("group", "")),
            area=str(payload.get("area", payload.get("kind", ""))),
            route_id=str(payload.get("route_id", payload.get("owner_page", ""))),
            icon=str(payload.get("icon", "")),
            keywords=tuple(str(item) for item in payload.get("keywords", ())),
            action_id=(str(payload["action_id"]) if payload.get("action_id") is not None else None),
            bundle_id=(str(payload["bundle_id"]) if payload.get("bundle_id") is not None else None),
            availability=str(payload.get("availability", CapabilityState.SUPPORTED.value)),
            risk=str(payload.get("risk", payload.get("risk_level", "low"))),  # type: ignore[arg-type]
            status=str(payload.get("status", "available")),  # type: ignore[arg-type]
            execution_mode=str(payload.get("execution_mode", TaskExecutionMode.EXECUTE.value)),
            parameters=tuple(TaskParameter.from_dict(item) for item in raw_parameters if isinstance(item, Mapping)),
            required_capabilities=frozenset(str(item) for item in payload.get("required_capabilities", ())),
            supported_variants=frozenset(
                FedoraVariant(str(item)) for item in payload.get("supported_variants", ("traditional", "atomic"))
            ),
            preflight=tuple(
                TaskStep.from_dict(item) for item in payload.get("preflight", ()) if isinstance(item, Mapping)
            ),
            verification=tuple(
                TaskStep.from_dict(item) for item in payload.get("verification", ()) if isinstance(item, Mapping)
            ),
            recovery=tuple(
                TaskStep.from_dict(item) for item in payload.get("recovery", ()) if isinstance(item, Mapping)
            ),
            manual_guidance=str(payload.get("manual_guidance", "")),
            handoff_route_id=(str(payload["handoff_route_id"]) if payload.get("handoff_route_id") is not None else None),
            reboot_policy=str(payload.get("reboot_policy", "none")),  # type: ignore[arg-type]
            discoverable=bool(payload.get("discoverable", True)),
            profile_eligible=bool(payload.get("profile_eligible", False)),
            order=int(payload.get("order", 100)),
            metadata=payload.get("metadata", {}) if isinstance(payload.get("metadata", {}), Mapping) else {},
        )


# A concise public name for callers that prefer ``Descriptor`` in type hints.
Task = TaskDescriptor


__all__ = [
    "CapabilityState",
    "FedoraVariant",
    "ParameterSpec",
    "RebootPolicy",
    "RiskLevel",
    "TASK_DESCRIPTOR_SCHEMA_VERSION",
    "Task",
    "TaskArea",
    "TaskCheck",
    "TaskDescriptor",
    "TaskExecutionMode",
    "TaskKind",
    "TaskParameter",
    "TaskStatus",
    "TaskStep",
]
