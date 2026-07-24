"""Read-only composition for the canonical System Check presentation."""

from __future__ import annotations

import sqlite3
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterable

from core.diagnostics.health_timeline import HealthTimeline
from core.observability.snapshot import HealthSnapshot
from core.observability.timeline import HealthTimelineStore
from core.system_check.comparison import (
    SystemCheckComparison,
    comparison_from_check,
    latest_comparison,
)
from core.system_check.handoff import evidence_digest
from core.system_check.mappings import mapped_action, validate_finding
from core.system_check.models import SystemFinding

PRESENTATION_SCHEMA_ID = "loofi.system-check"
PRESENTATION_SCHEMA_VERSION = 1


@dataclass(frozen=True)
class FindingView:
    """Privacy-safe finding fields used by GUI and CLI readers."""

    finding_id: str
    fingerprint: str
    category: str
    severity: str
    title: str
    summary: str
    freshness_state: str
    route_id: str
    action_id: str
    affected_resources: tuple[str, ...]
    manual_guidance: str = ""
    manual_reason_code: str = ""
    evidence_digest: str = ""


@dataclass(frozen=True)
class HistoryView:
    """One persisted snapshot with deterministic before/after counts."""

    timestamp: float
    source: str
    state: str
    check_id: str
    finding_count: int
    new_count: int
    recurring_count: int
    resolved_count: int


@dataclass(frozen=True)
class MetricView:
    """Read-only summary of one legacy SQLite metric series."""

    metric_type: str
    minimum: float
    maximum: float
    average: float
    count: int
    unit: str
    last_timestamp: str


@dataclass(frozen=True)
class MaintenanceOutcomeView:
    """Separate Action Center verification and follow-up finding outcome."""

    run_id: str
    plan_id: str
    action_id: str
    check_id: str
    finding_fingerprint: str
    verification_state: str
    resolution_state: str
    resolution_reason_code: str
    reboot_required: bool
    affected_resources: tuple[str, ...]
    updated_at: float


@dataclass(frozen=True)
class SystemCheckPageState:
    """Stable versioned state shared by the canonical GUI and CLI."""

    latest_check_id: str
    latest_state: str
    latest_completed_at: float | None
    atomic: bool | None
    findings: tuple[FindingView, ...]
    history: tuple[HistoryView, ...]
    metrics: tuple[MetricView, ...]
    unavailable_sources: tuple[str, ...]
    snapshot_error: str
    metric_error: str
    comparison: SystemCheckComparison | None = None
    maintenance_outcomes: tuple[MaintenanceOutcomeView, ...] = ()
    schema_id: str = PRESENTATION_SCHEMA_ID
    schema_version: int = PRESENTATION_SCHEMA_VERSION

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def envelope(self, command: str) -> dict[str, Any]:
        return {
            "schema_id": self.schema_id,
            "schema_version": self.schema_version,
            "command": str(command),
            "data": self.to_dict(),
        }


class SystemCheckPresentationService:
    """Compose both v18 stores without collecting or migrating metric data."""

    def __init__(
        self,
        *,
        snapshot_store: HealthTimelineStore | None = None,
        metric_path: str | Path | None = None,
        run_store: Any | None = None,
    ) -> None:
        self.snapshot_store = snapshot_store or HealthTimelineStore()
        self.metric_path = Path(metric_path or HealthTimeline.DB_PATH)
        self.run_store = run_store

    def load(self, *, history_limit: int = 30) -> SystemCheckPageState:
        snapshots = self.snapshot_store.load()
        latest_check = next(
            (
                payload
                for snapshot in reversed(snapshots)
                if (payload := _system_check_payload(snapshot)) is not None
            ),
            None,
        )
        findings = _finding_views(latest_check)
        source_errors = latest_check.get("source_errors", []) if latest_check else []
        unavailable = tuple(
            sorted(
                {
                    str(item.get("source_id", ""))
                    for item in source_errors
                    if isinstance(item, dict) and item.get("source_id")
                }
            )
        )
        metrics, metric_error = self._metric_views()
        comparison = latest_comparison(snapshots)
        runs = []
        if self.run_store is not None:
            try:
                runs = self.run_store.list_read_only(limit=25)
            except (OSError, RuntimeError, TypeError, ValueError):
                runs = []
        return SystemCheckPageState(
            latest_check_id=str(latest_check.get("check_id", "")) if latest_check else "",
            latest_state=str(latest_check.get("state", "unavailable")) if latest_check else "unavailable",
            latest_completed_at=_optional_float(latest_check.get("completed_at")) if latest_check else None,
            atomic=bool(latest_check.get("atomic")) if latest_check else None,
            findings=findings,
            history=_history_views(snapshots, history_limit),
            metrics=metrics,
            unavailable_sources=unavailable,
            snapshot_error=_error_reason(self.snapshot_store.last_error),
            metric_error=metric_error,
            comparison=comparison,
            maintenance_outcomes=_maintenance_outcome_views(
                runs,
                comparison,
                snapshots=snapshots,
            ),
        )

    def _metric_views(self) -> tuple[tuple[MetricView, ...], str]:
        if not self.metric_path.exists():
            return (), ""
        uri = f"file:{self.metric_path.resolve()}?mode=ro"
        try:
            with sqlite3.connect(uri, uri=True, timeout=1.0) as connection:
                rows = connection.execute(
                    """
                    SELECT metric_type, MIN(value), MAX(value), AVG(value),
                           COUNT(*), COALESCE(MAX(unit), ''), MAX(timestamp)
                    FROM metrics
                    GROUP BY metric_type
                    ORDER BY metric_type
                    """
                ).fetchall()
        except (OSError, sqlite3.Error):
            return (), "metric-store-unavailable"
        return (
            tuple(
                MetricView(
                    metric_type=str(row[0]),
                    minimum=float(row[1]),
                    maximum=float(row[2]),
                    average=float(row[3]),
                    count=int(row[4]),
                    unit=str(row[5] or ""),
                    last_timestamp=str(row[6] or ""),
                )
                for row in rows
            ),
            "",
        )


def _optional_float(value: Any) -> float | None:
    try:
        return float(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _error_reason(value: Any) -> str:
    """Return a stable reason code without leaking local paths or payloads."""
    return str(value or "").partition(":")[0].strip()


def _system_check_payload(snapshot: HealthSnapshot) -> dict[str, Any] | None:
    maintenance = snapshot.daily_maintenance
    payload = maintenance.get("system_check") if isinstance(maintenance, dict) else None
    if not isinstance(payload, dict) or int(payload.get("schema_version", 0)) != 1:
        return None
    return payload


def _finding_views(payload: dict[str, Any] | None) -> tuple[FindingView, ...]:
    raw_findings = payload.get("findings", []) if payload else []
    if not isinstance(raw_findings, list):
        return ()
    findings: list[FindingView] = []
    for item in raw_findings:
        if not isinstance(item, dict):
            continue
        try:
            finding = SystemFinding.from_dict(item)
            validate_finding(finding)
        except (TypeError, ValueError):
            continue
        mapped_id, mapped_parameters = mapped_action(
            finding.finding_id,
            finding.evidence.facts_dict(),
            atomic=bool(payload.get("atomic", False)) if payload else False,
        )
        reviewable_action = (
            finding.action_id
            if (
                finding.freshness_state == "fresh"
                and mapped_id == finding.action_id
                and mapped_parameters == finding.parameters_dict()
            )
            else ""
        )
        findings.append(
            FindingView(
                finding_id=finding.finding_id,
                fingerprint=finding.fingerprint,
                category=finding.category,
                severity=finding.severity,
                title=finding.title,
                summary=finding.summary,
                freshness_state=finding.freshness_state,
                route_id=finding.route_id,
                action_id=reviewable_action,
                affected_resources=finding.affected_resources,
                manual_guidance=finding.manual_guidance,
                manual_reason_code=finding.manual_reason_code,
                evidence_digest=evidence_digest(finding),
            )
        )
    return tuple(sorted(findings, key=lambda finding: (finding.severity != "critical", finding.title, finding.fingerprint)))


def _maintenance_outcome_views(
    runs: Iterable[Any],
    comparison: SystemCheckComparison | None,
    *,
    snapshots: Iterable[HealthSnapshot] = (),
) -> tuple[MaintenanceOutcomeView, ...]:
    saved_snapshots = tuple(snapshots)
    views: list[MaintenanceOutcomeView] = []
    for run in runs:
        context = getattr(run, "finding_context", None)
        if context is None:
            continue
        run_state = str(getattr(run, "state", ""))
        reboot_required = bool(getattr(run, "reboot_required", False))
        verification_state = {
            "succeeded": "verified",
            "awaiting_reboot": "pending_reboot",
            "verification_failed": "verification_failed",
        }.get(run_state, "not_verified")
        resolution_state = "not_comparable"
        resolution_reason = "follow_up_check_required"
        linked_comparison = (
            comparison_from_check(
                saved_snapshots,
                context.check_result_id,
            )
            if saved_snapshots
            else comparison
        )
        if reboot_required or run_state == "awaiting_reboot":
            resolution_reason = "pending_reboot"
        elif (
            linked_comparison is not None
            and linked_comparison.before_check_id == context.check_result_id
            and linked_comparison.after_completed_at
            > float(getattr(run, "last_verified_at", 0.0) or 0.0)
        ):
            outcome = linked_comparison.outcome_for(
                context.finding_fingerprint
            )
            if outcome is not None:
                resolution_state = outcome.state
                resolution_reason = outcome.reason_code
        views.append(
            MaintenanceOutcomeView(
                run_id=str(getattr(run, "run_id", "")),
                plan_id=str(getattr(run, "plan_id", "")),
                action_id=str(getattr(run, "action_id", "")),
                check_id=context.check_result_id,
                finding_fingerprint=context.finding_fingerprint,
                verification_state=verification_state,
                resolution_state=resolution_state,
                resolution_reason_code=resolution_reason,
                reboot_required=reboot_required,
                affected_resources=tuple(context.affected_resources),
                updated_at=float(getattr(run, "updated_at", 0.0) or 0.0),
            )
        )
    return tuple(
        sorted(
            views,
            key=lambda item: (item.updated_at, item.run_id),
            reverse=True,
        )
    )


def _snapshot_fingerprints(snapshot: HealthSnapshot) -> frozenset[str]:
    payload = _system_check_payload(snapshot)
    if payload is not None:
        return frozenset(
            str(item.get("fingerprint"))
            for item in payload.get("findings", [])
            if isinstance(item, dict) and item.get("fingerprint")
        )
    return frozenset(item.id for item in snapshot.problem_fingerprints if item.id)


def _history_views(
    snapshots: Iterable[HealthSnapshot],
    limit: int,
) -> tuple[HistoryView, ...]:
    previous: frozenset[str] = frozenset()
    history: list[HistoryView] = []
    for snapshot in sorted(snapshots, key=lambda item: item.timestamp):
        payload = _system_check_payload(snapshot)
        current = _snapshot_fingerprints(snapshot)
        new = current - previous
        recurring = current & previous
        resolved = previous - current
        history.append(
            HistoryView(
                timestamp=float(snapshot.timestamp),
                source="system-check" if payload is not None else "health-snapshot",
                state=str(payload.get("state", "recorded")) if payload else "recorded",
                check_id=str(payload.get("check_id", "")) if payload else "",
                finding_count=len(current),
                new_count=len(new),
                recurring_count=len(recurring),
                resolved_count=len(resolved),
            )
        )
        previous = current
    return tuple(reversed(history[-max(1, int(limit)) :]))
