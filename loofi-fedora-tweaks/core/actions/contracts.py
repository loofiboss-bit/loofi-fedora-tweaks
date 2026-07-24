"""Canonical v14 Action Center contracts and lifecycle validation."""

from __future__ import annotations

import time
import re
from dataclasses import dataclass, field
from typing import Any, Callable, Literal, Mapping, Protocol, Sequence

from core.actions.model import ActionRisk
from core.executor.action_result import ActionResult
from core.fedora_release_policy import FEDORA_RELEASE_POLICY

PlanState = Literal["planned", "ready", "needs_review", "blocked"]
RunState = Literal[
    "running",
    "verifying",
    "awaiting_reboot",
    "succeeded",
    "failed",
    "verification_failed",
    "cancelled",
    "interrupted",
]
ConfirmationPolicy = Literal["explicit", "explicit-no-rollback"]
OperationClass = Literal["host", "app_state", "session", "manual_only"]
SupportedVariant = Literal["traditional", "atomic"]
RebootPolicy = Literal["none", "may_require", "required"]

_RISK_LEVELS = frozenset({"low", "medium", "high", "critical"})
_CONFIRMATION_POLICIES = frozenset({"explicit", "explicit-no-rollback"})
_OPERATION_CLASSES = frozenset({"host", "app_state", "session", "manual_only"})
_SUPPORTED_VARIANTS = frozenset({"traditional", "atomic"})
_REBOOT_POLICIES = frozenset({"none", "may_require", "required"})
_FINDING_ORIGIN_ROUTES = frozenset({"health", "maintenance:health-timeline"})
_SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")
_CHECK_ID_PATTERN = re.compile(r"^[A-Za-z0-9._:-]{1,128}$")


def _validated_value(value: Any, allowed: frozenset[str], field_name: str) -> str:
    normalized = str(value)
    if normalized not in allowed:
        raise ValueError(f"Invalid persisted {field_name}: {normalized}")
    return normalized


def _validated_variants(value: Any) -> frozenset[SupportedVariant]:
    if not isinstance(value, (list, tuple, set, frozenset)):
        raise ValueError("Persisted supported_variants must be a collection.")
    variants = frozenset(str(item) for item in value)
    if not variants.issubset(_SUPPORTED_VARIANTS):
        raise ValueError("Persisted supported_variants contain an unsupported variant.")
    return variants  # type: ignore[return-value]


class ActionLifecycleError(ValueError):
    """Raised when a persisted action attempts an invalid state transition."""


@dataclass(frozen=True)
class FindingContext:
    """Integrity-bound, non-authoritative link to one persisted System Check finding."""

    check_result_id: str
    finding_fingerprint: str
    evidence_digest: str
    origin_route: str
    affected_resources: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not _CHECK_ID_PATTERN.fullmatch(self.check_result_id):
            raise ValueError("Finding context requires a bounded check result ID.")
        if not _SHA256_PATTERN.fullmatch(self.finding_fingerprint):
            raise ValueError("Finding context fingerprint must be a SHA-256 digest.")
        if not _SHA256_PATTERN.fullmatch(self.evidence_digest):
            raise ValueError("Finding context evidence digest must be SHA-256.")
        if self.origin_route not in _FINDING_ORIGIN_ROUTES:
            raise ValueError("Finding context origin route is not a System Check route.")
        if len(self.affected_resources) > 16 or any(
            not resource
            or len(resource) > 160
            or any(ord(character) < 32 or ord(character) == 127 for character in resource)
            for resource in self.affected_resources
        ):
            raise ValueError("Finding context affected resources are invalid.")

    def to_dict(self) -> dict[str, Any]:
        return {
            "check_result_id": self.check_result_id,
            "finding_fingerprint": self.finding_fingerprint,
            "evidence_digest": self.evidence_digest,
            "origin_route": self.origin_route,
            "affected_resources": list(self.affected_resources),
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "FindingContext":
        resources = payload.get("affected_resources", [])
        if not isinstance(resources, (list, tuple)):
            raise ValueError("Finding context resources must be a collection.")
        return cls(
            check_result_id=str(payload.get("check_result_id", "")),
            finding_fingerprint=str(payload.get("finding_fingerprint", "")),
            evidence_digest=str(payload.get("evidence_digest", "")),
            origin_route=str(payload.get("origin_route", "")),
            affected_resources=tuple(str(item) for item in resources),
        )


PLAN_TRANSITIONS: dict[str, frozenset[str]] = {
    "planned": frozenset({"ready", "needs_review", "blocked"}),
    "ready": frozenset({"blocked"}),
    "needs_review": frozenset({"ready", "blocked"}),
    "blocked": frozenset(),
}

RUN_TRANSITIONS: dict[str, frozenset[str]] = {
    "running": frozenset({"verifying", "failed", "cancelled", "interrupted"}),
    "verifying": frozenset({"awaiting_reboot", "succeeded", "verification_failed", "interrupted"}),
    "awaiting_reboot": frozenset({"verifying", "interrupted"}),
    "succeeded": frozenset(),
    "failed": frozenset(),
    "verification_failed": frozenset(),
    "cancelled": frozenset(),
    "interrupted": frozenset(),
}


def _transition(current: str, target: str, table: Mapping[str, frozenset[str]]) -> None:
    if target not in table.get(current, frozenset()):
        raise ActionLifecycleError(f"Invalid Action Center transition: {current} -> {target}")


@dataclass(frozen=True)
class PolicyDecision:
    """Machine-readable preflight decision with an honest safe alternative."""

    allowed: bool
    reason_code: str
    explanation: str
    alternative: str = ""
    facts: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "allowed": self.allowed,
            "reason_code": self.reason_code,
            "explanation": self.explanation,
            "alternative": self.alternative,
            "facts": dict(self.facts),
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "PolicyDecision":
        facts = payload.get("facts", {})
        return cls(
            allowed=bool(payload.get("allowed", False)),
            reason_code=str(payload.get("reason_code", "invalid_policy")),
            explanation=str(payload.get("explanation", "Policy data is invalid.")),
            alternative=str(payload.get("alternative", "")),
            facts=dict(facts) if isinstance(facts, Mapping) else {},
        )


class ActionRuntime(Protocol):
    """Read-only system probes available to catalog definitions."""

    def is_atomic(self) -> bool:
        ...

    def package_manager(self) -> str:
        ...

    def fedora_version(self) -> str:
        ...

    def boot_id(self) -> str:
        ...

    def package_manager_busy(self) -> bool:
        ...

    def failed_services(self) -> tuple[bool, list[str], str]:
        ...

    def fstrim_support(self) -> tuple[bool, dict[str, Any], str]:
        ...

    def execute_read_only(self, vector: Sequence[str], *, action_id: str, timeout: int = 30) -> ActionResult:
        ...


CommandRenderer = Callable[[Mapping[str, Any], ActionRuntime], Sequence[str]]
PreflightChecker = Callable[[Mapping[str, Any], ActionRuntime], PolicyDecision]
ParameterValidator = Callable[[Mapping[str, Any]], PolicyDecision]
PrivilegeResolver = Callable[[Mapping[str, Any], ActionRuntime], bool]


VerificationState = Literal["succeeded", "awaiting_reboot", "failed"]


@dataclass(frozen=True)
class VerificationDecision:
    """Typed verification result, including durable reboot hand-off."""

    state: VerificationState
    message: str
    data: dict[str, Any] = field(default_factory=dict)
    exit_code: int | None = None

    @classmethod
    def succeeded(cls, message: str, **data: Any) -> "VerificationDecision":
        return cls("succeeded", message, data)

    @classmethod
    def awaiting_reboot(cls, message: str, **data: Any) -> "VerificationDecision":
        return cls("awaiting_reboot", message, data)

    @classmethod
    def failed(cls, message: str, *, exit_code: int | None = None, **data: Any) -> "VerificationDecision":
        return cls("failed", message, data, exit_code)

    def to_result(self, *, action_id: str) -> ActionResult:
        return ActionResult(
            success=self.state == "succeeded",
            message=self.message,
            exit_code=self.exit_code,
            data={"verification_state": self.state, **self.data},
            needs_reboot=self.state == "awaiting_reboot",
            action_id=action_id,
        )


ActionVerifier = Callable[["ActionRun", "ActionPlan", ActionRuntime], VerificationDecision | ActionResult]


@dataclass(frozen=True)
class ActionDefinition:
    """Audited first-party action definition; callables are never persisted."""

    id: str
    capability_id: str
    title: str
    description: str
    parameter_schema: dict[str, dict[str, Any]]
    risk_level: ActionRisk
    privileged: bool
    confirmation_policy: ConfirmationPolicy
    recovery_guidance: str
    rollback_supported: bool
    command_renderer: CommandRenderer = field(repr=False, compare=False)
    preflight_checker: PreflightChecker = field(repr=False, compare=False)
    verifier: ActionVerifier = field(repr=False, compare=False)
    operation_class: OperationClass = "host"
    supported_variants: frozenset[SupportedVariant] = field(
        default_factory=lambda: frozenset({"traditional", "atomic"})
    )
    reboot_policy: RebootPolicy = "none"
    affected_resources: tuple[str, ...] = ()
    parameter_validator: ParameterValidator | None = field(default=None, repr=False, compare=False)
    privilege_resolver: PrivilegeResolver | None = field(default=None, repr=False, compare=False)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "capability_id": self.capability_id,
            "title": self.title,
            "description": self.description,
            "parameter_schema": dict(self.parameter_schema),
            "risk_level": self.risk_level,
            "privileged": self.privileged,
            "confirmation_policy": self.confirmation_policy,
            "recovery_guidance": self.recovery_guidance,
            "rollback_supported": self.rollback_supported,
            "operation_class": self.operation_class,
            "supported_variants": sorted(self.supported_variants),
            "reboot_policy": self.reboot_policy,
            "affected_resources": list(self.affected_resources),
        }


@dataclass
class ActionPlan:
    """Bounded, expiring preview of one action and its policy facts."""

    plan_id: str
    action_id: str
    parameters: dict[str, Any]
    target: str
    digest: str
    preview: list[str]
    policy_decision: PolicyDecision
    risk_level: ActionRisk
    privileged: bool
    confirmation_policy: ConfirmationPolicy
    recovery_guidance: str
    rollback_supported: bool
    operation_class: OperationClass = "host"
    supported_variants: frozenset[SupportedVariant] = field(
        default_factory=lambda: frozenset({"traditional", "atomic"})
    )
    reboot_policy: RebootPolicy = "none"
    affected_resources: tuple[str, ...] = ()
    finding_context: FindingContext | None = None
    state: PlanState = "planned"
    created_at: float = field(default_factory=time.time)
    expires_at: float = 0.0
    state_history: list[dict[str, Any]] = field(default_factory=list)

    def transition(self, target: PlanState, reason: str, *, at: float | None = None) -> None:
        _transition(self.state, target, PLAN_TRANSITIONS)
        timestamp = time.time() if at is None else at
        self.state = target
        self.state_history.append({"state": target, "reason": reason, "timestamp": timestamp})

    def is_expired(self, now: float | None = None) -> bool:
        return (time.time() if now is None else now) >= self.expires_at

    def to_dict(self) -> dict[str, Any]:
        return {
            "plan_id": self.plan_id,
            "action_id": self.action_id,
            "parameters": dict(self.parameters),
            "target": self.target,
            "digest": self.digest,
            "preview": list(self.preview),
            "policy_decision": self.policy_decision.to_dict(),
            "risk_level": self.risk_level,
            "privileged": self.privileged,
            "confirmation_policy": self.confirmation_policy,
            "recovery_guidance": self.recovery_guidance,
            "rollback_supported": self.rollback_supported,
            "operation_class": self.operation_class,
            "supported_variants": sorted(self.supported_variants),
            "reboot_policy": self.reboot_policy,
            "affected_resources": list(self.affected_resources),
            "finding_context": self.finding_context.to_dict() if self.finding_context else None,
            "state": self.state,
            "created_at": self.created_at,
            "expires_at": self.expires_at,
            "state_history": [dict(entry) for entry in self.state_history],
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "ActionPlan":
        parameters = payload.get("parameters", {})
        history = payload.get("state_history", [])
        finding_context = payload.get("finding_context")
        return cls(
            plan_id=str(payload["plan_id"]),
            action_id=str(payload["action_id"]),
            parameters=dict(parameters) if isinstance(parameters, Mapping) else {},
            target=str(payload.get("target", FEDORA_RELEASE_POLICY.stable_target)),
            digest=str(payload.get("digest", "")),
            preview=[str(part) for part in payload.get("preview", [])],
            policy_decision=PolicyDecision.from_dict(payload.get("policy_decision", {})),
            risk_level=_validated_value(payload.get("risk_level", "low"), _RISK_LEVELS, "risk_level"),  # type: ignore[arg-type]
            privileged=bool(payload.get("privileged", False)),
            confirmation_policy=_validated_value(payload.get("confirmation_policy", "explicit"), _CONFIRMATION_POLICIES, "confirmation_policy"),  # type: ignore[arg-type]
            recovery_guidance=str(payload.get("recovery_guidance", "")),
            rollback_supported=bool(payload.get("rollback_supported", False)),
            operation_class=_validated_value(payload.get("operation_class", "host"), _OPERATION_CLASSES, "operation_class"),  # type: ignore[arg-type]
            supported_variants=_validated_variants(
                payload.get("supported_variants", ["traditional", "atomic"])
            ),
            reboot_policy=_validated_value(payload.get("reboot_policy", "none"), _REBOOT_POLICIES, "reboot_policy"),  # type: ignore[arg-type]
            affected_resources=tuple(str(item) for item in payload.get("affected_resources", [])),
            finding_context=(
                FindingContext.from_dict(finding_context)
                if isinstance(finding_context, Mapping)
                else None
            ),
            state=str(payload.get("state", "blocked")),  # type: ignore[arg-type]
            created_at=float(payload.get("created_at", 0.0)),
            expires_at=float(payload.get("expires_at", 0.0)),
            state_history=[dict(entry) for entry in history if isinstance(entry, Mapping)],
        )


@dataclass
class ActionRun:
    """Durable execution and verification record for one plan."""

    run_id: str
    plan_id: str
    action_id: str
    correlation_id: str
    parameters: dict[str, Any] = field(default_factory=dict)
    operation_class: OperationClass = "host"
    supported_variants: frozenset[SupportedVariant] = field(
        default_factory=lambda: frozenset({"traditional", "atomic"})
    )
    reboot_policy: RebootPolicy = "none"
    affected_resources: tuple[str, ...] = ()
    finding_context: FindingContext | None = None
    state: RunState = "running"
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    started_at: float = field(default_factory=time.time)
    completed_at: float | None = None
    execution_result: dict[str, Any] | None = None
    verification_result: dict[str, Any] | None = None
    recovery_status: str = "not-required"
    execution_boot_id: str = ""
    reboot_required: bool = False
    verification_attempts: int = 0
    last_verified_at: float | None = None
    state_history: list[dict[str, Any]] = field(default_factory=list)

    def transition(self, target: RunState, reason: str, *, at: float | None = None) -> None:
        _transition(self.state, target, RUN_TRANSITIONS)
        if target == "succeeded" and not bool((self.verification_result or {}).get("success", False)):
            raise ActionLifecycleError("A run cannot succeed without successful verification.")
        timestamp = time.time() if at is None else at
        self.state = target
        self.updated_at = timestamp
        if target in {"succeeded", "failed", "verification_failed", "cancelled", "interrupted"}:
            self.completed_at = timestamp
        self.state_history.append({"state": target, "reason": reason, "timestamp": timestamp})

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "plan_id": self.plan_id,
            "action_id": self.action_id,
            "correlation_id": self.correlation_id,
            "parameters": dict(self.parameters),
            "operation_class": self.operation_class,
            "supported_variants": sorted(self.supported_variants),
            "reboot_policy": self.reboot_policy,
            "affected_resources": list(self.affected_resources),
            "finding_context": self.finding_context.to_dict() if self.finding_context else None,
            "state": self.state,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "execution_result": dict(self.execution_result) if self.execution_result else None,
            "verification_result": dict(self.verification_result) if self.verification_result else None,
            "recovery_status": self.recovery_status,
            "execution_boot_id": self.execution_boot_id,
            "reboot_required": self.reboot_required,
            "verification_attempts": self.verification_attempts,
            "last_verified_at": self.last_verified_at,
            "state_history": [dict(entry) for entry in self.state_history],
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "ActionRun":
        execution = payload.get("execution_result")
        verification = payload.get("verification_result")
        history = payload.get("state_history", [])
        finding_context = payload.get("finding_context")
        return cls(
            run_id=str(payload["run_id"]),
            plan_id=str(payload["plan_id"]),
            action_id=str(payload["action_id"]),
            correlation_id=str(payload.get("correlation_id", payload["run_id"])),
            parameters=dict(payload.get("parameters", {})) if isinstance(payload.get("parameters", {}), Mapping) else {},
            operation_class=_validated_value(payload.get("operation_class", "host"), _OPERATION_CLASSES, "operation_class"),  # type: ignore[arg-type]
            supported_variants=_validated_variants(
                payload.get("supported_variants", ["traditional", "atomic"])
            ),
            reboot_policy=_validated_value(payload.get("reboot_policy", "none"), _REBOOT_POLICIES, "reboot_policy"),  # type: ignore[arg-type]
            affected_resources=tuple(str(item) for item in payload.get("affected_resources", [])),
            finding_context=(
                FindingContext.from_dict(finding_context)
                if isinstance(finding_context, Mapping)
                else None
            ),
            state=str(payload.get("state", "interrupted")),  # type: ignore[arg-type]
            created_at=float(payload.get("created_at", 0.0)),
            updated_at=float(payload.get("updated_at", 0.0)),
            started_at=float(payload.get("started_at", 0.0)),
            completed_at=float(payload["completed_at"]) if payload.get("completed_at") is not None else None,
            execution_result=dict(execution) if isinstance(execution, Mapping) else None,
            verification_result=dict(verification) if isinstance(verification, Mapping) else None,
            recovery_status=str(payload.get("recovery_status", "not-required")),
            execution_boot_id=str(payload.get("execution_boot_id", "")),
            reboot_required=bool(payload.get("reboot_required", False)),
            verification_attempts=int(payload.get("verification_attempts", 0)),
            last_verified_at=float(payload["last_verified_at"]) if payload.get("last_verified_at") is not None else None,
            state_history=[dict(entry) for entry in history if isinstance(entry, Mapping)],
        )


@dataclass(frozen=True)
class PreparedActionRun:
    """Ephemeral two-phase execution token for an async GUI worker."""

    run_id: str
    plan_id: str
    action_id: str
    correlation_id: str
    command: tuple[str, ...]
    privileged: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "plan_id": self.plan_id,
            "action_id": self.action_id,
            "correlation_id": self.correlation_id,
            "command": list(self.command),
            "privileged": self.privileged,
        }
