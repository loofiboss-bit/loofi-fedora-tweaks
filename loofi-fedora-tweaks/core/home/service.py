"""Read-only composition of existing trusted sources for Home."""

from __future__ import annotations

import re
import time
from collections.abc import Callable, Mapping, Sequence
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from core.actions.stores import ActionPlanStore, ActionRunStore
from core.observability.timeline import HealthTimelineStore
from core.observability.trends import MaintenanceTrendAnalyzer
from core.state.doctor import StateDoctor
from utils.history import HistoryManager

from .models import (
    AttentionItem,
    HomeDataState,
    HomeOverallState,
    HomeSummary,
    HomeTask,
    RecentChange,
    Recommendation,
)
from .recommendations import ordered_recommendations, select_primary_recommendation

_STALE_AFTER_SECONDS = 24 * 60 * 60
_PROBLEM_STATES = frozenset({"blocked", "critical", "error", "failed"})
_ATTENTION_STATES = frozenset({"attention", "pending", "updates_available", "warning"})
_UPDATE_PENDING_STATES = frozenset({"attention", "pending", "updates_available"})

_COMMON_TASKS = (
    HomeTask("updates", "Update the system", "Review available Fedora updates.", "maintenance:updates", "update"),
    HomeTask("applications", "Install an application", "Find and install Fedora or Flatpak apps.", "software:apps", "packages-software"),
    HomeTask("performance", "Check performance", "Inspect CPU, memory, and running processes.", "monitor", "overview-dashboard"),
    HomeTask("protection", "Protect or recover", "Review backups and recovery options.", "backup", "storage-disk"),
)


class HomeService:
    """Compose Home without collecting metrics or invoking mutating services."""

    def __init__(
        self,
        *,
        snapshot_store: Any | None = None,
        state_source: Any | None = None,
        plan_store: Any | None = None,
        run_store: Any | None = None,
        history_source: Any | None = None,
        notification_source: Any | None = None,
        clock: Callable[[], float] = time.time,
        stale_after_seconds: float = _STALE_AFTER_SECONDS,
    ) -> None:
        self.snapshot_store = snapshot_store or HealthTimelineStore()
        self.state_source = state_source or StateDoctor()
        self.plan_store = plan_store or ActionPlanStore()
        self.run_store = run_store or ActionRunStore()
        if history_source is not None:
            self.history_source = history_source
        elif Path(HistoryManager.HISTORY_FILE).exists():
            self.history_source = HistoryManager()
        else:
            self.history_source = None
        if notification_source is not None:
            self.notification_source = notification_source
        else:
            self.notification_source = self._default_notification_source()
        self.clock = clock
        self.stale_after_seconds = max(0.0, float(stale_after_seconds))

    def summary(self) -> HomeSummary:
        """Read persisted sources once and return a bounded Home payload."""
        now = float(self.clock())
        errors: list[str] = []
        snapshots = self._read_source("health snapshots", self.snapshot_store.load, errors, default=[])
        store_error = str(getattr(self.snapshot_store, "last_error", "") or "")
        if store_error:
            errors.append(f"health snapshots: {store_error}")
        for snapshot in snapshots:
            for error in getattr(snapshot, "collection_errors", ()):
                if error:
                    errors.append(f"health snapshot: {error}")
        state = self._read_source("state integrity", self.state_source.run, errors, default={})
        plans = self._read_source("Action Center plans", lambda: self.plan_store.list(limit=25), errors, default=[])
        runs = self._read_source("Action Center runs", lambda: self.run_store.list(limit=25), errors, default=[])
        history = self._read_history(errors)
        notifications = self._read_notifications(errors)

        latest = max(snapshots, key=lambda item: float(getattr(item, "timestamp", 0.0)), default=None)
        data_state = self._data_state(now, latest, errors)
        recommendations = self._recommendations(now, snapshots, latest, state, plans, runs)
        if not recommendations and data_state == "error":
            recommendations.append(Recommendation(
                "home-source-error", "source_error", "Home data needs attention",
                "Some saved status sources could not be read. Review system health before making changes.",
                "maintenance:health-timeline", "attention",
            ))
        elif not recommendations and data_state == "stale":
            recommendations.append(Recommendation(
                "home-stale", "stale_data", "Refresh system health",
                "The latest saved health snapshot is more than 24 hours old.",
                "maintenance:health-timeline", "attention",
            ))
        elif not recommendations and data_state == "fresh":
            recommendations.append(Recommendation(
                "home-good", "no_action", "No action required",
                "Saved health and maintenance signals do not need attention.",
                "maintenance:health-timeline", "info",
            ))

        ordered = ordered_recommendations(recommendations)
        primary = select_primary_recommendation(ordered)
        attention = tuple(
            AttentionItem(item.id, item.title, item.summary, item.route_id, item.severity)
            for item in ordered
            if item is not primary and item.kind != "no_action"
        )[:3]
        overall = self._overall_state(data_state, primary)
        return HomeSummary(
            overall_state=overall,
            data_state=data_state,
            summary=self._summary_text(data_state, primary),
            generated_at=datetime.fromtimestamp(now, timezone.utc),
            primary_recommendation=primary,
            attention_items=attention,
            common_tasks=_COMMON_TASKS,
            recent_change=self._recent_activity(history, notifications),
            source_errors=tuple(dict.fromkeys(errors)),
        )

    @staticmethod
    def _read_source(label: str, reader: Callable[[], Any], errors: list[str], *, default: Any) -> Any:
        try:
            return reader()
        except (OSError, RuntimeError, TypeError, ValueError) as exc:
            errors.append(f"{label}: {exc}")
            return default

    def _read_history(self, errors: list[str]) -> list[Any]:
        if self.history_source is None:
            return []
        return list(self._read_source("recent changes", lambda: self.history_source.get_recent(count=1), errors, default=[]))

    def _read_notifications(self, errors: list[str]) -> list[Any]:
        if self.notification_source is None:
            return []
        return list(
            self._read_source(
                "recent notifications",
                lambda: self.notification_source.get_recent(limit=1),
                errors,
                default=[],
            )
        )

    @staticmethod
    def _default_notification_source() -> Any | None:
        """Open existing local notification history only when Home is loaded."""
        try:
            from utils.notification_center import NOTIFICATIONS_FILE, NotificationCenter

            return NotificationCenter() if NOTIFICATIONS_FILE.exists() else None
        except (OSError, RuntimeError, TypeError, ValueError):
            return None

    def _data_state(
        self,
        now: float,
        latest: Any | None,
        errors: Sequence[str],
    ) -> HomeDataState:
        if errors:
            return "error"
        if latest is not None:
            age = max(0.0, now - float(getattr(latest, "timestamp", 0.0)))
            return "stale" if age > self.stale_after_seconds else "fresh"
        return "empty"

    def _recommendations(
        self,
        now: float,
        snapshots: Sequence[Any],
        latest: Any | None,
        state: Mapping[str, Any],
        plans: Sequence[Any],
        runs: Sequence[Any],
    ) -> list[Recommendation]:
        items: list[Recommendation] = []
        findings = [item for item in state.get("findings", []) if isinstance(item, Mapping)]
        critical_findings = [item for item in findings if str(item.get("severity", "")) == "error"]
        if critical_findings:
            first = critical_findings[0]
            items.append(Recommendation(
                "state-integrity", "state_integrity", "Repair Loofi state",
                str(first.get("summary") or "Local application state failed validation."),
                "settings:repair", "critical", len(critical_findings),
            ))

        problematic_runs = [
            run for run in runs
            if str(getattr(run, "state", "")) in {"failed", "interrupted", "verification_failed"}
        ]
        if problematic_runs:
            latest_run = max(problematic_runs, key=lambda run: float(getattr(run, "updated_at", 0.0)))
            run_state = str(getattr(latest_run, "state", ""))
            items.append(Recommendation(
                "action-run-review", "action_run_review", "Review verified maintenance",
                f"The latest Action Center run is {run_state.replace('_', ' ')} and requires manual review.",
                "maintenance:action-center", "critical", len(problematic_runs),
            ))

        if latest is not None:
            cards = self._card_map(latest)
            if self._pending_reboot(latest, cards):
                items.append(Recommendation(
                    "pending-reboot", "pending_reboot", "Restart to finish an existing operation",
                    "A completed system operation is waiting for a reboot.",
                    "maintenance:updates", "attention",
                ))
            disk = self._mapping(getattr(latest, "disk_usage_summary", {})) or cards.get("disk-usage", {})
            if self._disk_pressure(disk):
                items.append(Recommendation(
                    "disk-pressure", "disk_pressure", "Free disk space",
                    str(disk.get("summary") or "Root filesystem usage is critically high."),
                    "storage", "critical",
                ))
            update = cards.get("system-updates", {})
            package = self._mapping(getattr(latest, "package_manager_health_summary", {})) or cards.get("package-health", {})
            if self._state(update) in _PROBLEM_STATES or self._state(package) in _PROBLEM_STATES:
                items.append(Recommendation(
                    "failed-update", "failed_update", "Review update health",
                    str(package.get("summary") or update.get("summary") or "An update or package operation needs review."),
                    "maintenance:updates", "critical",
                ))
            elif self._state(update) in _UPDATE_PENDING_STATES or int(update.get("pending_count", 0) or 0) > 0:
                items.append(Recommendation(
                    "pending-updates", "pending_updates", "Review system updates",
                    str(update.get("summary") or "Important system updates are available."),
                    "maintenance:updates", "attention",
                ))
            protection = self._mapping(getattr(latest, "rollback_snapshot_availability", {})) or cards.get("rollback", {})
            if protection and self._state(protection) in _PROBLEM_STATES:
                items.append(Recommendation(
                    "incomplete-recovery", "failed_update", "Review incomplete recovery",
                    str(protection.get("summary") or "A recovery operation needs review."),
                    "backup", "critical",
                ))
            elif protection and self._state(protection) in (_ATTENTION_STATES | {"unsupported"}):
                items.append(Recommendation(
                    "missing-backup", "missing_backup", "Review recovery protection",
                    str(protection.get("summary") or "No current recovery protection was found."),
                    "backup", "attention",
                ))

        if len(snapshots) >= 2:
            trend = MaintenanceTrendAnalyzer(snapshots).analyze()
            if trend.recurring or trend.worsening:
                items.append(Recommendation(
                    "repeated-health", "repeated_health", "Review recurring system health issues",
                    trend.summary, "maintenance:health-timeline", "attention",
                    len(trend.recurring) + len(trend.worsening),
                ))

        ready_plans = [
            plan for plan in plans
            if str(getattr(plan, "state", "")) in {"ready", "needs_review"}
            and float(getattr(plan, "expires_at", 0.0) or 0.0) > now
        ]
        candidate_count = 0
        if latest is not None:
            action_summary = self._mapping(getattr(latest, "action_center_summary", {}))
            candidate_count = max(0, int(action_summary.get("candidate_count", 0) or 0))
        review_count = max(len(ready_plans), candidate_count)
        if review_count:
            items.append(Recommendation(
                "action-center-review", "action_center_review", "Review maintenance options",
                f"Action Center has {review_count} item(s) ready for explicit review.",
                "maintenance:action-center", "attention", review_count,
            ))
        return items

    @staticmethod
    def _mapping(value: Any) -> dict[str, Any]:
        return dict(value) if isinstance(value, Mapping) else {}

    @classmethod
    def _card_map(cls, snapshot: Any) -> dict[str, dict[str, Any]]:
        maintenance = cls._mapping(getattr(snapshot, "daily_maintenance", {}))
        cards = maintenance.get("cards", [])
        if not isinstance(cards, list):
            return {}
        return {
            str(card["id"]): dict(card)
            for card in cards
            if isinstance(card, Mapping) and card.get("id")
        }

    @staticmethod
    def _state(value: Mapping[str, Any]) -> str:
        return str(value.get("state", "")).strip().lower()

    @classmethod
    def _pending_reboot(cls, snapshot: Any, cards: Mapping[str, Mapping[str, Any]]) -> bool:
        maintenance = cls._mapping(getattr(snapshot, "daily_maintenance", {}))
        if bool(maintenance.get("pending_reboot")):
            return True
        return any(cls._state(card) in {"pending_reboot", "reboot_required"} for card in cards.values())

    @classmethod
    def _disk_pressure(cls, disk: Mapping[str, Any]) -> bool:
        if cls._state(disk) in {"blocked", "critical", "error"}:
            return True
        text = " ".join(str(disk.get(key, "")) for key in ("summary", "details"))
        percentages = [int(value) for value in re.findall(r"(?<!\d)(\d{1,3})%", text)]
        return bool(percentages and max(percentages) >= 90)

    @staticmethod
    def _recent_activity(history: Sequence[Any], notifications: Sequence[Any]) -> RecentChange | None:
        entry = history[0] if history else None
        raw_timestamp = str(getattr(entry, "timestamp", "") or "")
        try:
            occurred_at = datetime.fromisoformat(raw_timestamp) if raw_timestamp else None
        except ValueError:
            occurred_at = None
        history_timestamp = HomeService._datetime_timestamp(occurred_at)

        notification = notifications[0] if notifications else None
        try:
            notification_timestamp = float(getattr(notification, "timestamp", 0.0) or 0.0)
        except (TypeError, ValueError):
            notification_timestamp = 0.0

        if notification is not None and (entry is None or notification_timestamp > history_timestamp):
            title = str(getattr(notification, "title", "") or "").strip()
            message = str(getattr(notification, "message", "") or "").strip()
            description = ": ".join(part for part in (title, message) if part) or "Recent notification"
            return RecentChange(
                id=f"notification:{getattr(notification, 'id', 'recent')}",
                description=description,
                occurred_at=(
                    datetime.fromtimestamp(notification_timestamp, timezone.utc)
                    if notification_timestamp > 0.0
                    else None
                ),
                undo_available=False,
            )
        if entry is None:
            return None
        return RecentChange(
            id=str(getattr(entry, "id", "recent-change")),
            description=str(getattr(entry, "description", "Recent change")),
            occurred_at=occurred_at,
            undo_available=bool(getattr(entry, "undo_command", [])),
        )

    @staticmethod
    def _datetime_timestamp(value: datetime | None) -> float:
        if value is None:
            return 0.0
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.timestamp()

    @staticmethod
    def _overall_state(
        data_state: HomeDataState,
        primary: Recommendation | None,
    ) -> HomeOverallState:
        if primary and primary.severity == "critical":
            return "critical"
        if primary and primary.kind != "no_action":
            return "attention"
        if data_state == "fresh":
            return "good"
        return "unknown"

    @staticmethod
    def _summary_text(data_state: HomeDataState, primary: Recommendation | None) -> str:
        if primary is not None:
            return primary.summary
        if data_state == "empty":
            return "No saved system health snapshot is available yet."
        return "System status is not available."
