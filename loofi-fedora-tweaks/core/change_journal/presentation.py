"""PyQt-free presentation states for Activity & Recovery."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from .models import ChangeEvent, ChangeJournalSnapshot

ActivityViewState = Literal[
    "initial",
    "loading",
    "empty",
    "partial",
    "truncated",
    "loaded",
    "selected",
    "recoverable",
    "manual-only",
    "error",
]


@dataclass(frozen=True)
class ActivityPresentationState:
    """One explicit progressive-disclosure state for the journal UI."""

    state: ActivityViewState
    message: str
    table_visible: bool = False
    empty_visible: bool = False
    details_visible: bool = False
    refresh_enabled: bool = False
    recovery_review_visible: bool = False


def initial_state() -> ActivityPresentationState:
    return ActivityPresentationState(
        "initial",
        "Activity has not been loaded.",
        empty_visible=True,
    )


def loading_state() -> ActivityPresentationState:
    return ActivityPresentationState("loading", "Reading supported local sources…")


def error_state(
    message: str,
    *,
    has_snapshot: bool,
    has_events: bool = False,
) -> ActivityPresentationState:
    return ActivityPresentationState(
        "error",
        f"Activity could not be loaded: {message}",
        table_visible=has_events,
        refresh_enabled=has_snapshot,
    )


def snapshot_state(snapshot: ChangeJournalSnapshot) -> ActivityPresentationState:
    available = sum(source.availability == "available" for source in snapshot.sources)
    partial = sum(source.availability == "partial" for source in snapshot.sources)
    unavailable = sum(source.availability == "unavailable" for source in snapshot.sources)
    source_summary = (
        f"{available} source(s) ready · {partial} partial · "
        f"{unavailable} unavailable"
    )
    if not snapshot.events:
        return ActivityPresentationState(
            "empty",
            source_summary,
            empty_visible=True,
            refresh_enabled=True,
        )
    if snapshot.truncated:
        return ActivityPresentationState(
            "truncated",
            f"{source_summary} · Showing the newest 100 changes",
            table_visible=True,
            refresh_enabled=True,
        )
    if partial or unavailable:
        return ActivityPresentationState(
            "partial",
            source_summary,
            table_visible=True,
            refresh_enabled=True,
        )
    return ActivityPresentationState(
        "loaded",
        source_summary,
        table_visible=True,
        refresh_enabled=True,
    )


def selected_state(event: ChangeEvent) -> ActivityPresentationState:
    if event.recovery.kind == "action_center":
        state: ActivityViewState = "recoverable"
    elif event.recovery.kind == "manual_guidance":
        state = "manual-only"
    else:
        state = "selected"
    return ActivityPresentationState(
        state,
        "Showing the selected recorded change.",
        table_visible=True,
        details_visible=True,
        refresh_enabled=True,
        recovery_review_visible=state == "recoverable",
    )
