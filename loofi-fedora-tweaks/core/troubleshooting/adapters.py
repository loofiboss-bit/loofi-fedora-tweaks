"""Read-only adapters from source-owned evidence into Compass contracts."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Iterable, Mapping, Protocol, Sequence, cast

from core.troubleshooting.models import (
    NextStep,
    FindingSeverity,
    SourceResult,
    SupportedVariant,
    TroubleshootingFinding,
    TroubleshootingSession,
)
from core.troubleshooting.profiles import all_profiles, require_profile
from core.troubleshooting.validation import (
    MAX_RELATED_CHANGES,
    MAX_RESOURCES,
    validate_identifier,
    validate_resource_identifier,
)


_PROFILE_SOURCE_IDS = frozenset(
    budget.source_id
    for profile in all_profiles()
    for budget in profile.source_budgets
)
_TRADITIONAL_CHANGE_SOURCES = frozenset({"dnf5"})
_ATOMIC_CHANGE_SOURCES = frozenset({"rpm_ostree"})
_SAFE_IDENTIFIER = re.compile(r"[^a-z0-9._:-]+")


@dataclass(frozen=True)
class SourceChange:
    """One inert source-owned change candidate before conservative matching."""

    change_id: str
    source_kind: str
    occurred_at: float
    affected_resources: tuple[str, ...]

    def __post_init__(self) -> None:
        validate_identifier(self.change_id, field="change_id")
        validate_identifier(self.source_kind, field="change source")
        if self.occurred_at < 0:
            raise ValueError("Change timestamp cannot be negative.")
        if not self.affected_resources or len(self.affected_resources) > MAX_RESOURCES:
            raise ValueError("Source changes require bounded affected resources.")
        for resource in self.affected_resources:
            validate_resource_identifier(resource)


@dataclass(frozen=True)
class SourceEvidence:
    """One adapted source outcome with no collector, store, or write authority."""

    result: SourceResult
    findings: tuple[TroubleshootingFinding, ...] = ()
    changes: tuple[SourceChange, ...] = ()
    schema_version: int = 1

    def __post_init__(self) -> None:
        if self.result.source_id not in _PROFILE_SOURCE_IDS:
            raise ValueError("Evidence source is outside the closed profile catalog.")
        if self.schema_version < 1:
            raise ValueError("Evidence source schema version must be positive.")
        if len(self.changes) > MAX_RELATED_CHANGES:
            raise ValueError("Adapted source exceeds the related-change limit.")
        if self.result.state not in {"completed", "partial", "stale"} and (
            self.findings or self.changes
        ):
            raise ValueError("Sources without usable evidence cannot claim findings or changes.")
        if self.result.state == "empty" and (self.findings or self.changes):
            raise ValueError("An empty source cannot claim findings or changes.")
        if any(finding.source_id != self.result.source_id for finding in self.findings):
            raise ValueError("Adapted findings must retain their troubleshooting source ID.")
        if self.changes and self.result.source_id != "change-journal":
            raise ValueError("Only the Trusted Change Journal may provide source changes.")


class ReadOnlyEvidenceAdapter(Protocol):
    """Injected adapter boundary used by a later explicit collection surface."""

    source_id: str

    def read(self, session: TroubleshootingSession) -> SourceEvidence:
        ...


def adapt_structured_source(
    *,
    profile_id: str,
    variant: SupportedVariant,
    source_id: str,
    state: str,
    started_at: float,
    completed_at: float,
    facts: Mapping[str, Any] | None = None,
    findings: Iterable[TroubleshootingFinding] = (),
    reason_code: str = "",
    message: str = "",
    schema_version: int = 1,
) -> SourceEvidence:
    """Adapt already-structured source-owned evidence without probing or writing."""
    budget = require_profile(profile_id).budget_for(source_id, variant)
    if budget is None:
        raise ValueError("Structured evidence does not belong to this profile and variant.")
    if state == "completed":
        result = SourceResult.completed(
            source_id,
            started_at=started_at,
            completed_at=completed_at,
            timeout_seconds=budget.timeout_seconds,
            facts=facts,
        )
    elif state == "empty":
        result = SourceResult.empty(
            source_id,
            started_at=started_at,
            completed_at=completed_at,
            timeout_seconds=budget.timeout_seconds,
            facts=facts,
        )
    elif state == "partial":
        result = SourceResult.partial(
            source_id,
            started_at=started_at,
            completed_at=completed_at,
            timeout_seconds=budget.timeout_seconds,
            facts=facts,
            reason_code=reason_code,
            message=message,
        )
    elif state == "stale":
        result = SourceResult.stale(
            source_id,
            started_at=started_at,
            completed_at=completed_at,
            timeout_seconds=budget.timeout_seconds,
            facts=facts,
            reason_code=reason_code or "stale-evidence",
            message=message or "The newest source-owned evidence is stale.",
        )
    elif state in {"unavailable", "failed", "cancelled", "timed_out"}:
        result = SourceResult(
            source_id,
            state,  # type: ignore[arg-type]
            started_at,
            completed_at,
            budget.timeout_seconds,
            reason_code=reason_code,
            message=message,
        )
    else:
        raise ValueError(f"Unsupported structured evidence state: {state}.")
    return SourceEvidence(result, tuple(findings), schema_version=schema_version)


def adapt_system_check(
    result: Any,
    *,
    profile_id: str,
    variant: SupportedVariant,
) -> SourceEvidence:
    """Project one source-owned System Check result without rerunning it."""
    budget = require_profile(profile_id).budget_for("system-check", variant)
    if budget is None:
        raise ValueError("This troubleshooting profile does not use System Check.")
    started_at = float(getattr(result, "started_at", 0.0))
    completed_at = float(getattr(result, "completed_at", started_at) or started_at)
    result_variant = "atomic" if bool(getattr(result, "atomic", False)) else "traditional"
    if result_variant != variant:
        source = SourceResult.unavailable(
            "system-check",
            at=completed_at,
            timeout_seconds=budget.timeout_seconds,
            reason_code="variant-mismatch",
            message="Saved System Check evidence belongs to another Fedora variant.",
        )
        return SourceEvidence(source)
    if completed_at - started_at > budget.timeout_seconds:
        source = SourceResult(
            "system-check",
            "timed_out",
            started_at,
            completed_at,
            budget.timeout_seconds,
            reason_code="source-timeout",
            message="System Check evidence exceeded the Compass source budget.",
        )
        return SourceEvidence(source)

    state = str(getattr(result, "state", "failed"))
    converted = tuple(
        _system_finding(item, variant)
        for item in getattr(result, "findings", ())
        if variant in getattr(item, "applicable_variants", ())
    )
    facts = {
        "check_id": str(getattr(result, "check_id", "")),
        "profile_id": str(getattr(result, "profile_id", "")),
        "finding_count": len(converted),
        "completed_source_count": len(getattr(result, "completed_sources", ())),
        "source_error_count": len(getattr(result, "source_errors", ())),
    }
    if state == "completed":
        source = (
            SourceResult.completed(
                "system-check",
                started_at=started_at,
                completed_at=completed_at,
                timeout_seconds=budget.timeout_seconds,
                facts=facts,
            )
            if converted
            else SourceResult.empty(
                "system-check",
                started_at=started_at,
                completed_at=completed_at,
                timeout_seconds=budget.timeout_seconds,
                facts=facts,
            )
        )
    elif state == "partial":
        source = SourceResult.partial(
            "system-check",
            started_at=started_at,
            completed_at=completed_at,
            timeout_seconds=budget.timeout_seconds,
            facts=facts,
            reason_code="system-check-partial",
            message="System Check retained partial source-owned evidence.",
        )
    elif state == "cancelled":
        source = SourceResult(
            "system-check",
            "cancelled",
            started_at,
            completed_at,
            budget.timeout_seconds,
            reason_code="system-check-cancelled",
            message="System Check collection was cancelled.",
        )
        converted = ()
    elif state == "failed":
        source = SourceResult(
            "system-check",
            "failed",
            started_at,
            completed_at,
            budget.timeout_seconds,
            reason_code="system-check-failed",
            message="System Check did not retain usable evidence.",
        )
        converted = ()
    else:
        source = SourceResult.unavailable(
            "system-check",
            at=completed_at,
            timeout_seconds=budget.timeout_seconds,
            reason_code="system-check-non-terminal",
            message="Only terminal System Check evidence can be composed.",
        )
        converted = ()
    return SourceEvidence(source, converted, schema_version=int(getattr(result, "schema_version", 1)))


def adapt_observability(
    snapshots: Sequence[Any],
    *,
    profile_id: str,
    variant: SupportedVariant,
    started_at: float,
    completed_at: float,
    last_error: str = "",
    stale_after_seconds: float = 24 * 60 * 60,
) -> SourceEvidence:
    """Project compatible saved health snapshots and trends without store writes."""
    budget = require_profile(profile_id).budget_for("observability", variant)
    if budget is None:
        raise ValueError("This troubleshooting profile does not use observability.")
    if last_error:
        state = "unavailable" if last_error.startswith("future-schema") else "failed"
        return adapt_structured_source(
            profile_id=profile_id,
            variant=variant,
            source_id="observability",
            state=state,
            started_at=started_at,
            completed_at=completed_at,
            reason_code="observability-read-failed",
            message="Saved observability evidence could not be read safely.",
        )
    compatible = tuple(
        snapshot
        for snapshot in snapshots
        if bool(getattr(snapshot, "atomic", False)) == (variant == "atomic")
    )
    if not compatible:
        return adapt_structured_source(
            profile_id=profile_id,
            variant=variant,
            source_id="observability",
            state="empty" if not snapshots else "unavailable",
            started_at=started_at,
            completed_at=completed_at,
            facts={"snapshot_count": 0},
            reason_code="" if not snapshots else "variant-mismatch",
            message="" if not snapshots else "Saved observability evidence belongs to another Fedora variant.",
        )

    from core.observability.trends import MaintenanceTrendAnalyzer

    ordered = tuple(sorted(compatible, key=lambda item: float(getattr(item, "timestamp", 0.0))))
    latest = ordered[-1]
    trend = MaintenanceTrendAnalyzer(ordered).analyze()
    latest_at = float(getattr(latest, "timestamp", 0.0))
    stale = completed_at - latest_at > stale_after_seconds
    facts = {
        "snapshot_count": len(ordered),
        "latest_timestamp": latest_at,
        "new_count": len(trend.new),
        "recurring_count": len(trend.recurring),
        "resolved_count": len(trend.resolved),
        "worsening_count": len(trend.worsening),
    }
    findings = tuple(
        _observability_finding(item, variant, latest_at, stale)
        for item in getattr(latest, "problem_fingerprints", ())
    )
    state = "stale" if stale else ("completed" if findings else "empty")
    return adapt_structured_source(
        profile_id=profile_id,
        variant=variant,
        source_id="observability",
        state=state,
        started_at=started_at,
        completed_at=completed_at,
        facts=facts,
        findings=findings,
        reason_code="stale-evidence" if stale else "",
        message="The newest saved observability snapshot is stale." if stale else "",
        schema_version=int(getattr(latest, "schema_version", 1)),
    )


def adapt_change_journal(
    snapshot: Any,
    *,
    profile_id: str,
    variant: SupportedVariant,
    started_at: float,
    completed_at: float,
) -> SourceEvidence:
    """Project a Trusted Change Journal snapshot into bounded change candidates."""
    budget = require_profile(profile_id).budget_for("change-journal", variant)
    if budget is None:
        raise ValueError("This troubleshooting profile does not use the change journal.")
    statuses = tuple(getattr(snapshot, "sources", ()))
    available = [item for item in statuses if getattr(item, "availability", "") == "available"]
    degraded = [item for item in statuses if getattr(item, "availability", "") != "available"]
    changes = tuple(
        _journal_change(event)
        for event in getattr(snapshot, "events", ())
        if _change_matches_variant(str(getattr(event, "source", "")), variant)
    )[:MAX_RELATED_CHANGES]
    facts = {
        "event_count": len(changes),
        "source_count": len(statuses),
        "degraded_source_count": len(degraded),
        "truncated": bool(getattr(snapshot, "truncated", False)),
    }
    if degraded:
        state = "partial" if available or changes else "unavailable"
        reason_code = "change-journal-partial" if state == "partial" else "change-journal-unavailable"
        message = "Trusted Change Journal retained partial source readiness."
    else:
        state = "completed" if changes else "empty"
        reason_code = ""
        message = ""
    result = adapt_structured_source(
        profile_id=profile_id,
        variant=variant,
        source_id="change-journal",
        state=state,
        started_at=started_at,
        completed_at=completed_at,
        facts=facts if state != "unavailable" else None,
        reason_code=reason_code,
        message=message,
    ).result
    return SourceEvidence(result, changes=changes if state in {"completed", "partial"} else ())


def adapt_action_center(
    plans: Sequence[Any],
    runs: Sequence[Any],
    *,
    profile_id: str,
    variant: SupportedVariant,
    started_at: float,
    completed_at: float,
    schema_version: int = 4,
) -> SourceEvidence:
    """Project supported plan/run facts without migration, execution, or verification."""
    findings: list[TroubleshootingFinding] = []
    for plan in plans:
        if variant not in getattr(plan, "supported_variants", ()) or getattr(plan, "state", "") not in {
            "blocked",
            "needs_review",
        }:
            continue
        findings.append(_action_finding(plan, variant, completed_at, is_run=False))
    for run in runs:
        if variant not in getattr(run, "supported_variants", ()) or getattr(run, "state", "") not in {
            "failed",
            "verification_failed",
            "interrupted",
        }:
            continue
        findings.append(_action_finding(run, variant, completed_at, is_run=True))
    return adapt_structured_source(
        profile_id=profile_id,
        variant=variant,
        source_id="action-center",
        state="completed" if findings else "empty",
        started_at=started_at,
        completed_at=completed_at,
        facts={
            "plan_count": len(plans),
            "run_count": len(runs),
            "finding_count": len(findings),
        },
        findings=tuple(findings),
        schema_version=schema_version,
    )


def _system_finding(finding: Any, variant: SupportedVariant) -> TroubleshootingFinding:
    if getattr(finding, "action_id", ""):
        next_step = NextStep.action(
            str(finding.action_id),
            getattr(finding, "parameters_dict")(),
            reason_code="system-check-action",
        )
    elif getattr(finding, "route_id", ""):
        next_step = NextStep.navigation(
            str(finding.route_id),
            reason_code="system-check-route",
        )
    elif getattr(finding, "manual_guidance", ""):
        next_step = NextStep.manual(
            str(finding.manual_guidance),
            reason_code=str(getattr(finding, "manual_reason_code", "") or "manual-review"),
        )
    else:
        next_step = NextStep.none(reason_code="no-safe-next-step")
    evidence = dict(getattr(getattr(finding, "evidence", None), "facts_dict")())
    evidence["finding_id"] = str(getattr(finding, "finding_id", "system-check-finding"))
    resources = _bounded_resources(
        getattr(finding, "affected_resources", ()),
        fallback=f"source:{_identifier(str(getattr(getattr(finding, 'evidence', None), 'source_id', 'system-check')))}",
    )
    return TroubleshootingFinding.build(
        finding_type=_identifier(str(getattr(finding, "finding_id", "system-check-finding"))),
        category=_identifier(str(getattr(finding, "category", "system"))),
        severity=cast(FindingSeverity, str(getattr(finding, "severity", "attention"))),
        title=str(getattr(finding, "title", "System Check finding")),
        summary=str(getattr(finding, "summary", "System Check retained a finding.")),
        evidence_explanation="This finding is adapted from the source-owned System Check result.",
        source_id="system-check",
        collected_at=float(getattr(getattr(finding, "evidence", None), "collected_at", 0.0)),
        freshness=str(getattr(finding, "freshness_state", "unknown")),  # type: ignore[arg-type]
        evidence_quality="supported",
        applicable_variants=frozenset({variant}),
        affected_resources=resources,
        evidence=evidence,
        next_step=next_step,
    )


def _observability_finding(
    item: Any,
    variant: SupportedVariant,
    collected_at: float,
    stale: bool,
) -> TroubleshootingFinding:
    severity: FindingSeverity = "critical" if str(getattr(item, "severity", "")).lower() in {
        "blocked",
        "critical",
        "error",
    } else "attention"
    kind = _identifier(str(getattr(item, "kind", "observability-signal")))
    source = _identifier(str(getattr(item, "source_id", "observability")))
    evidence = dict(getattr(item, "evidence", {}) or {})
    evidence["signal_id"] = str(getattr(item, "id", kind))
    return TroubleshootingFinding.build(
        finding_type=kind,
        category="observability",
        severity=severity,
        title=str(getattr(item, "title", "Saved health signal")),
        summary=str(getattr(item, "summary", "Saved observability evidence needs review.")),
        evidence_explanation="The latest compatible saved health snapshot contains this signal.",
        source_id="observability",
        collected_at=collected_at,
        freshness="stale" if stale else "fresh",
        evidence_quality="limited" if stale else "supported",
        applicable_variants=frozenset({variant}),
        affected_resources=(f"signal:{source}",),
        evidence=evidence,
        next_step=NextStep.navigation("health", reason_code="review-saved-health"),
    )


def _journal_change(event: Any) -> SourceChange:
    resources = _bounded_resources(
        getattr(event, "resources", ()),
        fallback=f"change-source:{_identifier(str(getattr(event, 'source', 'change-journal')))}",
    )
    return SourceChange(
        change_id=_identifier(str(getattr(event, "event_id", ""))),
        source_kind=_identifier(str(getattr(event, "source", "change-journal"))),
        occurred_at=float(getattr(event, "occurred_at", 0.0)),
        affected_resources=resources,
    )


def _change_matches_variant(source: str, variant: SupportedVariant) -> bool:
    if source in _TRADITIONAL_CHANGE_SOURCES:
        return variant == "traditional"
    if source in _ATOMIC_CHANGE_SOURCES:
        return variant == "atomic"
    return True


def _action_finding(
    item: Any,
    variant: SupportedVariant,
    collected_at: float,
    *,
    is_run: bool,
) -> TroubleshootingFinding:
    action_id = _identifier(str(getattr(item, "action_id", "unknown-action")))
    state = _identifier(str(getattr(item, "state", "needs-review")))
    resources = _bounded_resources(
        getattr(item, "affected_resources", ()),
        fallback=f"action:{action_id}",
    )
    record_id = str(getattr(item, "run_id" if is_run else "plan_id", ""))
    return TroubleshootingFinding.build(
        finding_type="action-run-needs-review" if is_run else "action-plan-needs-review",
        category="action-center",
        severity="critical" if state == "verification_failed" else "attention",
        title="Action run needs review" if is_run else "Action plan needs review",
        summary=f"{action_id} is {state.replace('_', ' ')}.",
        evidence_explanation="This is a read-only reference to the source-owned Action Center record.",
        source_id="action-center",
        collected_at=collected_at,
        freshness="fresh",
        evidence_quality="confirmed",
        applicable_variants=frozenset({variant}),
        affected_resources=resources,
        evidence={
            "action_id": action_id,
            "record_id": record_id,
            "record_kind": "run" if is_run else "plan",
            "state": state,
        },
        next_step=NextStep.navigation(
            "maintenance:action-center",
            reason_code="review-action-record",
        ),
    )


def _identifier(value: str) -> str:
    candidate = _SAFE_IDENTIFIER.sub("-", value.strip().lower()).strip("-.:_")
    return candidate[:128] or "unknown"


def _bounded_resources(values: Iterable[Any], *, fallback: str) -> tuple[str, ...]:
    resources: list[str] = []
    for value in values:
        candidate = str(value)
        try:
            validate_resource_identifier(candidate)
        except ValueError:
            continue
        if candidate not in resources:
            resources.append(candidate)
        if len(resources) == MAX_RESOURCES:
            break
    return tuple(resources) or (fallback,)
