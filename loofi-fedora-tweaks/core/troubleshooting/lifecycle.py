"""Pure session transitions and a bounded cancellation signal."""

from __future__ import annotations

import threading
import uuid
from dataclasses import replace
from typing import Any, Mapping

from core.troubleshooting.models import (
    RelatedChangeReference,
    SessionState,
    SourceResult,
    TroubleshootingFinding,
    TroubleshootingSession,
)
from core.troubleshooting.profiles import PROFILE_VERSION, SupportedVariant, require_profile


class CancellationSignal:
    """One cooperative signal with no callback, worker, timer, or authority."""

    def __init__(self) -> None:
        self._event = threading.Event()

    def cancel(self) -> None:
        self._event.set()

    def is_cancelled(self) -> bool:
        return self._event.is_set()

    def wait(self, timeout: float) -> bool:
        return self._event.wait(max(0.0, timeout))


def new_session(
    profile_id: str,
    variant: SupportedVariant,
    *,
    started_at: float,
    parameters: Mapping[str, Any] | None = None,
    session_id: str | None = None,
) -> TroubleshootingSession:
    """Create an inert queued session after explicit caller activation."""
    profile = require_profile(profile_id)
    return TroubleshootingSession(
        session_id=session_id or str(uuid.uuid4()),
        profile_id=profile.id,
        profile_version=PROFILE_VERSION,
        variant=variant,
        state="queued",
        started_at=started_at,
        completed_at=None,
        profile_parameters=profile.validate_parameters(parameters),
    )


def start_session(
    session: TroubleshootingSession,
    *,
    started_at: float,
) -> TroubleshootingSession:
    """Transition queued to running without collecting anything."""
    if session.state != "queued":
        raise ValueError("Only a queued troubleshooting session can start.")
    return replace(session, state="running", started_at=started_at)


def finalize_session(
    session: TroubleshootingSession,
    *,
    completed_at: float,
    source_results: tuple[SourceResult, ...],
    findings: tuple[TroubleshootingFinding, ...] = (),
    related_changes: tuple[RelatedChangeReference, ...] = (),
    cancellation_requested: bool = False,
) -> TroubleshootingSession:
    """Resolve the closed success/partial/unavailable/timeout/cancellation matrix."""
    if session.state != "running":
        raise ValueError("Only a running troubleshooting session can be finalized.")
    profile = require_profile(session.profile_id)
    result_by_source = {result.source_id: result for result in source_results}
    expected = tuple(
        budget
        for budget in profile.source_budgets
        if session.variant in budget.variants
    )
    unknown = sorted(set(result_by_source) - {budget.source_id for budget in expected})
    if unknown:
        raise ValueError(f"Session contains sources outside the closed profile: {', '.join(unknown)}.")

    normalized = list(source_results)
    if cancellation_requested:
        for budget in expected:
            if budget.source_id not in result_by_source:
                normalized.append(
                    SourceResult(
                        budget.source_id,
                        "cancelled",
                        completed_at,
                        completed_at,
                        budget.timeout_seconds,
                        reason_code="session-cancelled",
                        message="Collection was cancelled before this source completed.",
                    )
                )
        state: SessionState = "cancelled"
    else:
        for budget in expected:
            if budget.source_id not in result_by_source:
                normalized.append(
                    SourceResult.unavailable(
                        budget.source_id,
                        at=completed_at,
                        timeout_seconds=budget.timeout_seconds,
                        reason_code="source-not-collected",
                        message="Required evidence was not collected.",
                    )
                )
        if normalized and all(result.state == "completed" for result in normalized):
            state = "completed"
        elif any(result.state == "completed" for result in normalized):
            state = "partial"
        elif any(result.state in {"unavailable", "timed_out"} for result in normalized):
            state = "partial"
        else:
            state = "failed"

    return replace(
        session,
        state=state,
        completed_at=completed_at,
        source_results=tuple(sorted(normalized, key=lambda result: result.source_id)),
        findings=tuple(sorted(findings, key=lambda finding: finding.fingerprint)),
        related_changes=tuple(
            sorted(related_changes, key=lambda change: (change.occurred_at, change.change_id))
        ),
    )
