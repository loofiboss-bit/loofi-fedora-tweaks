"""Immutable, privacy-safe troubleshooting session contracts."""

from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import asdict, dataclass, field
from typing import Any, Literal, Mapping, cast

from core.troubleshooting.profiles import PROFILE_VERSION, require_profile
from core.troubleshooting.validation import (
    MAX_FINDINGS,
    MAX_PARAMETERS,
    MAX_RELATED_CHANGES,
    MAX_RESOURCES,
    freeze_mapping,
    thaw,
    validate_identifier,
    validate_resource_identifier,
    validate_text,
)


SESSION_SCHEMA_ID = "loofi.troubleshooting-session"
SESSION_SCHEMA_VERSION = 1
SessionState = Literal["queued", "running", "completed", "partial", "cancelled", "failed"]
SourceState = Literal[
    "completed",
    "empty",
    "partial",
    "stale",
    "unavailable",
    "timed_out",
    "failed",
    "cancelled",
]
FindingSeverity = Literal["info", "attention", "critical"]
EvidenceQuality = Literal["confirmed", "supported", "limited", "unknown"]
FreshnessState = Literal["fresh", "stale", "unknown"]
NextStepKind = Literal["action", "navigation", "collect", "manual", "none"]
SupportedVariant = Literal["traditional", "atomic"]
ComparisonState = Literal["resolved", "unchanged", "worsened", "not_comparable"]

_SESSION_STATES = frozenset({"queued", "running", "completed", "partial", "cancelled", "failed"})
_SOURCE_STATES = frozenset({
    "completed",
    "empty",
    "partial",
    "stale",
    "unavailable",
    "timed_out",
    "failed",
    "cancelled",
})
_EVIDENCE_SOURCE_STATES = frozenset({"completed", "empty", "partial", "stale"})
_TERMINAL_SESSION_STATES = frozenset({"completed", "partial", "cancelled", "failed"})
_EVIDENCE_QUALITIES = frozenset({"confirmed", "supported", "limited", "unknown"})
_FRESHNESS_STATES = frozenset({"fresh", "stale", "unknown"})
_SEVERITIES = frozenset({"info", "attention", "critical"})
_COMPARISON_STATES = frozenset({"resolved", "unchanged", "worsened", "not_comparable"})


def _validate_session_id(value: str) -> str:
    if not isinstance(value, str):
        raise ValueError("Troubleshooting session ID must be a string.")
    candidate = value
    try:
        parsed = uuid.UUID(candidate)
    except ValueError as exc:
        raise ValueError("Troubleshooting session ID must be an opaque UUID.") from exc
    if str(parsed) != candidate:
        raise ValueError("Troubleshooting session ID must use canonical UUID form.")
    return candidate


def _validate_fingerprint(value: str, *, field_name: str) -> str:
    if len(value) != 64:
        raise ValueError(f"{field_name} must be a SHA-256 digest.")
    try:
        int(value, 16)
    except ValueError as exc:
        raise ValueError(f"{field_name} must be a SHA-256 digest.") from exc
    if value != value.lower():
        raise ValueError(f"{field_name} must use canonical lower-case hexadecimal.")
    return value


@dataclass(frozen=True)
class NextStep:
    """Exactly one inert next step with no stored execution behavior."""

    kind: NextStepKind
    target_id: str = ""
    parameters: tuple[tuple[str, Any], ...] = ()
    guidance: str = ""
    reason_code: str = ""

    def __post_init__(self) -> None:
        if self.kind not in {"action", "navigation", "collect", "manual", "none"}:
            raise ValueError(f"Unsupported troubleshooting next-step kind: {self.kind}.")
        parameters = dict(thaw(self.parameters))
        canonical_parameters = freeze_mapping(
            parameters,
            field="next-step parameters",
            max_items=MAX_PARAMETERS,
        )
        if canonical_parameters != self.parameters:
            raise ValueError("Next-step parameters must use the canonical frozen form.")
        if len(parameters) > MAX_PARAMETERS:
            raise ValueError("Next-step parameters exceed the bounded limit.")
        if self.kind == "action":
            self._validate_action(parameters)
        elif self.kind == "navigation":
            self._validate_navigation(parameters)
        elif self.kind == "collect":
            validate_identifier(self.target_id, field="collection source")
            if parameters or self.guidance:
                raise ValueError("Read-only collection steps cannot carry presentation or execution data.")
            validate_identifier(self.reason_code, field="reason_code")
        elif self.kind == "manual":
            if self.target_id or parameters:
                raise ValueError("Manual guidance cannot contain a target or parameters.")
            validate_text(self.guidance, field="manual guidance")
            validate_identifier(self.reason_code, field="reason_code")
        else:
            if self.target_id or parameters or self.guidance:
                raise ValueError("No-safe-next-step cannot contain a target or payload.")
            validate_identifier(self.reason_code, field="reason_code")

    def _validate_action(self, parameters: Mapping[str, Any]) -> None:
        if self.guidance or not self.target_id:
            raise ValueError("Action next steps contain only an audited action ID and typed parameters.")
        from core.actions.catalog import ActionCatalog, validate_parameters

        definition = ActionCatalog().get(self.target_id)
        if definition is None:
            raise ValueError(f"Unknown Action Center action: {self.target_id}.")
        decision = validate_parameters(definition, parameters)
        if not decision.allowed:
            raise ValueError(f"Invalid Action Center parameters: {decision.reason_code}.")
        if self.reason_code:
            validate_identifier(self.reason_code, field="reason_code")

    def _validate_navigation(self, parameters: Mapping[str, Any]) -> None:
        if self.guidance or not self.target_id:
            raise ValueError("Navigation next steps contain only a canonical route and inert metadata.")
        from core.navigation.manifest import get_route

        if get_route(self.target_id) is None:
            raise ValueError(f"Unknown canonical navigation route: {self.target_id}.")
        if self.reason_code:
            validate_identifier(self.reason_code, field="reason_code")
        freeze_mapping(parameters, field="navigation preselection", max_items=MAX_PARAMETERS)

    @classmethod
    def action(
        cls,
        action_id: str,
        parameters: Mapping[str, Any] | None = None,
        *,
        reason_code: str = "",
    ) -> "NextStep":
        return cls(
            "action",
            action_id,
            freeze_mapping(parameters, field="action_parameters", max_items=MAX_PARAMETERS),
            reason_code=reason_code,
        )

    @classmethod
    def navigation(
        cls,
        route_id: str,
        preselection: Mapping[str, Any] | None = None,
        *,
        reason_code: str = "",
    ) -> "NextStep":
        return cls(
            "navigation",
            route_id,
            freeze_mapping(preselection, field="navigation preselection", max_items=MAX_PARAMETERS),
            reason_code=reason_code,
        )

    @classmethod
    def collect(cls, source_id: str, *, reason_code: str) -> "NextStep":
        return cls("collect", source_id, reason_code=reason_code)

    @classmethod
    def manual(cls, guidance: str, *, reason_code: str) -> "NextStep":
        return cls("manual", guidance=guidance, reason_code=reason_code)

    @classmethod
    def none(cls, *, reason_code: str) -> "NextStep":
        return cls("none", reason_code=reason_code)

    def parameters_dict(self) -> dict[str, Any]:
        return dict(thaw(self.parameters))

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "target_id": self.target_id,
            "parameters": self.parameters_dict(),
            "guidance": self.guidance,
            "reason_code": self.reason_code,
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "NextStep":
        parameters = payload.get("parameters", {})
        if not isinstance(parameters, Mapping):
            raise ValueError("Persisted next-step parameters must be a mapping.")
        return cls(
            kind=str(payload.get("kind", "none")),  # type: ignore[arg-type]
            target_id=str(payload.get("target_id", "")),
            parameters=freeze_mapping(parameters, field="next-step parameters", max_items=MAX_PARAMETERS),
            guidance=str(payload.get("guidance", "")),
            reason_code=str(payload.get("reason_code", "")),
        )


@dataclass(frozen=True)
class SourceResult:
    """One terminal source outcome bounded by its declared profile budget."""

    source_id: str
    state: SourceState
    started_at: float
    completed_at: float
    timeout_seconds: float
    facts: tuple[tuple[str, Any], ...] = ()
    reason_code: str = ""
    message: str = ""

    def __post_init__(self) -> None:
        validate_identifier(self.source_id, field="source_id")
        if self.state not in _SOURCE_STATES:
            raise ValueError(f"Unsupported troubleshooting source state: {self.state}.")
        if self.timeout_seconds <= 0:
            raise ValueError("Source timeout must be positive.")
        if self.completed_at < self.started_at:
            raise ValueError("Source completion cannot precede its start.")
        canonical_facts = freeze_mapping(dict(thaw(self.facts)), field="source facts")
        if canonical_facts != self.facts:
            raise ValueError("Source facts must use the canonical frozen form.")
        elapsed = self.completed_at - self.started_at
        if self.state in _EVIDENCE_SOURCE_STATES:
            if self.state in {"completed", "empty"} and (self.reason_code or self.message):
                raise ValueError("Completed and empty source results cannot contain an error.")
            if self.state in {"partial", "stale"}:
                validate_identifier(self.reason_code, field="reason_code")
                validate_text(self.message, field="source message")
            if elapsed > self.timeout_seconds:
                raise ValueError("Evidence source result exceeded its declared timeout.")
        else:
            validate_identifier(self.reason_code, field="reason_code")
            validate_text(self.message, field="source message")
            if self.facts:
                raise ValueError("Unavailable, timed-out, failed, or cancelled sources cannot claim facts.")
            if self.state == "timed_out" and elapsed < self.timeout_seconds:
                raise ValueError("A timed-out source must reach its declared timeout.")

    @classmethod
    def completed(
        cls,
        source_id: str,
        *,
        started_at: float,
        completed_at: float,
        timeout_seconds: float,
        facts: Mapping[str, Any] | None = None,
    ) -> "SourceResult":
        return cls(
            source_id,
            "completed",
            started_at,
            completed_at,
            timeout_seconds,
            freeze_mapping(facts, field="source facts"),
        )

    @classmethod
    def unavailable(
        cls,
        source_id: str,
        *,
        at: float,
        timeout_seconds: float,
        reason_code: str,
        message: str,
    ) -> "SourceResult":
        return cls(source_id, "unavailable", at, at, timeout_seconds, reason_code=reason_code, message=message)

    @classmethod
    def empty(
        cls,
        source_id: str,
        *,
        started_at: float,
        completed_at: float,
        timeout_seconds: float,
        facts: Mapping[str, Any] | None = None,
    ) -> "SourceResult":
        return cls(
            source_id,
            "empty",
            started_at,
            completed_at,
            timeout_seconds,
            freeze_mapping(facts, field="source facts"),
        )

    @classmethod
    def partial(
        cls,
        source_id: str,
        *,
        started_at: float,
        completed_at: float,
        timeout_seconds: float,
        facts: Mapping[str, Any] | None,
        reason_code: str,
        message: str,
    ) -> "SourceResult":
        return cls(
            source_id,
            "partial",
            started_at,
            completed_at,
            timeout_seconds,
            freeze_mapping(facts, field="source facts"),
            reason_code,
            message,
        )

    @classmethod
    def stale(
        cls,
        source_id: str,
        *,
        started_at: float,
        completed_at: float,
        timeout_seconds: float,
        facts: Mapping[str, Any] | None,
        reason_code: str = "stale-evidence",
        message: str = "The newest source-owned evidence is stale.",
    ) -> "SourceResult":
        return cls(
            source_id,
            "stale",
            started_at,
            completed_at,
            timeout_seconds,
            freeze_mapping(facts, field="source facts"),
            reason_code,
            message,
        )

    def facts_dict(self) -> dict[str, Any]:
        return dict(thaw(self.facts))

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_id": self.source_id,
            "state": self.state,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "timeout_seconds": self.timeout_seconds,
            "facts": self.facts_dict(),
            "reason_code": self.reason_code,
            "message": self.message,
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "SourceResult":
        facts = payload.get("facts", {})
        if not isinstance(facts, Mapping):
            raise ValueError("Persisted source facts must be a mapping.")
        return cls(
            source_id=str(payload.get("source_id", "")),
            state=str(payload.get("state", "failed")),  # type: ignore[arg-type]
            started_at=float(payload.get("started_at", 0.0)),
            completed_at=float(payload.get("completed_at", 0.0)),
            timeout_seconds=float(payload.get("timeout_seconds", 0.0)),
            facts=freeze_mapping(facts, field="source facts"),
            reason_code=str(payload.get("reason_code", "")),
            message=str(payload.get("message", "")),
        )


def _finding_fingerprint(
    finding_type: str,
    source_id: str,
    resources: tuple[str, ...],
    evidence: tuple[tuple[str, Any], ...],
) -> str:
    payload = {
        "finding_type": finding_type,
        "source_id": source_id,
        "affected_resources": sorted(resources),
        "evidence": thaw(evidence),
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class TroubleshootingFinding:
    """One structured finding with evidence quality and exactly one next step."""

    finding_type: str
    category: str
    severity: FindingSeverity
    title: str
    summary: str
    evidence_explanation: str
    source_id: str
    collected_at: float
    freshness: FreshnessState
    evidence_quality: EvidenceQuality
    applicable_variants: frozenset[SupportedVariant]
    affected_resources: tuple[str, ...]
    evidence: tuple[tuple[str, Any], ...]
    next_step: NextStep
    fingerprint: str = ""

    def __post_init__(self) -> None:
        validate_identifier(self.finding_type, field="finding_type")
        validate_identifier(self.category, field="finding category")
        validate_identifier(self.source_id, field="source_id")
        if self.severity not in _SEVERITIES:
            raise ValueError(f"Unsupported troubleshooting severity: {self.severity}.")
        if self.freshness not in _FRESHNESS_STATES:
            raise ValueError(f"Unsupported finding freshness: {self.freshness}.")
        if self.evidence_quality not in _EVIDENCE_QUALITIES:
            raise ValueError(f"Unsupported evidence quality: {self.evidence_quality}.")
        if not self.applicable_variants or not self.applicable_variants.issubset({"traditional", "atomic"}):
            raise ValueError("Every finding requires valid Fedora applicability.")
        validate_text(self.title, field="finding title")
        validate_text(self.summary, field="finding summary")
        validate_text(self.evidence_explanation, field="evidence explanation")
        if not self.affected_resources or len(self.affected_resources) > MAX_RESOURCES:
            raise ValueError("Every finding requires bounded affected resources.")
        for resource in self.affected_resources:
            validate_resource_identifier(resource)
        canonical_evidence = freeze_mapping(
            dict(thaw(self.evidence)),
            field="finding evidence",
        )
        if canonical_evidence != self.evidence:
            raise ValueError("Finding evidence must use the canonical frozen form.")
        expected = _finding_fingerprint(
            self.finding_type,
            self.source_id,
            self.affected_resources,
            self.evidence,
        )
        if not self.fingerprint:
            object.__setattr__(self, "fingerprint", expected)
        else:
            _validate_fingerprint(self.fingerprint, field_name="Finding fingerprint")
            if self.fingerprint != expected:
                raise ValueError("Finding fingerprint does not match its normalized evidence.")

    @classmethod
    def build(
        cls,
        *,
        finding_type: str,
        category: str,
        severity: FindingSeverity,
        title: str,
        summary: str,
        evidence_explanation: str,
        source_id: str,
        collected_at: float,
        freshness: FreshnessState,
        evidence_quality: EvidenceQuality,
        applicable_variants: frozenset[SupportedVariant],
        affected_resources: tuple[str, ...],
        evidence: Mapping[str, Any],
        next_step: NextStep,
        fingerprint: str = "",
    ) -> "TroubleshootingFinding":
        return cls(
            finding_type,
            category,
            severity,
            title,
            summary,
            evidence_explanation,
            source_id,
            collected_at,
            freshness,
            evidence_quality,
            applicable_variants,
            tuple(affected_resources),
            freeze_mapping(evidence, field="finding evidence"),
            next_step,
            fingerprint,
        )

    def evidence_dict(self) -> dict[str, Any]:
        return dict(thaw(self.evidence))

    def to_dict(self) -> dict[str, Any]:
        return {
            "finding_type": self.finding_type,
            "category": self.category,
            "severity": self.severity,
            "title": self.title,
            "summary": self.summary,
            "evidence_explanation": self.evidence_explanation,
            "source_id": self.source_id,
            "collected_at": self.collected_at,
            "freshness": self.freshness,
            "evidence_quality": self.evidence_quality,
            "applicable_variants": sorted(self.applicable_variants),
            "affected_resources": list(self.affected_resources),
            "evidence": self.evidence_dict(),
            "next_step": self.next_step.to_dict(),
            "fingerprint": self.fingerprint,
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "TroubleshootingFinding":
        evidence = payload.get("evidence", {})
        next_step = payload.get("next_step", {})
        variants = payload.get("applicable_variants", [])
        resources = payload.get("affected_resources", [])
        if not isinstance(evidence, Mapping) or not isinstance(next_step, Mapping):
            raise ValueError("Persisted finding evidence and next step must be mappings.")
        if not isinstance(variants, (list, tuple)) or not isinstance(resources, (list, tuple)):
            raise ValueError("Persisted finding applicability and resources must be collections.")
        return cls.build(
            finding_type=str(payload.get("finding_type", "")),
            category=str(payload.get("category", "")),
            severity=str(payload.get("severity", "attention")),  # type: ignore[arg-type]
            title=str(payload.get("title", "")),
            summary=str(payload.get("summary", "")),
            evidence_explanation=str(payload.get("evidence_explanation", "")),
            source_id=str(payload.get("source_id", "")),
            collected_at=float(payload.get("collected_at", 0.0)),
            freshness=str(payload.get("freshness", "unknown")),  # type: ignore[arg-type]
            evidence_quality=str(payload.get("evidence_quality", "unknown")),  # type: ignore[arg-type]
            applicable_variants=cast(
                frozenset[SupportedVariant],
                frozenset(str(item) for item in variants),
            ),
            affected_resources=tuple(str(item) for item in resources),
            evidence=dict(evidence),
            next_step=NextStep.from_dict(next_step),
            fingerprint=str(payload.get("fingerprint", "")),
        )


@dataclass(frozen=True)
class RelatedChangeReference:
    """A bounded source-owned change reference, always labelled possibly related."""

    change_id: str
    source_id: str
    occurred_at: float
    affected_resources: tuple[str, ...]
    match_reasons: frozenset[Literal["time_proximity", "shared_resource"]]
    label: str = field(default="Possibly related", init=False)

    def __post_init__(self) -> None:
        validate_identifier(self.change_id, field="change_id")
        validate_identifier(self.source_id, field="source_id")
        if not self.affected_resources or len(self.affected_resources) > MAX_RESOURCES:
            raise ValueError("Related changes require bounded affected resources.")
        for resource in self.affected_resources:
            validate_resource_identifier(resource)
        if not self.match_reasons or not self.match_reasons.issubset({"time_proximity", "shared_resource"}):
            raise ValueError("Related changes require a closed association reason.")

    def to_dict(self) -> dict[str, Any]:
        return {
            "change_id": self.change_id,
            "source_id": self.source_id,
            "occurred_at": self.occurred_at,
            "affected_resources": list(self.affected_resources),
            "match_reasons": sorted(self.match_reasons),
            "label": self.label,
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "RelatedChangeReference":
        resources = payload.get("affected_resources", [])
        reasons = payload.get("match_reasons", [])
        if payload.get("label", "Possibly related") != "Possibly related":
            raise ValueError("Troubleshooting correlation must stay labelled Possibly related.")
        if not isinstance(resources, (list, tuple)) or not isinstance(reasons, (list, tuple)):
            raise ValueError("Persisted related-change fields must be collections.")
        return cls(
            str(payload.get("change_id", "")),
            str(payload.get("source_id", "")),
            float(payload.get("occurred_at", 0.0)),
            tuple(str(item) for item in resources),
            cast(
                frozenset[Literal["time_proximity", "shared_resource"]],
                frozenset(str(item) for item in reasons),
            ),
        )


@dataclass(frozen=True)
class CompatibilityMetadata:
    """Facts required before a future follow-up comparison can be attempted."""

    profile_version: int
    variant: SupportedVariant
    source_versions: tuple[tuple[str, int], ...] = ()

    def __post_init__(self) -> None:
        if self.profile_version != PROFILE_VERSION:
            raise ValueError("Unsupported troubleshooting profile version.")
        if self.variant not in {"traditional", "atomic"}:
            raise ValueError("Unsupported Fedora variant.")
        for source_id, version in self.source_versions:
            validate_identifier(source_id, field="source_id")
            if version < 1:
                raise ValueError("Source schema versions must be positive.")
        if len({source_id for source_id, _version in self.source_versions}) != len(
            self.source_versions
        ):
            raise ValueError("Source compatibility versions must be unique.")

    def to_dict(self) -> dict[str, Any]:
        return {
            "profile_version": self.profile_version,
            "variant": self.variant,
            "source_versions": dict(self.source_versions),
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "CompatibilityMetadata":
        versions = payload.get("source_versions", {})
        if not isinstance(versions, Mapping):
            raise ValueError("Persisted source versions must be a mapping.")
        return cls(
            int(payload.get("profile_version", 0)),
            str(payload.get("variant", "")),  # type: ignore[arg-type]
            tuple(sorted((str(key), int(value)) for key, value in versions.items())),
        )


@dataclass(frozen=True)
class TroubleshootingSession:
    """One explicit troubleshooting session with no execution authority."""

    session_id: str
    profile_id: str
    profile_version: int
    variant: SupportedVariant
    state: SessionState
    started_at: float
    completed_at: float | None
    profile_parameters: tuple[tuple[str, Any], ...] = ()
    source_results: tuple[SourceResult, ...] = ()
    findings: tuple[TroubleshootingFinding, ...] = ()
    related_changes: tuple[RelatedChangeReference, ...] = ()
    compatibility: CompatibilityMetadata | None = None
    schema_id: str = field(default=SESSION_SCHEMA_ID, init=False)
    schema_version: int = field(default=SESSION_SCHEMA_VERSION, init=False)

    def __post_init__(self) -> None:
        _validate_session_id(self.session_id)
        profile = require_profile(self.profile_id)
        if self.profile_version != profile.version:
            raise ValueError("Session profile version does not match the closed catalog.")
        if self.variant not in {"traditional", "atomic"}:
            raise ValueError("Unsupported Fedora variant.")
        if self.state not in _SESSION_STATES:
            raise ValueError(f"Unsupported troubleshooting session state: {self.state}.")
        if self.state in {"queued", "running"} and self.completed_at is not None:
            raise ValueError("An active troubleshooting session cannot be completed.")
        if self.state in _TERMINAL_SESSION_STATES and self.completed_at is None:
            raise ValueError("A terminal troubleshooting session requires a completion timestamp.")
        if self.completed_at is not None and self.completed_at < self.started_at:
            raise ValueError("Session completion cannot precede its start.")
        profile.validate_parameters(dict(thaw(self.profile_parameters)))
        source_ids = tuple(result.source_id for result in self.source_results)
        if len(source_ids) != len(set(source_ids)):
            raise ValueError("A session cannot contain duplicate source results.")
        expected_source_ids = {
            budget.source_id
            for budget in profile.source_budgets
            if self.variant in budget.variants
        }
        if self.state in _TERMINAL_SESSION_STATES and set(source_ids) != expected_source_ids:
            raise ValueError("A terminal session must retain every applicable profile source.")
        for result in self.source_results:
            budget = profile.budget_for(result.source_id, self.variant)
            if budget is None or result.timeout_seconds != budget.timeout_seconds:
                raise ValueError("Source result does not match the closed profile budget.")
        if len(self.findings) > MAX_FINDINGS or len(self.related_changes) > MAX_RELATED_CHANGES:
            raise ValueError("Troubleshooting session exceeds bounded result limits.")
        if any(finding.source_id not in source_ids for finding in self.findings):
            raise ValueError("Every finding must reference a retained source result.")
        if any(self.variant not in finding.applicable_variants for finding in self.findings):
            raise ValueError("A finding cannot cross Traditional and Atomic variants.")
        if self.compatibility is None:
            object.__setattr__(
                self,
                "compatibility",
                CompatibilityMetadata(self.profile_version, self.variant),
            )
        elif (
            self.compatibility.profile_version != self.profile_version
            or self.compatibility.variant != self.variant
        ):
            raise ValueError("Session compatibility metadata conflicts with its profile or variant.")
        if self.state == "completed" and any(
            result.state not in {"completed", "empty"}
            for result in self.source_results
        ):
            raise ValueError("A completed session cannot contain incomplete source results.")
        if self.state == "partial" and (
            all(result.state in {"completed", "empty"} for result in self.source_results)
            or any(result.state == "cancelled" for result in self.source_results)
        ):
            raise ValueError("A partial session must identify non-cancelled incomplete evidence.")
        if self.state == "cancelled" and not any(result.state == "cancelled" for result in self.source_results):
            raise ValueError("A cancelled session must retain cancellation evidence.")
        if self.state == "failed" and any(result.state != "failed" for result in self.source_results):
            raise ValueError("A failed session requires every applicable source to fail.")

    @property
    def completed_sources(self) -> tuple[str, ...]:
        return self._sources_with_state("completed")

    @property
    def unavailable_sources(self) -> tuple[str, ...]:
        return self._sources_with_state("unavailable")

    @property
    def empty_sources(self) -> tuple[str, ...]:
        return self._sources_with_state("empty")

    @property
    def partial_sources(self) -> tuple[str, ...]:
        return self._sources_with_state("partial")

    @property
    def stale_sources(self) -> tuple[str, ...]:
        return self._sources_with_state("stale")

    @property
    def timed_out_sources(self) -> tuple[str, ...]:
        return self._sources_with_state("timed_out")

    @property
    def failed_sources(self) -> tuple[str, ...]:
        return self._sources_with_state("failed")

    @property
    def cancelled_sources(self) -> tuple[str, ...]:
        return self._sources_with_state("cancelled")

    def _sources_with_state(self, state: SourceState) -> tuple[str, ...]:
        return tuple(sorted(result.source_id for result in self.source_results if result.state == state))

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_id": self.schema_id,
            "schema_version": self.schema_version,
            "session_id": self.session_id,
            "profile_id": self.profile_id,
            "profile_version": self.profile_version,
            "variant": self.variant,
            "state": self.state,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "profile_parameters": dict(thaw(self.profile_parameters)),
            "source_results": [result.to_dict() for result in self.source_results],
            "completed_sources": list(self.completed_sources),
            "empty_sources": list(self.empty_sources),
            "partial_sources": list(self.partial_sources),
            "stale_sources": list(self.stale_sources),
            "unavailable_sources": list(self.unavailable_sources),
            "timed_out_sources": list(self.timed_out_sources),
            "failed_sources": list(self.failed_sources),
            "cancelled_sources": list(self.cancelled_sources),
            "findings": [finding.to_dict() for finding in self.findings],
            "related_changes": [change.to_dict() for change in self.related_changes],
            "compatibility": self.compatibility.to_dict() if self.compatibility else {},
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "TroubleshootingSession":
        if payload.get("schema_id") != SESSION_SCHEMA_ID:
            raise ValueError("Unsupported troubleshooting session schema ID.")
        if int(payload.get("schema_version", 0)) != SESSION_SCHEMA_VERSION:
            raise ValueError("Unsupported troubleshooting session schema version.")
        parameters = payload.get("profile_parameters", {})
        source_results = payload.get("source_results", [])
        findings = payload.get("findings", [])
        changes = payload.get("related_changes", [])
        compatibility = payload.get("compatibility", {})
        if not isinstance(parameters, Mapping) or not isinstance(compatibility, Mapping):
            raise ValueError("Persisted session parameters and compatibility must be mappings.")
        if not all(isinstance(items, list) for items in (source_results, findings, changes)):
            raise ValueError("Persisted session result collections must be lists.")
        if any(not isinstance(item, Mapping) for item in (*source_results, *findings, *changes)):
            raise ValueError("Persisted session contains malformed result data.")
        profile_id = str(payload.get("profile_id", ""))
        profile = require_profile(profile_id)
        session = cls(
            session_id=str(payload.get("session_id", "")),
            profile_id=profile_id,
            profile_version=int(payload.get("profile_version", 0)),
            variant=str(payload.get("variant", "")),  # type: ignore[arg-type]
            state=str(payload.get("state", "failed")),  # type: ignore[arg-type]
            started_at=float(payload.get("started_at", 0.0)),
            completed_at=(
                float(payload["completed_at"])
                if payload.get("completed_at") is not None
                else None
            ),
            profile_parameters=profile.validate_parameters(parameters),
            source_results=tuple(SourceResult.from_dict(item) for item in source_results),
            findings=tuple(TroubleshootingFinding.from_dict(item) for item in findings),
            related_changes=tuple(RelatedChangeReference.from_dict(item) for item in changes),
            compatibility=CompatibilityMetadata.from_dict(compatibility),
        )
        derived_lists = {
            "completed_sources": session.completed_sources,
            "empty_sources": session.empty_sources,
            "partial_sources": session.partial_sources,
            "stale_sources": session.stale_sources,
            "unavailable_sources": session.unavailable_sources,
            "timed_out_sources": session.timed_out_sources,
            "failed_sources": session.failed_sources,
            "cancelled_sources": session.cancelled_sources,
        }
        for key, derived in derived_lists.items():
            if key in payload:
                persisted = payload[key]
                if not isinstance(persisted, list) or tuple(persisted) != derived:
                    raise ValueError(f"Persisted {key} does not match source results.")
        return session


@dataclass(frozen=True)
class FindingComparison:
    """Immutable outcome contract; comparison logic belongs to Phase 2."""

    original_fingerprint: str
    follow_up_fingerprint: str
    state: ComparisonState
    reason_code: str

    def __post_init__(self) -> None:
        _validate_fingerprint(
            self.original_fingerprint,
            field_name="Original finding fingerprint",
        )
        if self.follow_up_fingerprint:
            _validate_fingerprint(
                self.follow_up_fingerprint,
                field_name="Follow-up finding fingerprint",
            )
        if self.state not in _COMPARISON_STATES:
            raise ValueError(f"Unsupported comparison state: {self.state}.")
        validate_identifier(self.reason_code, field="reason_code")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "FindingComparison":
        return cls(
            str(payload.get("original_fingerprint", "")),
            str(payload.get("follow_up_fingerprint", "")),
            str(payload.get("state", "not_comparable")),  # type: ignore[arg-type]
            str(payload.get("reason_code", "")),
        )


@dataclass(frozen=True)
class TroubleshootingComparison:
    """Compatible before/after identities and bounded finding outcomes."""

    before_session_id: str
    after_session_id: str
    profile_id: str
    profile_version: int
    variant: SupportedVariant
    outcomes: tuple[FindingComparison, ...]
    comparable: bool
    reason_code: str
    schema_id: str = field(default="loofi.troubleshooting-comparison", init=False)
    schema_version: int = field(default=1, init=False)

    def __post_init__(self) -> None:
        _validate_session_id(self.before_session_id)
        _validate_session_id(self.after_session_id)
        if self.before_session_id == self.after_session_id:
            raise ValueError("A troubleshooting comparison requires two distinct sessions.")
        profile = require_profile(self.profile_id)
        if self.profile_version != profile.version:
            raise ValueError("Comparison profile version does not match the catalog.")
        if self.variant not in {"traditional", "atomic"}:
            raise ValueError("Unsupported Fedora variant.")
        validate_identifier(self.reason_code, field="reason_code")
        if len(self.outcomes) > MAX_FINDINGS:
            raise ValueError("Troubleshooting comparison exceeds the finding limit.")

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_id": self.schema_id,
            "schema_version": self.schema_version,
            "before_session_id": self.before_session_id,
            "after_session_id": self.after_session_id,
            "profile_id": self.profile_id,
            "profile_version": self.profile_version,
            "variant": self.variant,
            "outcomes": [outcome.to_dict() for outcome in self.outcomes],
            "comparable": self.comparable,
            "reason_code": self.reason_code,
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "TroubleshootingComparison":
        if payload.get("schema_id") != "loofi.troubleshooting-comparison":
            raise ValueError("Unsupported troubleshooting comparison schema ID.")
        if int(payload.get("schema_version", 0)) != 1:
            raise ValueError("Unsupported troubleshooting comparison schema version.")
        outcomes = payload.get("outcomes", [])
        if not isinstance(outcomes, list) or any(
            not isinstance(item, Mapping)
            for item in outcomes
        ):
            raise ValueError("Persisted comparison outcomes must be a list of mappings.")
        return cls(
            before_session_id=str(payload.get("before_session_id", "")),
            after_session_id=str(payload.get("after_session_id", "")),
            profile_id=str(payload.get("profile_id", "")),
            profile_version=int(payload.get("profile_version", 0)),
            variant=str(payload.get("variant", "")),  # type: ignore[arg-type]
            outcomes=tuple(FindingComparison.from_dict(item) for item in outcomes),
            comparable=bool(payload.get("comparable", False)),
            reason_code=str(payload.get("reason_code", "")),
        )
