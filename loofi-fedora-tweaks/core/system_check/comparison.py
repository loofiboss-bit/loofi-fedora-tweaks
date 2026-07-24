"""Deterministic, read-only comparison of compatible System Check results."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import TYPE_CHECKING, Any, Iterable, Literal, Mapping, Sequence

from core.system_check.models import SystemCheckResult, SystemFinding

if TYPE_CHECKING:
    from core.observability.snapshot import HealthSnapshot

FindingOutcomeState = Literal[
    "resolved",
    "unchanged",
    "worsened",
    "not_comparable",
]

COMPARISON_SCHEMA_ID = "loofi.system-check-comparison"
COMPARISON_SCHEMA_VERSION = 1
_TERMINAL_STATES = frozenset({"completed", "partial"})
_STATE_RANK = {
    "success": 0,
    "good": 0,
    "healthy": 0,
    "current": 0,
    "attention": 1,
    "pending": 1,
    "warning": 1,
    "error": 2,
    "blocked": 2,
    "critical": 2,
    "failed": 2,
}
_INCREASING_IS_WORSE_SUFFIXES = (
    "bytes",
    "count",
    "percent",
    "percentage",
    "usage",
)


@dataclass(frozen=True)
class FindingOutcome:
    """Outcome for one finding from the original check."""

    finding_id: str
    original_fingerprint: str
    follow_up_fingerprint: str
    title: str
    state: FindingOutcomeState
    reason_code: str
    affected_resources: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class SystemCheckComparison:
    """One bounded before/after comparison without persisted mutations."""

    before_check_id: str
    after_check_id: str
    before_completed_at: float
    after_completed_at: float
    profile_id: str
    atomic: bool
    comparable: bool
    reason_code: str
    outcomes: tuple[FindingOutcome, ...]
    unavailable_sources: tuple[str, ...] = ()
    schema_id: str = COMPARISON_SCHEMA_ID
    schema_version: int = COMPARISON_SCHEMA_VERSION

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["counts"] = {
            state: sum(outcome.state == state for outcome in self.outcomes)
            for state in (
                "resolved",
                "unchanged",
                "worsened",
                "not_comparable",
            )
        }
        return payload

    def outcome_for(self, fingerprint: str) -> FindingOutcome | None:
        return next(
            (
                outcome
                for outcome in self.outcomes
                if outcome.original_fingerprint == fingerprint
            ),
            None,
        )


def compare_results(
    before: SystemCheckResult,
    after: SystemCheckResult,
) -> SystemCheckComparison:
    """Classify every original finding using only compatible collected sources."""
    reason_code = _compatibility_reason(before, after)
    unavailable = tuple(
        sorted({error.source_id for error in after.source_errors if error.source_id})
    )
    if reason_code:
        return SystemCheckComparison(
            before.check_id,
            after.check_id,
            float(before.completed_at or 0.0),
            float(after.completed_at or 0.0),
            before.profile_id,
            before.atomic,
            False,
            reason_code,
            tuple(
                _not_comparable(finding, reason_code)
                for finding in before.findings
            ),
            unavailable,
        )

    follow_up = _group_findings(after.findings)
    outcomes: list[FindingOutcome] = []
    for finding in before.findings:
        if not _source_was_collected(after, finding.evidence.source_id):
            outcomes.append(
                _not_comparable(finding, "follow_up_source_unavailable")
            )
            continue
        candidates = follow_up.get(_identity(finding), ())
        if len(candidates) > 1:
            outcomes.append(
                _not_comparable(finding, "ambiguous_follow_up_finding")
            )
            continue
        if not candidates:
            outcomes.append(
                FindingOutcome(
                    finding.finding_id,
                    finding.fingerprint,
                    "",
                    finding.title,
                    "resolved",
                    "finding_absent_after_compatible_check",
                    finding.affected_resources,
                )
            )
            continue
        current = candidates[0]
        worsened = _is_worsened(finding, current)
        outcomes.append(
            FindingOutcome(
                finding.finding_id,
                finding.fingerprint,
                current.fingerprint,
                finding.title,
                "worsened" if worsened else "unchanged",
                (
                    "finding_severity_or_evidence_worsened"
                    if worsened
                    else "finding_still_present"
                ),
                finding.affected_resources,
            )
        )
    return SystemCheckComparison(
        before.check_id,
        after.check_id,
        float(before.completed_at or 0.0),
        float(after.completed_at or 0.0),
        before.profile_id,
        before.atomic,
        True,
        "compatible",
        tuple(sorted(outcomes, key=lambda item: item.original_fingerprint)),
        unavailable,
    )


def results_from_snapshots(
    snapshots: Iterable[HealthSnapshot],
) -> tuple[SystemCheckResult, ...]:
    """Reconstruct supported persisted checks without rewriting their store."""
    results: list[SystemCheckResult] = []
    for snapshot in snapshots:
        maintenance = snapshot.daily_maintenance
        payload = (
            maintenance.get("system_check")
            if isinstance(maintenance, Mapping)
            else None
        )
        if not isinstance(payload, Mapping):
            continue
        try:
            result = SystemCheckResult.from_dict(payload)
        except (TypeError, ValueError):
            continue
        if result.state in _TERMINAL_STATES:
            results.append(result)
    return tuple(
        sorted(
            results,
            key=lambda item: (
                float(item.completed_at or 0.0),
                item.check_id,
            ),
        )
    )


def latest_comparison(
    snapshots: Sequence[HealthSnapshot],
) -> SystemCheckComparison | None:
    """Compare the latest two supported saved results, if available."""
    results = results_from_snapshots(snapshots)
    if len(results) < 2:
        return None
    return compare_results(results[-2], results[-1])


def comparison_from_check(
    snapshots: Sequence[HealthSnapshot],
    check_id: str,
) -> SystemCheckComparison | None:
    """Compare one saved origin with the newest later supported result."""
    results = results_from_snapshots(snapshots)
    before = next(
        (result for result in results if result.check_id == str(check_id)),
        None,
    )
    if before is None:
        return None
    later = [
        result
        for result in results
        if float(result.completed_at or 0.0) > float(before.completed_at or 0.0)
    ]
    if not later:
        return None
    return compare_results(before, later[-1])


def _compatibility_reason(
    before: SystemCheckResult,
    after: SystemCheckResult,
) -> str:
    if before.state not in _TERMINAL_STATES or after.state not in _TERMINAL_STATES:
        return "non_terminal_check"
    if before.profile_id != after.profile_id:
        return "profile_mismatch"
    if before.atomic != after.atomic:
        return "fedora_variant_mismatch"
    if before.check_id == after.check_id:
        return "same_check"
    if float(after.completed_at or 0.0) <= float(before.completed_at or 0.0):
        return "invalid_check_order"
    return ""


def _identity(finding: SystemFinding) -> tuple[str, tuple[str, ...]]:
    return finding.finding_id, tuple(sorted(finding.affected_resources))


def _group_findings(
    findings: Iterable[SystemFinding],
) -> dict[tuple[str, tuple[str, ...]], tuple[SystemFinding, ...]]:
    grouped: dict[tuple[str, tuple[str, ...]], list[SystemFinding]] = {}
    for finding in findings:
        grouped.setdefault(_identity(finding), []).append(finding)
    return {
        key: tuple(sorted(values, key=lambda item: item.fingerprint))
        for key, values in grouped.items()
    }


def _source_was_collected(
    result: SystemCheckResult,
    source_id: str,
) -> bool:
    if any(error.source_id == source_id for error in result.source_errors):
        return False
    if result.completed_sources:
        return source_id in result.completed_sources
    return result.state == "completed"


def _not_comparable(
    finding: SystemFinding,
    reason_code: str,
) -> FindingOutcome:
    return FindingOutcome(
        finding.finding_id,
        finding.fingerprint,
        "",
        finding.title,
        "not_comparable",
        reason_code,
        finding.affected_resources,
    )


def _is_worsened(
    before: SystemFinding,
    after: SystemFinding,
) -> bool:
    severity_rank = {"attention": 1, "critical": 2}
    if severity_rank[after.severity] > severity_rank[before.severity]:
        return True
    old_facts = before.evidence.facts_dict()
    new_facts = after.evidence.facts_dict()
    old_state = str(old_facts.get("state", "")).lower()
    new_state = str(new_facts.get("state", "")).lower()
    if _STATE_RANK.get(new_state, 0) > _STATE_RANK.get(old_state, 0):
        return True
    for key in sorted(set(old_facts) & set(new_facts)):
        if not key.lower().endswith(_INCREASING_IS_WORSE_SUFFIXES):
            continue
        old_value = old_facts[key]
        new_value = new_facts[key]
        if (
            isinstance(old_value, (int, float))
            and not isinstance(old_value, bool)
            and isinstance(new_value, (int, float))
            and not isinstance(new_value, bool)
            and new_value > old_value
        ):
            return True
    return False
