"""Deterministic, conservative matching of findings to source-owned changes."""

from __future__ import annotations

from collections import defaultdict
from typing import Iterable

from core.troubleshooting.adapters import SourceChange
from core.troubleshooting.models import RelatedChangeReference, TroubleshootingFinding
from core.troubleshooting.validation import MAX_RELATED_CHANGES


RELATED_WINDOW_SECONDS = 7 * 24 * 60 * 60


def correlate_changes(
    findings: Iterable[TroubleshootingFinding],
    changes: Iterable[SourceChange],
    *,
    window_seconds: float = RELATED_WINDOW_SECONDS,
    limit: int = MAX_RELATED_CHANGES,
) -> tuple[RelatedChangeReference, ...]:
    """Match only prior nearby changes and exact shared typed resources."""
    if window_seconds < 0:
        raise ValueError("Correlation window cannot be negative.")
    bounded_limit = max(0, min(int(limit), MAX_RELATED_CHANGES))
    ordered_findings = tuple(
        sorted(
            findings,
            key=lambda item: (item.collected_at, item.fingerprint),
        )
    )
    if not ordered_findings or bounded_limit == 0:
        return ()

    reasons_by_change: dict[str, set[str]] = defaultdict(set)
    change_by_id: dict[str, SourceChange] = {}
    for change in sorted(
        changes,
        key=lambda item: (-item.occurred_at, item.source_kind, item.change_id),
    ):
        for finding in ordered_findings:
            if change.occurred_at > finding.collected_at:
                continue
            distance = finding.collected_at - change.occurred_at
            if distance <= window_seconds:
                reasons_by_change[change.change_id].add("time_proximity")
            if set(change.affected_resources).intersection(finding.affected_resources):
                reasons_by_change[change.change_id].add("shared_resource")
        if reasons_by_change.get(change.change_id):
            change_by_id[change.change_id] = change

    ranked = sorted(
        change_by_id.values(),
        key=lambda item: (
            -("shared_resource" in reasons_by_change[item.change_id]),
            -("time_proximity" in reasons_by_change[item.change_id]),
            -item.occurred_at,
            item.source_kind,
            item.change_id,
        ),
    )[:bounded_limit]
    return tuple(
        RelatedChangeReference(
            change_id=change.change_id,
            source_id="change-journal",
            occurred_at=change.occurred_at,
            affected_resources=change.affected_resources,
            match_reasons=frozenset(reasons_by_change[change.change_id]),  # type: ignore[arg-type]
        )
        for change in ranked
    )
