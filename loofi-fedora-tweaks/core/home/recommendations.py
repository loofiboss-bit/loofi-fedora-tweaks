"""Deterministic recommendation ordering for the canonical Home."""

from __future__ import annotations

from collections.abc import Iterable

from .models import Recommendation

_PRIORITY = {
    "state_integrity": 1,
    "action_run_review": 2,
    "system_check_partial": 3,
    "pending_reboot": 4,
    "disk_pressure": 5,
    "failed_update": 6,
    "pending_updates": 7,
    "missing_backup": 8,
    "recovery_warning": 9,
    "resolution_check": 10,
    "system_check_finding": 11,
    "repeated_health": 12,
    "action_center_review": 13,
    "source_error": 14,
    "stale_data": 15,
    "no_action": 16,
}


def recommendation_priority(kind: str) -> int:
    """Return the stable priority for a recommendation kind."""
    return _PRIORITY.get(str(kind), 100)


def ordered_recommendations(
    recommendations: Iterable[Recommendation],
) -> tuple[Recommendation, ...]:
    """Sort independently of source iteration order and object identity."""
    return tuple(
        sorted(
            recommendations,
            key=lambda item: (
                recommendation_priority(item.kind),
                item.kind,
                item.id,
                item.route_id,
            ),
        )
    )


def select_primary_recommendation(
    recommendations: Iterable[Recommendation],
) -> Recommendation | None:
    """Return one deterministic primary recommendation, if any."""
    ordered = ordered_recommendations(recommendations)
    return ordered[0] if ordered else None
