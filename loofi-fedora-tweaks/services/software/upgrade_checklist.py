"""Private, resumable local state for Fedora upgrade preparation."""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Mapping

from core.fedora_release_policy import FEDORA_RELEASE_POLICY
from core.state.atomic_io import advisory_lock, atomic_write_json
from core.state.inventory import StateInventory


SCHEMA_ID = "loofi.upgrade-preparation-checklist"
SCHEMA_VERSION = 1
MAX_FILE_BYTES = 32 * 1024
MAX_SOURCE_IDS = 256
OBSERVATION_MAX_AGE = timedelta(days=7)
_TARGET = re.compile(r"\d{2,3}(?:-preview)?\Z")
_SOURCE_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.:+-]{0,127}\Z")


def _timestamp(value: str, field: str, *, optional: bool = False) -> str:
    if optional and value == "":
        return value
    if not isinstance(value, str) or len(value) > 64:
        raise ValueError(f"{field} must be an ISO timestamp.")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"{field} must be an ISO timestamp.") from exc
    if parsed.tzinfo is None:
        raise ValueError(f"{field} must include a timezone.")
    return parsed.astimezone(timezone.utc).isoformat()


@dataclass(frozen=True)
class UpgradePreparationChecklist:
    """One saved checklist and the date-bound observations it refers to."""

    target: str = FEDORA_RELEASE_POLICY.stable_target
    updated_at: str = ""
    observation_target: str = ""
    observation_checked_at: str = ""
    observation_state: str = "unknown"
    third_party_source_ids: tuple[str, ...] = ()
    backup_files_confirmed_at: str = ""
    backup_recovery_confirmed_at: str = ""

    def __post_init__(self) -> None:
        if not isinstance(self.target, str) or not _TARGET.fullmatch(self.target):
            raise ValueError("The saved upgrade target is invalid.")
        if self.observation_target and (not isinstance(self.observation_target, str) or not _TARGET.fullmatch(self.observation_target)):
            raise ValueError("The observed upgrade target is invalid.")
        if self.observation_state not in {"unknown", "completed", "partial"}:
            raise ValueError("The saved observation state is invalid.")
        _timestamp(self.updated_at, "updated_at", optional=True)
        _timestamp(self.observation_checked_at, "observation_checked_at", optional=True)
        _timestamp(self.backup_files_confirmed_at, "backup_files_confirmed_at", optional=True)
        _timestamp(self.backup_recovery_confirmed_at, "backup_recovery_confirmed_at", optional=True)
        if len(self.third_party_source_ids) > MAX_SOURCE_IDS:
            raise ValueError("The saved source list exceeds its limit.")
        if any(not isinstance(item, str) or not _SOURCE_ID.fullmatch(item) for item in self.third_party_source_ids):
            raise ValueError("The saved source list contains an invalid ID.")
        if len(set(item.casefold() for item in self.third_party_source_ids)) != len(self.third_party_source_ids):
            raise ValueError("The saved source list contains duplicate IDs.")

    @property
    def backup_files_confirmed(self) -> bool:
        return bool(self.backup_files_confirmed_at)

    @property
    def backup_recovery_confirmed(self) -> bool:
        return bool(self.backup_recovery_confirmed_at)

    def observations_are_stale(self, *, selected_target: str, now: datetime | None = None) -> bool:
        if not self.observation_checked_at or self.observation_state == "unknown":
            return True
        if selected_target != self.observation_target:
            return True
        checked = datetime.fromisoformat(self.observation_checked_at.replace("Z", "+00:00"))
        current = now or datetime.now(timezone.utc)
        if current.tzinfo is None:
            current = current.replace(tzinfo=timezone.utc)
        age = current.astimezone(timezone.utc) - checked
        return age < timedelta(0) or age > OBSERVATION_MAX_AGE

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["third_party_source_ids"] = list(self.third_party_source_ids)
        return payload

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "UpgradePreparationChecklist":
        expected = {
            "target", "updated_at", "observation_target", "observation_checked_at",
            "observation_state", "third_party_source_ids", "backup_files_confirmed_at",
            "backup_recovery_confirmed_at",
        }
        if set(payload) != expected:
            raise ValueError("The saved upgrade checklist has an unsupported shape.")
        source_ids = payload["third_party_source_ids"]
        if not isinstance(source_ids, list):
            raise ValueError("The saved source list is malformed.")
        return cls(
            target=payload["target"],
            updated_at=payload["updated_at"],
            observation_target=payload["observation_target"],
            observation_checked_at=payload["observation_checked_at"],
            observation_state=payload["observation_state"],
            third_party_source_ids=tuple(source_ids),
            backup_files_confirmed_at=payload["backup_files_confirmed_at"],
            backup_recovery_confirmed_at=payload["backup_recovery_confirmed_at"],
        )


@dataclass(frozen=True)
class UpgradeChecklistSnapshot:
    checklist: UpgradePreparationChecklist
    schema_version: int
    writable: bool
    reason_code: str = ""


class UnsupportedFutureChecklistSchema(ValueError):
    """A future checklist schema can be read as unknown but must not be overwritten."""


def _unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("The saved upgrade checklist contains duplicate keys.")
        result[key] = value
    return result


class UpgradePreparationChecklistStore:
    """Crash-safe single-record store under the app's private XDG data directory."""

    def __init__(self, path: Path | None = None, *, inventory: StateInventory | None = None) -> None:
        state_inventory = inventory or StateInventory()
        self.path = path or state_inventory.get("upgrade_preparation").path

    def read(self) -> UpgradeChecklistSnapshot:
        if not self.path.exists():
            return UpgradeChecklistSnapshot(UpgradePreparationChecklist(), SCHEMA_VERSION, True)
        if self.path.stat().st_size > MAX_FILE_BYTES:
            raise ValueError("The saved upgrade checklist exceeds the file-size limit.")
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"), object_pairs_hook=_unique_object)
        except (OSError, UnicodeDecodeError, json.JSONDecodeError, RecursionError) as exc:
            raise ValueError("The saved upgrade checklist is malformed.") from exc
        if not isinstance(payload, Mapping) or payload.get("schema_id") != SCHEMA_ID:
            raise ValueError("The saved upgrade checklist has an unsupported schema.")
        version = payload.get("schema_version")
        if type(version) is not int:
            raise ValueError("The saved upgrade checklist version is invalid.")
        if version > SCHEMA_VERSION:
            return UpgradeChecklistSnapshot(UpgradePreparationChecklist(), version, False, "future-schema-read-only")
        if version != SCHEMA_VERSION or set(payload) != {"schema_id", "schema_version", "checklist"}:
            raise ValueError("The saved upgrade checklist schema is unsupported.")
        record = payload["checklist"]
        if not isinstance(record, Mapping):
            raise ValueError("The saved upgrade checklist is malformed.")
        return UpgradeChecklistSnapshot(UpgradePreparationChecklist.from_dict(record), version, True)

    def save(self, checklist: UpgradePreparationChecklist) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        with advisory_lock(self.path):
            current = self.read()
            if not current.writable:
                raise UnsupportedFutureChecklistSchema("A future upgrade checklist is read-only.")
            payload = {"schema_id": SCHEMA_ID, "schema_version": SCHEMA_VERSION, "checklist": checklist.to_dict()}
            encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
            if len(encoded) > MAX_FILE_BYTES:
                raise ValueError("The saved upgrade checklist exceeds the file-size limit.")
            atomic_write_json(self.path, payload, mode=0o600)
