"""Fail-closed, versioned Safety & Execution settings.

These settings intentionally live outside the legacy UI preference document.
The legacy document has a permissive migration contract; execution policy must
remain atomic, bounded, and read-only when its schema is newer than this build.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, Literal, Mapping

from core.state.atomic_io import atomic_write_json, advisory_lock
from core.state.paths import StatePaths

EXECUTION_SETTINGS_SCHEMA = "loofi.execution-settings/v1"
EXECUTION_SETTINGS_VERSION = 1
ExecutionMode = Literal["direct", "review_first"]


class ExecutionSettingsFutureSchemaError(ValueError):
    """Raised when a write would overwrite settings from a newer build."""


@dataclass(frozen=True)
class ExecutionSettings:
    """User policy for the bounded direct-action adapter."""

    execution_mode: ExecutionMode = "direct"
    confirm_medium_risk: bool = True
    show_command_preview: bool = True
    automatically_verify: bool = True
    open_action_center_on_verification_failure: bool = True
    future_schema: bool = False
    migration_notice: str = ""

    @classmethod
    def defaults(cls) -> "ExecutionSettings":
        return cls()

    @property
    def effective_mode(self) -> ExecutionMode:
        """Use review-first whenever policy data is not understood locally."""
        return "review_first" if self.future_schema else self.execution_mode

    def to_dict(self) -> dict[str, Any]:
        """Return only the stable persisted fields."""
        return {
            "schema": EXECUTION_SETTINGS_SCHEMA,
            "schema_version": EXECUTION_SETTINGS_VERSION,
            "execution_mode": self.execution_mode,
            "confirm_medium_risk": self.confirm_medium_risk,
            "show_command_preview": self.show_command_preview,
            "automatically_verify": self.automatically_verify,
            "open_action_center_on_verification_failure": self.open_action_center_on_verification_failure,
        }

    @classmethod
    def from_payload(cls, payload: Mapping[str, Any]) -> "ExecutionSettings":
        """Parse known settings without accepting arbitrary policy values."""
        mode = payload.get("execution_mode", "direct")
        if mode not in {"direct", "review_first"}:
            mode = "review_first"
        return cls(
            execution_mode=mode,  # type: ignore[arg-type]
            confirm_medium_risk=bool(payload.get("confirm_medium_risk", True)),
            show_command_preview=bool(payload.get("show_command_preview", True)),
            automatically_verify=bool(payload.get("automatically_verify", True)),
            open_action_center_on_verification_failure=bool(
                payload.get("open_action_center_on_verification_failure", True)
            ),
        )

    def with_notice(self, notice: str) -> "ExecutionSettings":
        return replace(self, migration_notice=str(notice)[:300])


class ExecutionSettingsStore:
    """Read and atomically persist Safety & Execution settings."""

    def __init__(self, path: Path | None = None, *, paths: StatePaths | None = None):
        state_paths = paths or StatePaths.from_environment()
        self.path = Path(path) if path is not None else state_paths.config / "execution-settings.json"
        self.future_schema = False
        self.migration_required = False
        self.last_error = ""

    def load(self) -> ExecutionSettings:
        """Load settings; newer schemas become review-first and stay untouched."""
        self.future_schema = False
        self.migration_required = False
        self.last_error = ""
        if not self.path.exists():
            return ExecutionSettings.defaults()
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError, TypeError, ValueError) as exc:
            self.last_error = f"Execution settings could not be read: {exc}"
            self.future_schema = True
            return replace(ExecutionSettings.defaults(), future_schema=True).with_notice(self.last_error)
        if not isinstance(payload, Mapping):
            self.last_error = "Execution settings must be a JSON object."
            self.future_schema = True
            return replace(ExecutionSettings.defaults(), future_schema=True).with_notice(self.last_error)

        version = payload.get("schema_version", 0)
        schema = str(payload.get("schema", ""))
        if isinstance(version, bool):
            numeric_version: int | None = None
        else:
            try:
                numeric_version = int(version)
            except (TypeError, ValueError):
                numeric_version = None
        if numeric_version is None or numeric_version < 0:
            self.future_schema = True
            self.last_error = "Execution settings contain an invalid schema version."
            return replace(ExecutionSettings.defaults(), future_schema=True).with_notice(self.last_error)
        if numeric_version > EXECUTION_SETTINGS_VERSION or (
            numeric_version == EXECUTION_SETTINGS_VERSION and schema not in {"", EXECUTION_SETTINGS_SCHEMA}
        ):
            self.future_schema = True
            self.last_error = "Execution settings were written by a newer or incompatible build."
            return replace(ExecutionSettings.defaults(), future_schema=True).with_notice(self.last_error)
        if numeric_version == 0 and schema:
            self.future_schema = True
            self.last_error = "Execution settings contain an unknown legacy schema."
            return replace(ExecutionSettings.defaults(), future_schema=True).with_notice(self.last_error)

        if numeric_version < EXECUTION_SETTINGS_VERSION:
            settings = self._migrate_legacy(payload)
            self.migration_required = True
            try:
                self.save(settings)
                self.migration_required = False
            except (OSError, RuntimeError, ValueError) as exc:
                self.last_error = f"Execution settings migration was not persisted: {exc}"
            return settings.with_notice(self.last_error)
        return ExecutionSettings.from_payload(payload)

    def save(self, settings: ExecutionSettings) -> ExecutionSettings:
        """Persist settings only when this store owns the schema."""
        if self.future_schema:
            raise ExecutionSettingsFutureSchemaError(
                "Refusing to overwrite execution settings from a newer schema."
            )
        with advisory_lock(self.path):
            atomic_write_json(self.path, settings.to_dict(), keep_backup=True)
        return settings

    def update(self, **changes: Any) -> ExecutionSettings:
        """Apply a closed set of settings changes and persist them."""
        current = self.load()
        if self.future_schema:
            raise ExecutionSettingsFutureSchemaError(
                "Cannot update execution settings from a newer schema."
            )
        allowed = {
            "execution_mode",
            "confirm_medium_risk",
            "show_command_preview",
            "automatically_verify",
            "open_action_center_on_verification_failure",
        }
        unknown = set(changes) - allowed
        if unknown:
            raise ValueError(f"Unknown execution setting(s): {', '.join(sorted(unknown))}")
        candidate = replace(current, **changes)
        if candidate.execution_mode not in {"direct", "review_first"}:
            raise ValueError("execution_mode must be direct or review_first")
        return self.save(candidate)

    @staticmethod
    def _migrate_legacy(payload: Mapping[str, Any]) -> ExecutionSettings:
        """Migrate the old confirmation preference without enabling new authority."""
        mode = payload.get("execution_mode", payload.get("mode", "direct"))
        if mode not in {"direct", "review_first"}:
            mode = "direct"
        medium = payload.get("confirm_medium_risk", payload.get("confirm_dangerous_actions", True))
        auto_verify = payload.get("automatically_verify", payload.get("auto_verify", True))
        return ExecutionSettings(
            execution_mode=mode,  # type: ignore[arg-type]
            confirm_medium_risk=bool(medium),
            show_command_preview=bool(payload.get("show_command_preview", True)),
            automatically_verify=bool(auto_verify),
            open_action_center_on_verification_failure=bool(
                payload.get("open_action_center_on_verification_failure", True)
            ),
        )
