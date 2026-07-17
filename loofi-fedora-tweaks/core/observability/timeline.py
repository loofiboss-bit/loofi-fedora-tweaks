"""Bounded JSON storage for v12 health snapshots."""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from core.observability.privacy import redact_payload
from core.observability.snapshot import HealthSnapshot
from core.observability.trends import MaintenanceTrendAnalyzer
from core.state.atomic_io import advisory_lock, atomic_write_json
from core.state.migrations import MigrationRunner
from core.state.paths import StatePaths
from core.state.schema import SchemaRegistry, UnsupportedFutureSchema

TIMELINE_SCHEMA_VERSION = 1
DEFAULT_RETENTION = 30
_TIMELINE_FILE = StatePaths.from_environment().data / "health_timeline_v12.json"


class HealthTimelineStore:
    """Persist bounded health snapshots with corruption-safe reads."""

    def __init__(
        self,
        path: Path | None = None,
        *,
        retention: int = DEFAULT_RETENTION,
        registry: SchemaRegistry | None = None,
    ):
        self.path = path or _TIMELINE_FILE
        self.retention = max(1, retention)
        self.last_error = ""
        self.registry = registry or self._registry()
        self.migrations = MigrationRunner(self.registry)

    def load(self) -> list[HealthSnapshot]:
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
            if isinstance(raw, dict):
                # The runner validates future schemas without writing them and
                # atomically advances supported older documents when needed.
                raw = self.migrations.migrate_json("loofi.health-snapshots", self.path)
        except FileNotFoundError:
            self.last_error = ""
            return []
        except UnsupportedFutureSchema as exc:
            self.last_error = f"future-schema-read-only: {exc}"
            return []
        except ValueError as exc:
            self.last_error = f"corrupt-history: {exc}"
            return []
        except (OSError, json.JSONDecodeError) as exc:
            self.last_error = f"corrupt-history: {exc}"
            return []
        return self._decode(raw)

    def _decode(self, raw: Any) -> list[HealthSnapshot]:
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
        with advisory_lock(self.path):
            self._assert_writable_schema()
            self._save_unlocked(snapshots)

    def append(self, snapshot: HealthSnapshot) -> HealthSnapshot:
        # The read/bound/write sequence is one critical section. Locking only
        # save() loses snapshots when GUI, CLI and daemon append concurrently.
        with advisory_lock(self.path):
            self._assert_writable_schema()
            try:
                raw = json.loads(self.path.read_text(encoding="utf-8"))
            except FileNotFoundError:
                snapshots: list[HealthSnapshot] = []
            except (OSError, json.JSONDecodeError):
                snapshots = []
            else:
                if isinstance(raw, dict):
                    raw = self.registry.migrate("loofi.health-snapshots", raw)
                snapshots = self._decode(raw)
            snapshots.append(snapshot)
            self._save_unlocked(snapshots)
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

    def _save_unlocked(self, snapshots: list[HealthSnapshot]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        bounded = sorted(snapshots, key=lambda item: item.timestamp)[-self.retention :]
        payload = {
            "schema_version": TIMELINE_SCHEMA_VERSION,
            "retention": self.retention,
            "updated_at": time.time(),
            "snapshots": [snapshot.to_dict() for snapshot in bounded],
        }
        atomic_write_json(self.path, redact_payload(payload))

    def _assert_writable_schema(self) -> None:
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return
        except (OSError, json.JSONDecodeError):
            return
        if isinstance(raw, dict):
            version = int(raw.get("schema_version", 0))
            self.registry.validate_version("loofi.health-snapshots", version)

    @staticmethod
    def _registry() -> SchemaRegistry:
        registry = SchemaRegistry()
        registry.register("loofi.health-snapshots", TIMELINE_SCHEMA_VERSION)
        registry.add_migration(
            "loofi.health-snapshots",
            0,
            lambda payload: {**payload, "schema_version": TIMELINE_SCHEMA_VERSION},
        )
        return registry
