"""Bounded Action Center history storage."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from core.state.atomic_io import advisory_lock, atomic_write_text
from core.state.paths import StatePaths

MAX_HISTORY = 100
_HISTORY_FILE = StatePaths.from_environment().data / "action_center_history.jsonl"


class ActionHistoryStore:
    """Append/read JSONL history for support bundles and diagnostics."""

    def __init__(self, path: Path | None = None):
        self.path = path or _HISTORY_FILE

    def append(self, item: dict[str, Any]) -> None:
        try:
            with advisory_lock(self.path):
                try:
                    lines = self.path.read_text(encoding="utf-8").splitlines()
                except OSError:
                    lines = []
                record = {"action_center_schema_version": 3, **item}
                lines.append(json.dumps(record, default=str))
                atomic_write_text(self.path, "\n".join(lines[-MAX_HISTORY:]) + "\n")
        except OSError:
            return

    def recent(self, limit: int = 25) -> list[dict[str, Any]]:
        try:
            lines = self.path.read_text(encoding="utf-8").splitlines()
        except OSError:
            return []
        entries: list[dict[str, Any]] = []
        for line in lines[-limit:]:
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(payload, dict):
                payload.pop("action_center_schema_version", None)
                entries.append(payload)
        return entries
