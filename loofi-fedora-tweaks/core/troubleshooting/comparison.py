"""Compatible before/after comparison for Compass troubleshooting sessions."""

from __future__ import annotations

from collections import defaultdict
from typing import Iterable

from core.troubleshooting.models import (
    FindingComparison,
    TroubleshootingComparison,
    TroubleshootingFinding,
    TroubleshootingSession,
)


_TERMINAL_EVIDENCE_STATES = frozenset({"completed", "partial"})
_SEVERITY_RANK = {"info": 0, "attention": 1, "critical": 2}
_STATE_RANK = {
    "success": 0,
    "healthy": 0,
    "current": 0,
    "attention": 1,
    "pending": 1,
    "warning": 1,
    "blocked": 2,
    "critical": 2,
    "error": 2,
    "failed": 2,
}
_INCREASING_IS_WORSE_SUFFIXES = (
    "bytes",
    "count",
    "percent",
    "percentage",
    "usage",
)


def compare_sessions(
    before: TroubleshootingSession,
    after: TroubleshootingSession,
) -> TroubleshootingComparison:
    """Classify original findings using only compatible follow-up evidence."""
    incompatibility = _compatibility_reason(before, after)
    if incompatibility:
        return _comparison(
            before,
            after,
            tuple(
                FindingComparison(
                    finding.fingerprint,
                    "",
                    "not_comparable",
                    incompatibility,
                )
                for finding in before.findings
            ),
            comparable=False,
            reason_code=incompatibility,
        )

    after_sources = {result.source_id: result for result in after.source_results}
    before_versions = dict(before.compatibility.source_versions if before.compatibility else ())
    after_versions = dict(after.compatibility.source_versions if after.compatibility else ())
    grouped = _group_findings(after.findings)
    outcomes: list[FindingComparison] = []
    for finding in before.findings:
        follow_up_source = after_sources.get(finding.source_id)
        if follow_up_source is None or follow_up_source.state not in {"completed", "empty"}:
            outcomes.append(_not_comparable(finding, "follow-up-source-unavailable"))
            continue
        if (
            finding.source_id in before_versions
            and finding.source_id in after_versions
            and before_versions[finding.source_id] != after_versions[finding.source_id]
        ):
            outcomes.append(_not_comparable(finding, "source-schema-mismatch"))
            continue
        candidates = grouped.get(_identity(finding), ())
        if len(candidates) > 1:
            outcomes.append(_not_comparable(finding, "ambiguous-follow-up-finding"))
        elif not candidates:
            outcomes.append(
                FindingComparison(
                    finding.fingerprint,
                    "",
                    "resolved",
                    "finding-absent-after-compatible-session",
                )
            )
        else:
            current = candidates[0]
            worsened = _is_worsened(finding, current)
            outcomes.append(
                FindingComparison(
                    finding.fingerprint,
                    current.fingerprint,
                    "worsened" if worsened else "unchanged",
                    "finding-worsened" if worsened else "finding-still-present",
                )
            )

    ordered = tuple(sorted(outcomes, key=lambda item: item.original_fingerprint))
    incomplete = (
        before.state != "completed"
        or after.state != "completed"
        or any(item.state == "not_comparable" for item in ordered)
    )
    return _comparison(
        before,
        after,
        ordered,
        comparable=not incomplete,
        reason_code="partial-evidence" if incomplete else "compatible",
    )


def _comparison(
    before: TroubleshootingSession,
    after: TroubleshootingSession,
    outcomes: tuple[FindingComparison, ...],
    *,
    comparable: bool,
    reason_code: str,
) -> TroubleshootingComparison:
    return TroubleshootingComparison(
        before.session_id,
        after.session_id,
        before.profile_id,
        before.profile_version,
        before.variant,
        outcomes,
        comparable,
        reason_code,
    )


def _compatibility_reason(
    before: TroubleshootingSession,
    after: TroubleshootingSession,
) -> str:
    if before.state not in _TERMINAL_EVIDENCE_STATES or after.state not in _TERMINAL_EVIDENCE_STATES:
        return "non-terminal-evidence"
    if before.profile_id != after.profile_id or before.profile_version != after.profile_version:
        return "profile-mismatch"
    if before.variant != after.variant:
        return "fedora-variant-mismatch"
    if before.session_id == after.session_id:
        return "same-session"
    if float(after.completed_at or 0.0) <= float(before.completed_at or 0.0):
        return "invalid-session-order"
    return ""


def _identity(finding: TroubleshootingFinding) -> tuple[str, str, tuple[str, ...]]:
    return (
        finding.finding_type,
        finding.source_id,
        tuple(sorted(finding.affected_resources)),
    )


def _group_findings(
    findings: Iterable[TroubleshootingFinding],
) -> dict[tuple[str, str, tuple[str, ...]], tuple[TroubleshootingFinding, ...]]:
    grouped: dict[
        tuple[str, str, tuple[str, ...]],
        list[TroubleshootingFinding],
    ] = defaultdict(list)
    for finding in findings:
        grouped[_identity(finding)].append(finding)
    return {
        identity: tuple(sorted(values, key=lambda item: item.fingerprint))
        for identity, values in grouped.items()
    }


def _not_comparable(
    finding: TroubleshootingFinding,
    reason_code: str,
) -> FindingComparison:
    return FindingComparison(
        finding.fingerprint,
        "",
        "not_comparable",
        reason_code,
    )


def _is_worsened(
    before: TroubleshootingFinding,
    after: TroubleshootingFinding,
) -> bool:
    if _SEVERITY_RANK[after.severity] > _SEVERITY_RANK[before.severity]:
        return True
    old_facts = before.evidence_dict()
    new_facts = after.evidence_dict()
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
