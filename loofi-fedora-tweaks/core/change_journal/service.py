"""Bounded composition and conservative correlation for change history."""

from __future__ import annotations

import time
from typing import Any, Iterable

from core.change_journal.models import (
    ChangeEvent,
    ChangeJournalSnapshot,
    ChangeSource,
)
from core.change_journal.sources import ChangeSourceAdapter, default_sources

DEFAULT_LIMIT = 100
MAX_LIMIT = 500
DEFAULT_CACHE_TTL = 15.0
RELATED_WINDOW_SECONDS = 7 * 24 * 60 * 60


class ChangeJournalService:
    """Compose source-owned records without creating a third durable store."""

    def __init__(
        self,
        *,
        sources: Iterable[ChangeSourceAdapter] | None = None,
        clock: Any = time.time,
        cache_ttl: float = DEFAULT_CACHE_TTL,
    ):
        self.sources = tuple(sources) if sources is not None else default_sources()
        self.clock = clock
        self.cache_ttl = max(0.0, float(cache_ttl))
        self._cache_key: tuple[Any, ...] | None = None
        self._cache_at = 0.0
        self._cache_snapshot: ChangeJournalSnapshot | None = None

    def snapshot(
        self,
        *,
        limit: int = DEFAULT_LIMIT,
        since: float | None = None,
        sources: Iterable[ChangeSource] | None = None,
        refresh: bool = False,
    ) -> ChangeJournalSnapshot:
        bounded_limit = min(MAX_LIMIT, max(1, int(limit)))
        selected = frozenset(sources or ())
        key = (bounded_limit, since, tuple(sorted(selected)))
        now = float(self.clock())
        if (
            not refresh
            and self._cache_snapshot is not None
            and self._cache_key == key
            and now - self._cache_at <= self.cache_ttl
        ):
            return self._cache_snapshot

        events_by_id: dict[str, ChangeEvent] = {}
        statuses = []
        for adapter in self.sources:
            if selected and adapter.source not in selected:
                continue
            result = adapter.collect(since=since)
            statuses.append(result.status)
            for event in result.events:
                events_by_id[event.event_id] = event
        ordered = sorted(
            events_by_id.values(),
            key=lambda event: (-event.occurred_at, event.source, event.event_id),
        )
        correlated = self._correlate(ordered)
        truncated = len(correlated) > bounded_limit
        snapshot = ChangeJournalSnapshot(
            events=tuple(correlated[:bounded_limit]),
            sources=tuple(sorted(statuses, key=lambda status: status.source)),
            generated_at=now,
            truncated=truncated,
        )
        self._cache_key = key
        self._cache_at = now
        self._cache_snapshot = snapshot
        return snapshot

    def get(self, event_id: str, *, refresh: bool = False) -> ChangeEvent | None:
        snapshot = self.snapshot(limit=MAX_LIMIT, refresh=refresh)
        return next(
            (event for event in snapshot.events if event.event_id == event_id),
            None,
        )

    def related(
        self,
        event_id: str,
        *,
        limit: int = 20,
        refresh: bool = False,
    ) -> tuple[ChangeEvent, ...]:
        snapshot = self.snapshot(limit=MAX_LIMIT, refresh=refresh)
        event = next(
            (candidate for candidate in snapshot.events if candidate.event_id == event_id),
            None,
        )
        if event is None:
            return ()
        related_ids = set(event.correlation_ids)
        return tuple(
            candidate
            for candidate in snapshot.events
            if candidate.event_id in related_ids
        )[: max(0, int(limit))]

    @staticmethod
    def _correlate(events: list[ChangeEvent]) -> list[ChangeEvent]:
        correlations: dict[str, list[str]] = {event.event_id: [] for event in events}
        for index, left in enumerate(events):
            left_resources = set(left.resources)
            if not left_resources:
                continue
            for right in events[index + 1 :]:
                if abs(left.occurred_at - right.occurred_at) > RELATED_WINDOW_SECONDS:
                    continue
                if left.source == right.source:
                    continue
                if left_resources.intersection(right.resources):
                    correlations[left.event_id].append(right.event_id)
                    correlations[right.event_id].append(left.event_id)
        return [
            event.with_correlations(tuple(correlations[event.event_id]))
            for event in events
        ]
