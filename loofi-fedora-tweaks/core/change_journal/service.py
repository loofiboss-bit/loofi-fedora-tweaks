"""Bounded composition and conservative correlation for change history."""

from __future__ import annotations

import time
import json
from collections.abc import Mapping
from typing import Any, Iterable

from core.change_journal.models import (
    ChangeEvent,
    ChangeJournalSnapshot,
    ChangeSource,
    ChangeSourceStatus,
)
from core.change_journal.sources import ChangeSourceAdapter, default_sources
from core.privacy import redact_payload

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
        until: float | None = None,
        sources: Iterable[ChangeSource] | None = None,
        statuses: Iterable[str] | None = None,
        reboot_required: bool | None = None,
        search: str | None = None,
        refresh: bool = False,
    ) -> ChangeJournalSnapshot:
        bounded_limit = min(MAX_LIMIT, max(1, int(limit)))
        selected = frozenset(sources or ())
        selected_statuses = frozenset(str(item).strip().lower() for item in (statuses or ()) if str(item).strip())
        normalized_search = str(search or "").strip().lower()[:120]
        key = (
            bounded_limit,
            since,
            until,
            tuple(sorted(selected)),
            tuple(sorted(selected_statuses)),
            reboot_required,
            normalized_search,
        )
        now = float(self.clock())
        if (
            not refresh
            and self._cache_snapshot is not None
            and self._cache_key == key
            and now - self._cache_at <= self.cache_ttl
        ):
            return self._cache_snapshot

        events_by_id: dict[str, ChangeEvent] = {}
        source_statuses: list[ChangeSourceStatus] = []
        for adapter in self.sources:
            if selected and adapter.source not in selected:
                continue
            result = adapter.collect(since=since)
            source_statuses.append(result.status)
            for event in result.events:
                if since is not None and event.occurred_at < float(since):
                    continue
                if until is not None and event.occurred_at > float(until):
                    continue
                if selected_statuses and event.state.lower() not in selected_statuses:
                    continue
                if reboot_required is not None and event.reboot_required != reboot_required:
                    continue
                if normalized_search and not self._matches_search(event, normalized_search):
                    continue
                events_by_id[event.event_id] = event
        ordered = sorted(
            events_by_id.values(),
            key=lambda event: (-event.occurred_at, event.source, event.event_id),
        )
        correlated = self._correlate(ordered)
        truncated = len(correlated) > bounded_limit
        snapshot = ChangeJournalSnapshot(
            events=tuple(correlated[:bounded_limit]),
            sources=tuple(sorted(source_statuses, key=lambda status: status.source)),
            generated_at=now,
            truncated=truncated,
        )
        self._cache_key = key
        self._cache_at = now
        self._cache_snapshot = snapshot
        return snapshot

    @staticmethod
    def _matches_search(event: ChangeEvent, query: str) -> bool:
        """Search bounded presentation facts, including action/package/resource IDs."""
        values = [event.event_id, event.source, event.summary, event.state, *event.resources]
        for facts in (event.before_facts, event.after_facts):
            values.extend(str(value) for value in facts.values())
        return query in " ".join(values).lower()

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

    def export_event(self, event_id: str, *, format: str = "json", refresh: bool = False) -> str:
        """Export one selected, already-redacted event without executable data."""
        event = self.get(event_id, refresh=refresh)
        if event is None:
            raise KeyError(event_id)
        payload = {
            "schema": "loofi.activity-export/v1",
            "event": ChangeJournalService._strip_sensitive(event.to_dict()),
        }
        if format == "json":
            return json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=True)
        if format == "markdown":
            return self._markdown_export(event)
        raise ValueError("format must be json or markdown")

    @staticmethod
    def _markdown_export(event: ChangeEvent) -> str:
        resource_lines = [f"- {resource}" for resource in event.resources] or ["- Not recorded"]
        expected_value = event.after_facts.get("expected", {})
        expected = ChangeJournalService._strip_sensitive(
            dict(expected_value) if isinstance(expected_value, Mapping) else {"value": expected_value}
        )
        before = ChangeJournalService._strip_sensitive(dict(event.before_facts))
        after = ChangeJournalService._strip_sensitive(dict(event.after_facts))
        lines = [
            "# Activity & Recovery event",
            "",
            f"- Event: `{event.event_id}`",
            f"- Source: `{event.source}`",
            f"- State: `{event.state}`",
            f"- Reboot required: `{str(event.reboot_required).lower()}`",
            "",
            "## Summary",
            "",
            event.summary,
            "",
            "## Resources",
            "",
            *resource_lines,
            "",
            "## Expected / before / after evidence",
            "",
        ]
        for label, facts in (
            ("Expected", expected),
            ("Before", before),
            ("After", after),
        ):
            lines.append(f"### {label}")
            if facts:
                lines.extend(f"- {key}: {value}" for key, value in facts.items())
            else:
                lines.append("- Not recorded")
            lines.append("")
        lines.extend(
            [
                "## Recovery",
                "",
                f"- Capability: `{event.recovery.kind}`",
                event.recovery.guidance or "Review current state in Action Center before any recovery decision.",
                "",
                "Source freshness and unavailable sources are reported in the Activity view; this export does not infer missing facts.",
                "",
            ]
        )
        return "\n".join(lines)

    @staticmethod
    def _strip_sensitive(value: Any) -> Any:
        """Remove executable vectors and secret-shaped keys from exports."""
        blocked = {
            "args",
            "command",
            "command_preview",
            "env",
            "password",
            "requested_vector",
            "secret",
            "stderr",
            "stdout",
            "token",
            "vector",
        }
        if isinstance(value, dict):
            return {
                str(key): ChangeJournalService._strip_sensitive(item)
                for key, item in value.items()
                if str(key).lower() not in blocked
            }
        if isinstance(value, list):
            return [ChangeJournalService._strip_sensitive(item) for item in value[:64]]
        if isinstance(value, tuple):
            return [ChangeJournalService._strip_sensitive(item) for item in value[:64]]
        return redact_payload({"value": value}).get("value")

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
