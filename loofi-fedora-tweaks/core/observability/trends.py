"""Trend analysis for the v12 health timeline."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable

from core.observability.fingerprints import ProblemFingerprint

_STATE_RANK = {"success": 0, "preview_only": 0, "unsupported": 1, "warning": 2, "blocked": 3, "error": 4}


@dataclass(frozen=True)
class TrendSummary:
    """User-facing trend summary for maintenance health."""

    schema_version: int
    snapshot_count: int
    latest_snapshot_id: str
    new: list[ProblemFingerprint] = field(default_factory=list)
    recurring: list[ProblemFingerprint] = field(default_factory=list)
    resolved: list[ProblemFingerprint] = field(default_factory=list)
    worsening: list[str] = field(default_factory=list)
    summary: str = "No health snapshots recorded."

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "snapshot_count": self.snapshot_count,
            "latest_snapshot_id": self.latest_snapshot_id,
            "new": [item.to_dict() for item in self.new],
            "recurring": [item.to_dict() for item in self.recurring],
            "resolved": [item.to_dict() for item in self.resolved],
            "worsening": list(self.worsening),
            "summary": self.summary,
        }


class MaintenanceTrendAnalyzer:
    """Detect new, recurring, resolved, and worsening health states."""

    def __init__(self, snapshots: Iterable[Any]):
        self.snapshots = sorted(list(snapshots), key=lambda item: item.timestamp)

    def analyze(self) -> TrendSummary:
        if not self.snapshots:
            return TrendSummary(schema_version=1, snapshot_count=0, latest_snapshot_id="", summary="No health snapshots recorded.")
        latest = self.snapshots[-1]
        previous = self.snapshots[:-1]
        latest_by_id = {item.id: item for item in latest.problem_fingerprints}
        previous_ids = {item.id for snapshot in previous for item in snapshot.problem_fingerprints}
        all_counts: dict[str, int] = {}
        all_by_id: dict[str, ProblemFingerprint] = {}
        for snapshot in self.snapshots:
            for item in snapshot.problem_fingerprints:
                all_counts[item.id] = all_counts.get(item.id, 0) + 1
                all_by_id[item.id] = item

        new = [item for item_id, item in latest_by_id.items() if item_id not in previous_ids]
        recurring = [item for item_id, item in latest_by_id.items() if all_counts.get(item_id, 0) >= 2]
        resolved = [all_by_id[item_id] for item_id in previous_ids if item_id not in latest_by_id and item_id in all_by_id]
        worsening = self._worsening_cards()
        summary = self._summary_text(new, recurring, resolved, worsening)
        return TrendSummary(
            schema_version=1,
            snapshot_count=len(self.snapshots),
            latest_snapshot_id=str(latest.timestamp),
            new=new,
            recurring=recurring,
            resolved=resolved,
            worsening=worsening,
            summary=summary,
        )

    def _worsening_cards(self) -> list[str]:
        if len(self.snapshots) < 2:
            return []
        previous_cards = _cards_by_id(self.snapshots[-2])
        latest_cards = _cards_by_id(self.snapshots[-1])
        worsening: list[str] = []
        for card_id, latest in latest_cards.items():
            previous = previous_cards.get(card_id)
            if not previous:
                continue
            if _STATE_RANK.get(str(latest.get("state")), 0) > _STATE_RANK.get(str(previous.get("state")), 0):
                worsening.append(card_id)
        return worsening

    @staticmethod
    def _summary_text(
        new: list[ProblemFingerprint],
        recurring: list[ProblemFingerprint],
        resolved: list[ProblemFingerprint],
        worsening: list[str],
    ) -> str:
        if recurring:
            return f"{len(recurring)} recurring issue(s) need review."
        if new:
            return f"{len(new)} new issue(s) appeared since the previous snapshot."
        if worsening:
            return f"{len(worsening)} maintenance signal(s) worsened since the previous snapshot."
        if resolved:
            return f"{len(resolved)} issue(s) appear resolved."
        return "No recurring maintenance issues detected."


def _cards_by_id(snapshot: Any) -> dict[str, dict[str, Any]]:
    maintenance = getattr(snapshot, "daily_maintenance", {})
    cards = maintenance.get("cards", []) if isinstance(maintenance, dict) else []
    result: dict[str, dict[str, Any]] = {}
    for card in cards:
        if isinstance(card, dict) and card.get("id"):
            result[str(card["id"])] = card
    return result
