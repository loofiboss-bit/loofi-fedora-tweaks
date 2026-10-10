"""Read-only suggestions derived from collected observations, never commands."""
from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime
from typing import Mapping

from core.tasks.update_flow import STALE_SECONDS, UPDATE_ACTION_SOURCES


@dataclass(frozen=True)
class NextStepContext:
    """Inert, typed identifiers for an existing destination."""
    run_id: str = ""
    update_source: str = ""
    symptom: str = ""

    def to_dict(self) -> dict[str, str]:
        values = (("run_id", self.run_id), ("update_source", self.update_source), ("symptom", self.symptom))
        return {key: value for key, value in values if value}


@dataclass(frozen=True)
class NextStep:
    id: str
    title: str
    reason: str
    route: str
    button: str
    sampled_at: float | None = None
    context: NextStepContext | None = None


def _timestamp(value: object) -> float | None:
    if isinstance(value, datetime):
        value = value.timestamp()
    if isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value) and value > 0:
        return float(value)
    return None


def _fresh(value: object, now: float) -> bool:
    stamp = _timestamp(value)
    return stamp is not None and 0 <= now - stamp <= STALE_SECONDS


def next_steps(maintenance: Mapping, metrics=(), *, now: float) -> tuple[NextStep, ...]:
    """Return at most three navigation-only suggestions in priority order."""
    result: list[NextStep] = []
    activity = maintenance.get("activity", {})
    runs = activity.get("runs", ()) or (activity,)
    pending = [run for run in runs if run.get("status") in {"awaiting_reboot", "verifying"}]
    failed = [run for run in runs if run.get("status") in {"failed", "verification_failed", "interrupted"}]
    for identifier, candidates, title, button in (
        ("pending", pending, "Continue verification", "Review verification"),
        ("failed", failed, "Review unsuccessful changes", "Review changes"),
    ):
        if candidates:
            latest = max(candidates, key=lambda run: _timestamp(run.get("sampled_at")) or 0)
            route = "maintenance:updates" if str(latest.get("action_id", latest.get("detail", ""))) in UPDATE_ACTION_SOURCES else "changes"
            source = UPDATE_ACTION_SOURCES.get(str(latest.get("action_id", latest.get("detail", ""))), "")
            run_id = latest.get("run_id", "")
            context = NextStepContext(run_id=run_id if isinstance(run_id, str) else "", update_source=source)
            if identifier == "failed" and source:
                route = "health"
            result.append(NextStep(identifier, title, str(latest.get("action_id", latest.get("detail", ""))),
                                   route, button, _timestamp(latest.get("sampled_at")), context))
    if activity.get("status") == "error":
        result.append(NextStep("history-error", "Review unreadable activity", str(activity.get("detail", "Saved activity is unreadable")),
                               "changes", "Open activity"))

    health_check = None
    health = maintenance.get("health", {})
    stamp = health.get("sampled_at")
    critical = [item for item in health.get("findings", ()) if isinstance(item, Mapping) and item.get("severity") == "critical"]
    # Match System Check's root-filesystem critical pressure threshold (95%).
    root_pressure = next((metric for metric in metrics if metric.id == "storage:/" and metric.status == "ready"
                          and metric.value is not None and metric.value >= 95 and _fresh(metric.sampled_at, now)), None)
    fresh_critical = [finding for finding in critical if finding.get("freshness_state") == "fresh"]
    if root_pressure is not None:
        result.append(NextStep("health", "Review critical health findings", "Root filesystem needs attention",
                               "health", "Open Health", _timestamp(root_pressure.sampled_at), NextStepContext(symptom="storage_full")))
    elif fresh_critical and _fresh(stamp, now):
        result.append(NextStep("health", "Review critical health findings", str(fresh_critical[0].get("summary", "Critical health findings recorded")),
                               "health", "Open Health", _timestamp(stamp)))
    elif health.get("status") not in {"completed", "partial"} or not _fresh(stamp, now) or critical:
        health_check = NextStep("health-check", "Check system health", str(health.get("detail") or "No recent health check"),
                                "health", "Run a check", _timestamp(stamp))

    update_check = None
    updates = maintenance.get("updates", {})
    sources = updates.get("sources", ())
    available = [source for source in sources if source.get("status") == "available" and not source.get("stale", True)
                 and _fresh(source.get("sampled_at"), now) and source.get("count", 0) > 0]
    if updates.get("status") != "error" and available:
        result.append(NextStep("updates", "Updates are available", "Review available system, app or firmware updates",
                               "maintenance:updates", "Review updates", max(_timestamp(source.get("sampled_at")) or 0 for source in available)))
    elif updates.get("status") == "error" or not sources or any(source.get("stale", True) or not _fresh(source.get("sampled_at"), now)
                                                                or source.get("status") in {"unchecked", "error"} for source in sources):
        update_check = NextStep("update-check", "Check for updates", str(updates.get("detail") or "No recent update check"),
                                "maintenance:updates", "Check updates", _timestamp(updates.get("sampled_at")))
    result.extend(step for step in (health_check, update_check) if step is not None)
    return tuple(result[:3])
