"""Canonical observability facade shared by all entry modes."""

from __future__ import annotations

import os
import socket
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from core.diagnostics.health_timeline import HealthTimeline as MetricTimelineStore
from core.fedora_release_policy import FEDORA_RELEASE_POLICY
from core.observability.snapshot import HealthSnapshot
from core.observability.timeline import HealthTimelineStore as HealthSnapshotStore
from core.state.atomic_io import StateBusyError, advisory_lock, atomic_write_text
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
    def __init__(
        self,
        snapshot_store: HealthSnapshotStore | None = None,
        metric_path: str | None = None,
        lease_path: Path | None = None,
    ):
        self.snapshots = snapshot_store or HealthSnapshotStore()
        self.metric_path = metric_path or MetricTimelineStore.DB_PATH
        self.lease_path = lease_path or StatePaths.from_environment().runtime / "collector"

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

    def collect(self, target: str = FEDORA_RELEASE_POLICY.stable_target, source: str = "daemon") -> ObservabilityStatus:
        try:
            self.collect_snapshot(target=target, source=source)
        except StateBusyError:
            status = self.status(source)
            return ObservabilityStatus(**{**status.to_dict(), "warning": "collector-busy", "recovery_status": "busy"})
        return self.status(source)

    def collect_snapshot(self, target: str = FEDORA_RELEASE_POLICY.stable_target, source: str = "daemon") -> HealthSnapshot:
        """Collect through the shared cross-process lease and return the snapshot.

        Entry modes that need the snapshot envelope (rather than only status)
        use this method so they do not bypass the canonical collector facade.
        """

        del source  # Reserved for collection audit metadata without changing v13 snapshots.
        with advisory_lock(self.lease_path, timeout=0.25):
            self._write_owner()
            return self.snapshots.collect_and_append(fedora_target=target)

    def _write_owner(self) -> None:
        atomic_write_text(
            self.lease_path,
            f"{socket.gethostname()}:{os.getpid()}",
            keep_backup=False,
        )

    def _owner(self) -> str:
        try:
            return Path(self.lease_path).read_text(encoding="utf-8").strip()
        except OSError:
            return "none"
