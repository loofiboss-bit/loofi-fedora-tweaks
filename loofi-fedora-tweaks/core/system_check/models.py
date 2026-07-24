"""Immutable, privacy-safe contracts for the canonical System Check domain."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Any, Literal, Mapping, cast

from core.privacy import redact_payload

CheckState = Literal["queued", "running", "completed", "partial", "cancelled", "failed"]
CheckProgressStage = Literal["running", "completed", "failed", "timed_out", "cancelling"]
FindingSeverity = Literal["attention", "critical"]
FindingFreshness = Literal["fresh", "stale", "unknown"]
SupportedVariant = Literal["traditional", "atomic"]

_VARIANTS = frozenset({"traditional", "atomic"})
_STATES = frozenset({"queued", "running", "completed", "partial", "cancelled", "failed"})
_SEVERITIES = frozenset({"attention", "critical"})
_FRESHNESS_STATES = frozenset({"fresh", "stale", "unknown"})
_EXECUTABLE_KEYS = frozenset({
    "callback",
    "command",
    "command_preview",
    "command_vector",
    "executable",
    "runner",
})


def _freeze(value: Any) -> Any:
    if callable(value):
        raise ValueError("System Check evidence cannot contain callbacks.")
    if isinstance(value, Mapping):
        for key in value:
            if str(key).lower() in _EXECUTABLE_KEYS:
                raise ValueError(f"System Check evidence cannot contain executable field '{key}'.")
        return tuple((str(key), _freeze(item)) for key, item in sorted(value.items(), key=lambda pair: str(pair[0])))
    if isinstance(value, (list, tuple, set, frozenset)):
        return tuple(_freeze(item) for item in value)
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    return str(value)


def _thaw(value: Any) -> Any:
    if isinstance(value, tuple):
        if all(isinstance(item, tuple) and len(item) == 2 and isinstance(item[0], str) for item in value):
            return {item[0]: _thaw(item[1]) for item in value}
        return [_thaw(item) for item in value]
    return value


def _fingerprint(finding_id: str, facts: Mapping[str, Any], variants: frozenset[str]) -> str:
    normalized = redact_payload({
        "finding_id": finding_id,
        "facts": _thaw(_freeze(facts)),
        "applicable_variants": sorted(variants),
    })
    canonical = json.dumps(normalized, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class FindingEvidence:
    """Closed, non-executable facts supporting one finding."""

    source_id: str
    facts: tuple[tuple[str, Any], ...]
    collected_at: float

    @classmethod
    def from_mapping(
        cls,
        source_id: str,
        facts: Mapping[str, Any],
        *,
        collected_at: float,
    ) -> "FindingEvidence":
        frozen = _freeze(redact_payload(dict(facts)))
        if not isinstance(frozen, tuple):
            raise ValueError("Finding evidence must be a mapping.")
        return cls(str(source_id), frozen, float(collected_at))

    def facts_dict(self) -> dict[str, Any]:
        return dict(_thaw(self.facts))

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_id": self.source_id,
            "facts": self.facts_dict(),
            "collected_at": self.collected_at,
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "FindingEvidence":
        facts = payload.get("facts", {})
        if not isinstance(facts, Mapping):
            raise ValueError("Persisted finding evidence facts must be a mapping.")
        return cls.from_mapping(
            str(payload.get("source_id", "")),
            facts,
            collected_at=float(payload.get("collected_at", 0.0)),
        )


@dataclass(frozen=True)
class SystemFinding:
    """One deterministic problem description with no executable behavior."""

    finding_id: str
    category: str
    severity: FindingSeverity
    title: str
    summary: str
    evidence: FindingEvidence
    applicable_variants: frozenset[SupportedVariant]
    freshness_state: FindingFreshness
    affected_resources: tuple[str, ...] = ()
    action_id: str = ""
    action_parameters: tuple[tuple[str, Any], ...] = ()
    route_id: str = ""
    manual_guidance: str = ""
    manual_reason_code: str = ""
    fingerprint: str = ""

    def __post_init__(self) -> None:
        if self.severity not in _SEVERITIES:
            raise ValueError(f"Unsupported finding severity: {self.severity}")
        if not self.applicable_variants or not set(self.applicable_variants).issubset(_VARIANTS):
            raise ValueError("Every finding must declare supported Traditional/Atomic applicability.")
        if self.freshness_state not in _FRESHNESS_STATES:
            raise ValueError(f"Unsupported finding freshness: {self.freshness_state}")
        if not (self.action_id or self.route_id or self.manual_guidance):
            raise ValueError("Every finding requires an audited action, navigation route, or manual guidance.")
        if self.manual_guidance and not self.manual_reason_code:
            raise ValueError("Manual finding guidance requires a stable reason code.")
        if self.manual_reason_code and not self.manual_guidance:
            raise ValueError("A manual reason code cannot exist without manual guidance.")
        if self.severity == "critical" and not (self.action_id or self.manual_guidance):
            raise ValueError("Critical findings require an audited action or manual guidance.")
        _freeze(dict(self.action_parameters))
        expected = _fingerprint(self.finding_id, self.evidence.facts_dict(), frozenset(self.applicable_variants))
        if not self.fingerprint:
            object.__setattr__(self, "fingerprint", expected)
        elif self.fingerprint != expected:
            raise ValueError("Finding fingerprint does not match normalized evidence.")

    @classmethod
    def build(
        cls,
        *,
        finding_id: str,
        category: str,
        severity: FindingSeverity,
        title: str,
        summary: str,
        evidence: FindingEvidence,
        applicable_variants: frozenset[SupportedVariant],
        freshness_state: FindingFreshness,
        affected_resources: tuple[str, ...] = (),
        action_id: str = "",
        action_parameters: Mapping[str, Any] | None = None,
        route_id: str = "",
        manual_guidance: str = "",
        manual_reason_code: str = "",
        fingerprint: str = "",
    ) -> "SystemFinding":
        parameters = _freeze(dict(action_parameters or {}))
        return cls(
            finding_id=finding_id,
            category=category,
            severity=severity,
            title=title,
            summary=summary,
            evidence=evidence,
            applicable_variants=applicable_variants,
            freshness_state=freshness_state,
            affected_resources=tuple(affected_resources),
            action_id=action_id,
            action_parameters=parameters,
            route_id=route_id,
            manual_guidance=manual_guidance,
            manual_reason_code=manual_reason_code,
            fingerprint=fingerprint,
        )

    def parameters_dict(self) -> dict[str, Any]:
        return dict(_thaw(self.action_parameters))

    def to_dict(self) -> dict[str, Any]:
        return {
            "finding_id": self.finding_id,
            "category": self.category,
            "severity": self.severity,
            "title": self.title,
            "summary": self.summary,
            "evidence": self.evidence.to_dict(),
            "applicable_variants": sorted(self.applicable_variants),
            "freshness_state": self.freshness_state,
            "affected_resources": list(self.affected_resources),
            "action_id": self.action_id,
            "action_parameters": self.parameters_dict(),
            "route_id": self.route_id,
            "manual_guidance": self.manual_guidance,
            "manual_reason_code": self.manual_reason_code,
            "fingerprint": self.fingerprint,
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "SystemFinding":
        evidence = payload.get("evidence", {})
        parameters = payload.get("action_parameters", {})
        variants = payload.get("applicable_variants", [])
        resources = payload.get("affected_resources", [])
        if not isinstance(evidence, Mapping):
            raise ValueError("Persisted finding evidence must be a mapping.")
        if not isinstance(parameters, Mapping):
            raise ValueError("Persisted finding parameters must be a mapping.")
        if not isinstance(variants, (list, tuple, set, frozenset)):
            raise ValueError("Persisted finding variants must be a collection.")
        if not isinstance(resources, (list, tuple)):
            raise ValueError("Persisted finding resources must be a collection.")
        return cls.build(
            finding_id=str(payload.get("finding_id", "")),
            category=str(payload.get("category", "")),
            severity=str(payload.get("severity", "attention")),  # type: ignore[arg-type]
            title=str(payload.get("title", "")),
            summary=str(payload.get("summary", "")),
            evidence=FindingEvidence.from_dict(evidence),
            applicable_variants=cast(
                frozenset[SupportedVariant],
                frozenset(str(item) for item in variants),
            ),
            freshness_state=str(payload.get("freshness_state", "unknown")),  # type: ignore[arg-type]
            affected_resources=tuple(str(item) for item in resources),
            action_id=str(payload.get("action_id", "")),
            action_parameters=dict(parameters),
            route_id=str(payload.get("route_id", "")),
            manual_guidance=str(payload.get("manual_guidance", "")),
            manual_reason_code=str(payload.get("manual_reason_code", "")),
            fingerprint=str(payload.get("fingerprint", "")),
        )


@dataclass(frozen=True)
class CheckSourceError:
    """Bounded collector failure retained alongside successful evidence."""

    source_id: str
    reason_code: str
    message: str
    duration_ms: float
    timed_out: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_id": self.source_id,
            "reason_code": self.reason_code,
            "message": self.message,
            "duration_ms": self.duration_ms,
            "timed_out": self.timed_out,
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "CheckSourceError":
        return cls(
            source_id=str(payload.get("source_id", "")),
            reason_code=str(payload.get("reason_code", "")),
            message=str(payload.get("message", "")),
            duration_ms=float(payload.get("duration_ms", 0.0)),
            timed_out=bool(payload.get("timed_out", False)),
        )


@dataclass(frozen=True)
class CheckProgress:
    """One bounded progress update from the closed collector profile."""

    source_id: str
    stage: CheckProgressStage
    completed_sources: int
    total_sources: int
    elapsed_seconds: float
    unavailable_sources: tuple[str, ...] = ()

    @property
    def percentage(self) -> int:
        if self.total_sources <= 0:
            return 0
        return max(0, min(100, round(100 * self.completed_sources / self.total_sources)))


@dataclass(frozen=True)
class SystemCheckResult:
    """Complete, partial, failed, or cancelled result from one closed profile."""

    check_id: str
    profile_id: str
    state: CheckState
    atomic: bool
    started_at: float
    completed_at: float | None
    findings: tuple[SystemFinding, ...] = ()
    source_errors: tuple[CheckSourceError, ...] = ()
    source_durations_ms: tuple[tuple[str, float], ...] = ()
    completed_sources: tuple[str, ...] = ()
    cancelled_sources: tuple[str, ...] = ()
    schema_version: int = field(default=1, init=False)

    def __post_init__(self) -> None:
        if self.state not in _STATES:
            raise ValueError(f"Unsupported System Check state: {self.state}")
        if self.state in {"queued", "running"} and self.completed_at is not None:
            raise ValueError("An active System Check cannot have a completion timestamp.")
        if self.state not in {"queued", "running"} and self.completed_at is None:
            raise ValueError("A terminal System Check requires a completion timestamp.")
        if self.completed_at is not None and self.completed_at < self.started_at:
            raise ValueError("System Check completion cannot precede its start.")
        if self.state == "completed" and self.source_errors:
            raise ValueError("A completed System Check cannot contain collector errors.")
        if self.state == "partial" and not self.source_errors:
            raise ValueError("A partial System Check must identify collector errors.")

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "check_id": self.check_id,
            "profile_id": self.profile_id,
            "state": self.state,
            "atomic": self.atomic,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "findings": [finding.to_dict() for finding in self.findings],
            "source_errors": [error.to_dict() for error in self.source_errors],
            "source_durations_ms": dict(self.source_durations_ms),
            "completed_sources": list(self.completed_sources),
            "cancelled_sources": list(self.cancelled_sources),
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "SystemCheckResult":
        """Strictly reconstruct one supported persisted result."""
        if int(payload.get("schema_version", 0)) != 1:
            raise ValueError("Unsupported System Check result schema.")
        findings = payload.get("findings", [])
        errors = payload.get("source_errors", [])
        durations = payload.get("source_durations_ms", {})
        completed_sources = payload.get("completed_sources", [])
        cancelled_sources = payload.get("cancelled_sources", [])
        if not isinstance(findings, list) or not isinstance(errors, list):
            raise ValueError("Persisted System Check findings and errors must be lists.")
        if any(not isinstance(item, Mapping) for item in findings):
            raise ValueError("Persisted System Check contains an invalid finding.")
        if any(not isinstance(item, Mapping) for item in errors):
            raise ValueError("Persisted System Check contains an invalid source error.")
        if not isinstance(durations, Mapping):
            raise ValueError("Persisted System Check source durations must be a mapping.")
        if not isinstance(completed_sources, (list, tuple)):
            raise ValueError("Persisted completed sources must be a collection.")
        if not isinstance(cancelled_sources, (list, tuple)):
            raise ValueError("Persisted cancelled sources must be a collection.")
        if not str(payload.get("check_id", "")) or not str(
            payload.get("profile_id", "")
        ):
            raise ValueError("Persisted System Check identity is incomplete.")
        return cls(
            check_id=str(payload.get("check_id", "")),
            profile_id=str(payload.get("profile_id", "")),
            state=str(payload.get("state", "failed")),  # type: ignore[arg-type]
            atomic=bool(payload.get("atomic", False)),
            started_at=float(payload.get("started_at", 0.0)),
            completed_at=(
                float(payload["completed_at"])
                if payload.get("completed_at") is not None
                else None
            ),
            findings=tuple(
                SystemFinding.from_dict(item)
                for item in findings
            ),
            source_errors=tuple(
                CheckSourceError.from_dict(item)
                for item in errors
            ),
            source_durations_ms=tuple(
                sorted((str(key), float(value)) for key, value in durations.items())
            ),
            completed_sources=tuple(str(item) for item in completed_sources),
            cancelled_sources=tuple(str(item) for item in cancelled_sources),
        )
