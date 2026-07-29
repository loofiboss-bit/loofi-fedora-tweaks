"""Pure composition of adapted evidence into one terminal Compass session."""

from __future__ import annotations

from dataclasses import replace
from typing import Iterable

from core.troubleshooting.adapters import SourceChange, SourceEvidence
from core.troubleshooting.correlation import correlate_changes
from core.troubleshooting.lifecycle import finalize_session
from core.troubleshooting.models import (
    CompatibilityMetadata,
    TroubleshootingFinding,
    TroubleshootingSession,
)
from core.troubleshooting.profiles import require_profile


def compose_session(
    session: TroubleshootingSession,
    evidence: Iterable[SourceEvidence],
    *,
    completed_at: float,
    cancellation_requested: bool = False,
) -> TroubleshootingSession:
    """Finalize one running session from source-owned, already-adapted evidence."""
    if session.state != "running":
        raise ValueError("Only a running troubleshooting session can compose evidence.")
    profile = require_profile(session.profile_id)
    if completed_at - session.started_at > profile.total_budget_seconds:
        raise ValueError("Evidence composition exceeded the closed profile total budget.")
    bundles = tuple(evidence)
    source_ids = tuple(bundle.result.source_id for bundle in bundles)
    if len(source_ids) != len(set(source_ids)):
        raise ValueError("Evidence composition cannot contain duplicate sources.")

    expected = {
        budget.source_id
        for budget in profile.source_budgets
        if session.variant in budget.variants
    }
    unknown = sorted(set(source_ids) - expected)
    if unknown:
        raise ValueError(f"Evidence contains sources outside the active profile: {', '.join(unknown)}.")

    findings: list[TroubleshootingFinding] = []
    changes: list[SourceChange] = []
    source_versions: list[tuple[str, int]] = []
    for bundle in bundles:
        result = bundle.result
        budget = profile.budget_for(result.source_id, session.variant)
        if budget is None or budget.timeout_seconds != result.timeout_seconds:
            raise ValueError("Adapted evidence does not match the active profile budget.")
        if result.started_at < session.started_at or result.completed_at > completed_at:
            raise ValueError("Adapted source timing falls outside the session boundary.")
        if any(session.variant not in finding.applicable_variants for finding in bundle.findings):
            raise ValueError("Adapted findings cannot cross Fedora variants.")
        findings.extend(bundle.findings)
        changes.extend(bundle.changes)
        source_versions.append((result.source_id, bundle.schema_version))

    related = correlate_changes(findings, changes)
    finalized = finalize_session(
        session,
        completed_at=completed_at,
        source_results=tuple(bundle.result for bundle in bundles),
        findings=tuple(findings),
        related_changes=related,
        cancellation_requested=cancellation_requested,
    )
    compatibility = CompatibilityMetadata(
        finalized.profile_version,
        finalized.variant,
        tuple(sorted(source_versions)),
    )
    return replace(finalized, compatibility=compatibility)
