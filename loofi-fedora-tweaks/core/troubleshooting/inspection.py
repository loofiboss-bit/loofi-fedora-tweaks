"""Bounded, read-only inspection helpers for troubleshooting interfaces."""

from __future__ import annotations

import re
import uuid
from typing import Any, cast

from core.privacy import redact_payload
from core.troubleshooting.comparison import compare_sessions
from core.troubleshooting.models import (
    TroubleshootingComparison,
    TroubleshootingSession,
)
from core.troubleshooting.profiles import TroubleshootingProfile
from core.troubleshooting.storage import (
    TroubleshootingSessionStore,
    UnsupportedFutureSessionSchema,
)


INTERFACE_SCHEMA_ID = "loofi.troubleshooting"
INTERFACE_SCHEMA_VERSION = 1
MAX_EXPORTED_FINDINGS = 50
MAX_EXPORTED_RELATED_CHANGES = 25
MAX_EXPORTED_LINKED_RECORDS = 25

_FORBIDDEN_EXPORT_KEYS = frozenset(
    {
        "argv",
        "command",
        "commands",
        "credential",
        "email",
        "hostname",
        "ip",
        "mac",
        "password",
        "path",
        "raw",
        "raw_output",
        "secret",
        "stderr",
        "stdout",
        "token",
    }
)
_HOSTNAME_LABEL_RE = re.compile(
    r"(?i)(\bhostname|\bhost)\s*[:=]\s*[A-Za-z0-9_.-]+"
)


def validate_session_id(value: str) -> str:
    """Validate one opaque canonical troubleshooting session UUID."""
    if not isinstance(value, str):
        raise ValueError("Troubleshooting session ID must be a string.")
    try:
        parsed = uuid.UUID(value)
    except ValueError as exc:
        raise ValueError(
            "Troubleshooting session ID must be an opaque UUID."
        ) from exc
    if str(parsed) != value:
        raise ValueError(
            "Troubleshooting session ID must use canonical UUID form."
        )
    return value


def profile_payload(profile: TroubleshootingProfile) -> dict[str, Any]:
    """Serialize one closed profile without collector or execution behavior."""
    return {
        "profile_id": profile.id,
        "profile_version": profile.version,
        "title": profile.title,
        "availability": profile.availability,
        "limitation_reason_code": profile.limitation_reason_code,
        "total_budget_seconds": profile.total_budget_seconds,
        "parameters": [
            {"name": name, "type": parameter_type}
            for name, parameter_type in profile.parameter_schema
        ],
        "sources": [
            {
                "source_id": budget.source_id,
                "timeout_seconds": budget.timeout_seconds,
                "required": budget.required,
                "variants": sorted(budget.variants),
            }
            for budget in profile.source_budgets
        ],
    }


def sanitize_interface_payload(value: Any) -> Any:
    """Remove authority/private fields and recursively redact remaining text."""
    redacted = redact_payload(_drop_forbidden_fields(value))
    return _mask_labeled_hostnames(redacted)


def bounded_session_payload(
    session: TroubleshootingSession,
) -> dict[str, Any]:
    """Return one privacy-safe session within the Phase 4 interface limits."""
    payload = session.to_dict()
    payload["findings"] = list(payload.get("findings", []))[
        :MAX_EXPORTED_FINDINGS
    ]
    payload["related_changes"] = list(
        payload.get("related_changes", [])
    )[:MAX_EXPORTED_RELATED_CHANGES]
    return cast(dict[str, Any], sanitize_interface_payload(payload))


class TroubleshootingInspectionService:
    """Read current-schema sessions without collecting or mutating state."""

    def __init__(
        self,
        store: TroubleshootingSessionStore | None = None,
    ) -> None:
        self.store = store or TroubleshootingSessionStore()

    def sessions(self) -> tuple[TroubleshootingSession, ...]:
        snapshot = self.store.read()
        if not snapshot.writable:
            raise UnsupportedFutureSessionSchema(
                "Future troubleshooting session data cannot be inspected "
                "through this interface."
            )
        return snapshot.sessions

    def latest(self) -> TroubleshootingSession | None:
        sessions = self.sessions()
        return sessions[0] if sessions else None

    def get(self, session_id: str) -> TroubleshootingSession | None:
        candidate = validate_session_id(session_id)
        return next(
            (
                session
                for session in self.sessions()
                if session.session_id == candidate
            ),
            None,
        )

    def require(self, session_id: str) -> TroubleshootingSession:
        session = self.get(session_id)
        if session is None:
            raise LookupError("Troubleshooting session was not found.")
        return session

    def compare(
        self,
        session_id: str,
        follow_up_id: str,
    ) -> TroubleshootingComparison:
        before = self.require(session_id)
        after = self.require(follow_up_id)
        return compare_sessions(before, after)

    def adjacent_comparison(
        self,
        session: TroubleshootingSession,
    ) -> TroubleshootingComparison | None:
        """Return at most one compatible before/after comparison."""
        compatible = [
            candidate
            for candidate in self.sessions()
            if candidate.session_id != session.session_id
            and candidate.profile_id == session.profile_id
            and candidate.profile_version == session.profile_version
            and candidate.variant == session.variant
        ]
        if not compatible:
            return None
        selected_time = session.completed_at or session.started_at
        newer = [
            candidate
            for candidate in compatible
            if (candidate.completed_at or candidate.started_at) > selected_time
        ]
        if newer:
            follow_up = min(
                newer,
                key=lambda candidate: (
                    candidate.completed_at or candidate.started_at,
                    candidate.session_id,
                ),
            )
            return compare_sessions(session, follow_up)
        previous = max(
            compatible,
            key=lambda candidate: (
                candidate.completed_at or candidate.started_at,
                candidate.session_id,
            ),
        )
        return compare_sessions(previous, session)


def _drop_forbidden_fields(value: Any) -> Any:
    if isinstance(value, dict):
        safe: dict[str, Any] = {}
        for key, item in value.items():
            normalized = str(key).casefold()
            parts = {
                part
                for part in re.split(r"[-_.:]", normalized)
                if part
            }
            if (
                normalized.endswith("_included")
                and isinstance(item, bool)
            ):
                safe[str(key)] = item
                continue
            if (
                normalized in _FORBIDDEN_EXPORT_KEYS
                or parts.intersection(_FORBIDDEN_EXPORT_KEYS)
            ):
                continue
            safe[str(key)] = _drop_forbidden_fields(item)
        return safe
    if isinstance(value, (list, tuple)):
        return [_drop_forbidden_fields(item) for item in value]
    return value


def _mask_labeled_hostnames(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            str(key): _mask_labeled_hostnames(item)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [_mask_labeled_hostnames(item) for item in value]
    if isinstance(value, str):
        return _HOSTNAME_LABEL_RE.sub(r"\1=<masked-host>", value)
    return value
