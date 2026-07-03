"""Bounded JSON storage for v12 health snapshots."""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any

from core.observability.privacy import redact_payload
from core.observability.snapshot import HealthSnapshot
from core.observability.trends import MaintenanceTrendAnalyzer

TIMELINE_SCHEMA_VERSION = 1
DEFAULT_RETENTION = 30
_DATA_DIR = Path(os.environ.get("XDG_DATA_HOME", os.path.expanduser("~/.local/share"))) / "loofi-fedora-tweaks"
_TIMELINE_FILE = _DATA_DIR / "health_timeline_v12.json"


class HealthTimelineStore:
    """Persist bounded health snapshots with corruption-safe reads."""

    def __init__(self, path: Path | None = None, *, retention: int = DEFAULT_RETENTION):
        self.path = path or _TIMELINE_FILE
        self.retention = max(1, retention)
        self.last_error = ""

    def load(self) -> list[HealthSnapshot]:
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            self.last_error = ""
            return []
        except (OSError, json.JSONDecodeError) as exc:
            self.last_error = f"corrupt-history: {exc}"
            return []
        snapshots = raw.get("snapshots", []) if isinstance(raw, dict) else raw
        if not isinstance(snapshots, list):
            self.last_error = "corrupt-history: snapshots is not a list"
            return []
        loaded: list[HealthSnapshot] = []
        for item in snapshots:
            if not isinstance(item, dict):
                continue
            try:
                loaded.append(HealthSnapshot.from_dict(item))
            except (TypeError, ValueError):
                continue
        self.last_error = ""
        return loaded[-self.retention :]

    def save(self, snapshots: list[HealthSnapshot]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        bounded = sorted(snapshots, key=lambda item: item.timestamp)[-self.retention :]
        payload = {
            "schema_version": TIMELINE_SCHEMA_VERSION,
            "retention": self.retention,
            "updated_at": time.time(),
            "snapshots": [snapshot.to_dict() for snapshot in bounded],
        }
        self.path.write_text(json.dumps(redact_payload(payload), indent=2, sort_keys=True), encoding="utf-8")

    def append(self, snapshot: HealthSnapshot) -> HealthSnapshot:
        snapshots = self.load()
        snapshots.append(snapshot)
        self.save(snapshots)
        return snapshot

    def collect_and_append(self, *, fedora_target: str = "44") -> HealthSnapshot:
        return self.append(HealthSnapshot.collect(fedora_target=fedora_target))

    def latest(self) -> HealthSnapshot | None:
        snapshots = self.load()
        return snapshots[-1] if snapshots else None

    def export(self, *, limit: int = 10, privacy_safe: bool = True) -> dict[str, Any]:
        snapshots = self.load()[-max(1, limit) :]
        summary = MaintenanceTrendAnalyzer(snapshots).analyze()
        return {
            "schema_version": TIMELINE_SCHEMA_VERSION,
            "retention": self.retention,
            "count": len(snapshots),
            "corrupt_history_recovered": bool(self.last_error),
            "last_error": self.last_error,
            "trend_summary": summary.to_dict(),
            "snapshots": [snapshot.to_dict(privacy_safe=privacy_safe) for snapshot in snapshots],
        }
