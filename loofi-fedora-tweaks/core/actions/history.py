"""Bounded Action Center history storage."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

MAX_HISTORY = 100
_DATA_DIR = Path(os.environ.get("XDG_DATA_HOME", os.path.expanduser("~/.local/share"))) / "loofi-fedora-tweaks"
_HISTORY_FILE = _DATA_DIR / "action_center_history.jsonl"


class ActionHistoryStore:
    """Append/read JSONL history for support bundles and diagnostics."""

    def __init__(self, path: Path | None = None):
        self.path = path or _HISTORY_FILE

    def append(self, item: dict[str, Any]) -> None:
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with self.path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(item, default=str) + "\n")
            self._trim()
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
                entries.append(payload)
        return entries

    def _trim(self) -> None:
        try:
            lines = self.path.read_text(encoding="utf-8").splitlines()
        except OSError:
            return
        if len(lines) <= MAX_HISTORY:
            return
        self.path.write_text("\n".join(lines[-MAX_HISTORY:]) + "\n", encoding="utf-8")
