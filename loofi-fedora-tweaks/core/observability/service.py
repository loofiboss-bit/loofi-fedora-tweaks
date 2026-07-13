"""Canonical observability facade shared by all entry modes."""

from __future__ import annotations

import os
import socket
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from core.diagnostics.health_timeline import HealthTimeline as MetricTimelineStore
from core.observability.timeline import HealthTimelineStore as HealthSnapshotStore
from core.state.atomic_io import StateBusyError, advisory_lock
from core.state.paths import StatePaths


@dataclass(frozen=True)
class ObservabilityStatus:
    source: str
    collected_at: float
    freshness_seconds: float | None
    schema_id: str
    schema_version: int
    retention: str
    collector_owner: str
    last_success: float | None
    last_failure: str
    next_collection: float | None
    warning: str
    recovery_status: str
    snapshot_count: int
    metric_store: str
    extra: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class ObservabilityService:
    def __init__(self, snapshot_store: HealthSnapshotStore | None = None, metric_path: str | None = None):
        self.snapshots = snapshot_store or HealthSnapshotStore()
        self.metric_path = metric_path or MetricTimelineStore.DB_PATH
        self.lease_path = StatePaths.from_environment().runtime / "collector"

    def status(self, source: str = "local") -> ObservabilityStatus:
        snapshots = self.snapshots.load()
        latest = snapshots[-1] if snapshots else None
        timestamp = latest.timestamp if latest else None
        now = time.time()
        freshness = max(0.0, now - timestamp) if timestamp else None
        warning = self.snapshots.last_error or ("stale" if freshness is not None and freshness > 86400 else "")
        return ObservabilityStatus(
            source=source, collected_at=now, freshness_seconds=freshness,
            schema_id="loofi.observability-status", schema_version=1,
            retention=f"{self.snapshots.retention} snapshots", collector_owner=self._owner(),
            last_success=timestamp, last_failure=self.snapshots.last_error, next_collection=(timestamp + 86400 if timestamp else None),
            warning=warning, recovery_status="degraded" if self.snapshots.last_error else "healthy",
            snapshot_count=len(snapshots), metric_store=self.metric_path,
        )

    def collect(self, target: str = "44", source: str = "daemon") -> ObservabilityStatus:
        try:
            with advisory_lock(self.lease_path, timeout=0.25):
                self._write_owner()
                self.snapshots.collect_and_append(fedora_target=target)
        except StateBusyError:
            status = self.status(source)
            return ObservabilityStatus(**{**status.to_dict(), "warning": "collector-busy", "recovery_status": "busy"})
        return self.status(source)

    def _write_owner(self) -> None:
        self.lease_path.parent.mkdir(parents=True, exist_ok=True)
        self.lease_path.write_text(f"{socket.gethostname()}:{os.getpid()}", encoding="utf-8")

    def _owner(self) -> str:
        try:
            return Path(self.lease_path).read_text(encoding="utf-8").strip()
        except OSError:
            return "none"
