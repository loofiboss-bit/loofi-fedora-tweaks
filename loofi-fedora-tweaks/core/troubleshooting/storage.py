"""Bounded XDG persistence for explicit troubleshooting session history."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from core.state.atomic_io import advisory_lock, atomic_write_json
from core.state.inventory import StateInventory
from core.troubleshooting.models import (
    SESSION_SCHEMA_VERSION,
    TroubleshootingSession,
)
from core.troubleshooting.validation import (
    MAX_SESSION_FILE_BYTES,
    MAX_SESSIONS,
)


STORE_SCHEMA_ID = "loofi.troubleshooting-sessions"
STORE_SCHEMA_VERSION = 1


class UnsupportedFutureSessionSchema(ValueError):
    """Raised when a future store is readable as raw data but not writable."""


@dataclass(frozen=True)
class SessionStoreSnapshot:
    sessions: tuple[TroubleshootingSession, ...]
    schema_version: int
    writable: bool
    reason_code: str = ""


class TroubleshootingSessionStore:
    """Crash-safe store that never rewrites an unknown future schema."""

    def __init__(
        self,
        path: Path | None = None,
        *,
        inventory: StateInventory | None = None,
    ) -> None:
        state_inventory = inventory or StateInventory()
        self.path = path or state_inventory.get("troubleshooting_sessions").path

    def read(self) -> SessionStoreSnapshot:
        if not self.path.exists():
            return SessionStoreSnapshot((), STORE_SCHEMA_VERSION, True)
        if self.path.stat().st_size > MAX_SESSION_FILE_BYTES:
            raise ValueError("Troubleshooting session store exceeds the bounded file size.")
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ValueError("Troubleshooting session store is malformed.") from exc
        if not isinstance(payload, Mapping):
            raise ValueError("Troubleshooting session store must be a JSON object.")
        if payload.get("schema_id") != STORE_SCHEMA_ID:
            raise ValueError("Unsupported troubleshooting session store schema ID.")
        version = int(payload.get("schema_version", 0))
        if version > STORE_SCHEMA_VERSION:
            return SessionStoreSnapshot(
                (),
                version,
                False,
                "future-schema-read-only",
            )
        if version != STORE_SCHEMA_VERSION:
            raise ValueError("Unsupported troubleshooting session store schema version.")
        records = payload.get("sessions", [])
        if not isinstance(records, list) or len(records) > MAX_SESSIONS:
            raise ValueError("Troubleshooting session store exceeds the bounded record limit.")
        if any(not isinstance(record, Mapping) for record in records):
            raise ValueError("Troubleshooting session store contains malformed records.")
        sessions = tuple(TroubleshootingSession.from_dict(record) for record in records)
        return SessionStoreSnapshot(sessions, version, True)

    def save(self, session: TroubleshootingSession) -> None:
        """Persist one explicit terminal session with bounded retention."""
        if session.schema_version != SESSION_SCHEMA_VERSION:
            raise ValueError("Only the current troubleshooting session schema is writable.")
        if session.state in {"queued", "running"}:
            raise ValueError("Active troubleshooting sessions are not persisted.")
        self.path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        with advisory_lock(self.path):
            snapshot = self.read()
            if not snapshot.writable:
                raise UnsupportedFutureSessionSchema(
                    "Future troubleshooting session data is read-only."
                )
            retained = [
                item
                for item in snapshot.sessions
                if item.session_id != session.session_id
            ]
            retained.append(session)
            retained.sort(
                key=lambda item: (
                    item.completed_at or item.started_at,
                    item.session_id,
                ),
                reverse=True,
            )
            payload: dict[str, Any] = {
                "schema_id": STORE_SCHEMA_ID,
                "schema_version": STORE_SCHEMA_VERSION,
                "sessions": [
                    item.to_dict()
                    for item in retained[:MAX_SESSIONS]
                ],
            }
            encoded_size = len(
                json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
            )
            if encoded_size > MAX_SESSION_FILE_BYTES:
                raise ValueError("Troubleshooting session data exceeds the bounded file size.")
            atomic_write_json(self.path, payload, mode=0o600)
