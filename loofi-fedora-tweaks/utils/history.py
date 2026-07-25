"""Typed, non-executable application activity history.

The pre-v20 format persisted arbitrary ``undo_command`` vectors and later
executed them.  That made a user-writable JSON file an execution boundary.
Version 2 deliberately stores descriptions and closed Action Center recovery
references only.  Legacy command vectors are never deserialized into the
runtime model and are never executed.
"""

from __future__ import annotations

import json
import logging
import os
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, List, Mapping

from core.privacy import redact_payload, redact_text
from core.state.atomic_io import advisory_lock, atomic_write_bytes, atomic_write_json
from utils.containers import Result

logger = logging.getLogger(__name__)

HISTORY_SCHEMA_VERSION = 2
MAX_HISTORY_ENTRIES = 50


class HistoryVersionError(ValueError):
    """Raised when history was written by a newer, unsupported application."""


@dataclass(frozen=True)
class HistoryEntry:
    """One inert application activity record."""

    id: str
    timestamp: str
    description: str
    source: str = "loofi_app"
    recovery_action_id: str | None = None
    recovery_parameters: dict[str, Any] = field(default_factory=dict)

    @property
    def undo_command(self) -> tuple[()]:
        """Compatibility view proving that persisted commands are inert."""
        return ()

    @staticmethod
    def from_dict(data: Mapping[str, Any]) -> "HistoryEntry":
        """Create a bounded, redacted entry from persisted data."""
        raw_parameters = data.get("recovery_parameters", {})
        parameters = (
            redact_payload(dict(raw_parameters))
            if isinstance(raw_parameters, Mapping)
            else {}
        )
        action_id = str(data.get("recovery_action_id", "") or "").strip()
        return HistoryEntry(
            id=str(data.get("id", "") or str(uuid.uuid4())[:8])[:128],
            timestamp=str(data.get("timestamp", ""))[:64],
            description=redact_text(str(data.get("description", "")), limit=500),
            source=str(data.get("source", "loofi_app") or "loofi_app")[:64],
            recovery_action_id=action_id[:128] or None,
            recovery_parameters=dict(parameters),
        )

    def to_dict(self) -> dict[str, Any]:
        """Serialize without executable command data."""
        return {
            "id": self.id,
            "timestamp": self.timestamp,
            "description": self.description,
            "source": self.source,
            "recovery_action_id": self.recovery_action_id,
            "recovery_parameters": dict(self.recovery_parameters),
        }


class HistoryManager:
    """Atomic compatibility store for Loofi-owned application activity."""

    HISTORY_FILE = os.path.expanduser("~/.config/loofi-fedora-tweaks/history.json")

    def __init__(self):
        Path(self.HISTORY_FILE).parent.mkdir(parents=True, exist_ok=True, mode=0o700)

    def log_change(
        self,
        description: str,
        undo_command: object | None = None,
        *,
        source: str = "loofi_app",
        recovery_action_id: str | None = None,
        recovery_parameters: Mapping[str, Any] | None = None,
    ) -> None:
        """Store inert activity metadata.

        ``undo_command`` remains accepted only so older in-process callers do
        not crash during migration.  Its value is intentionally discarded.
        Recoverable host changes must reference a registered Action Center
        definition through ``recovery_action_id``.
        """
        if undo_command:
            logger.info(
                "Discarded legacy executable undo data for history entry: %s",
                redact_text(description, limit=200),
            )
        entry = HistoryEntry(
            id=str(uuid.uuid4())[:8],
            timestamp=datetime.now(timezone.utc).isoformat(),
            description=redact_text(str(description), limit=500),
            source=str(source or "loofi_app")[:64],
            recovery_action_id=(
                str(recovery_action_id)[:128] if recovery_action_id else None
            ),
            recovery_parameters=dict(
                redact_payload(dict(recovery_parameters or {}))
            ),
        )
        history = self._load_entries()
        history.append(entry)
        self._save_entries(history[-MAX_HISTORY_ENTRIES:])

    def get_last_action(self) -> dict[str, Any] | None:
        """Return the newest inert entry as a compatibility mapping."""
        history = self._load_entries()
        return history[-1].to_dict() if history else None

    def get_recent(self, count: int = 3) -> List[HistoryEntry]:
        """Return the newest bounded activity entries first."""
        bounded = max(0, int(count))
        history = self._load_entries()
        return list(reversed(history[-bounded:])) if bounded else []

    def can_undo(self) -> bool:
        """Return whether a closed Action Center recovery is available."""
        return any(entry.recovery_action_id for entry in self._load_entries())

    def undo_last_action(self) -> Result:
        """Reject direct undo and direct users to reviewed recovery."""
        history = self._load_entries()
        if not history:
            return Result(False, "No actions to recover.")
        return self._recovery_result(history[-1])

    def undo_action(self, action_id: str) -> Result:
        """Reject direct undo for one entry and expose safe guidance."""
        target = next(
            (entry for entry in self._load_entries() if entry.id == action_id),
            None,
        )
        if target is None:
            return Result(False, f"Action not found: {action_id}")
        return self._recovery_result(target)

    @staticmethod
    def _recovery_result(entry: HistoryEntry) -> Result:
        if entry.recovery_action_id:
            return Result(
                False,
                "Recovery requires a new reviewed Action Center plan.",
                data={
                    "recovery_action_id": entry.recovery_action_id,
                    "recovery_parameters": dict(entry.recovery_parameters),
                },
            )
        return Result(
            False,
            "Direct undo is retired. Review Activity & Recovery for safe guidance.",
        )

    def _path(self) -> Path:
        return Path(self.HISTORY_FILE)

    def _load_entries(self) -> list[HistoryEntry]:
        path = self._path()
        if not path.exists():
            return []
        with advisory_lock(path):
            try:
                raw_bytes = path.read_bytes()
                payload = json.loads(raw_bytes.decode("utf-8"))
            except (OSError, UnicodeDecodeError, json.JSONDecodeError):
                return []

            legacy = isinstance(payload, list)
            if legacy:
                raw_entries = payload
            elif isinstance(payload, Mapping):
                version = int(payload.get("schema_version", 0))
                if version > HISTORY_SCHEMA_VERSION:
                    raise HistoryVersionError(
                        f"Unsupported history schema version: {version}"
                    )
                if version != HISTORY_SCHEMA_VERSION:
                    return []
                raw_entries = payload.get("entries", [])
            else:
                return []

            if not isinstance(raw_entries, list):
                return []
            entries = [
                HistoryEntry.from_dict(item)
                for item in raw_entries[-MAX_HISTORY_ENTRIES:]
                if isinstance(item, Mapping)
            ]
            if legacy:
                self._migrate_legacy_unlocked(path, raw_bytes, entries)
            return entries

    def _migrate_legacy_unlocked(
        self,
        path: Path,
        raw_bytes: bytes,
        entries: list[HistoryEntry],
    ) -> None:
        backup = path.with_name("history.v1.json.bak")
        if not backup.exists():
            atomic_write_bytes(
                backup,
                raw_bytes,
                mode=0o600,
                keep_backup=False,
            )
        self._write_unlocked(path, entries)

    def _save_entries(self, entries: list[HistoryEntry]) -> None:
        path = self._path()
        with advisory_lock(path):
            self._write_unlocked(path, entries)

    @staticmethod
    def _write_unlocked(path: Path, entries: list[HistoryEntry]) -> None:
        atomic_write_json(
            path,
            {
                "schema_version": HISTORY_SCHEMA_VERSION,
                "entries": [
                    entry.to_dict()
                    for entry in entries[-MAX_HISTORY_ENTRIES:]
                ],
            },
            mode=0o600,
        )

    # Private compatibility helpers retained for callers/tests that imported
    # the old implementation. They never expose executable command vectors.
    def _load_history(self) -> list[dict[str, Any]]:
        return [entry.to_dict() for entry in self._load_entries()]

    def _save_history(self, history: list[Mapping[str, Any]]) -> None:
        entries = [
            HistoryEntry.from_dict(item)
            for item in history[-MAX_HISTORY_ENTRIES:]
            if isinstance(item, Mapping)
        ]
        self._save_entries(entries)
