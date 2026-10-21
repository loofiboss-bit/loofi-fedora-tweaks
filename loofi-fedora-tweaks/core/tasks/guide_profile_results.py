"""Private aggregate references to independently verified profile action runs.

These records prove the selected settings operation, not the current desktop
state or that every setting in a portable profile was selected.
"""

from __future__ import annotations

import hashlib
import json
import math
import time
import uuid
from pathlib import Path
from typing import Any

from core.actions.stores import ActionRunStore
from core.state.atomic_io import advisory_lock, atomic_write_json
from core.state.inventory import StateInventory
from core.tasks.tweak_profiles import ProfileResult, ProfileReview
from core.tasks.tweaks import BY_ID


class GuideProfileResultStore:
    """Bounded versioned evidence, revalidated against original ActionRuns."""

    def __init__(self, path: Path | None = None) -> None:
        self.path = path or StateInventory().get("guide_profile_results").path

    def _read(self) -> list[dict[str, Any]]:
        if self.path.is_symlink():
            raise ValueError("Profile result references must not be symbolic links.")
        if not self.path.exists():
            return []
        if self.path.stat().st_size > 65536:
            raise ValueError("Profile result references exceed the size limit.")
        payload = json.loads(self.path.read_text(encoding="utf-8"))
        if (not isinstance(payload, dict) or payload.get("schema_id") != "loofi.guide-profile-results"
                or type(payload.get("schema_version")) is not int or payload["schema_version"] != 1):
            raise ValueError("Unsupported profile result references.")
        records = payload.get("results")
        if not isinstance(records, list) or len(records) > 30 or any(not isinstance(row, dict) for row in records):
            raise ValueError("Invalid profile result references.")
        return records

    @staticmethod
    def _fingerprint(run: Any) -> str:
        return hashlib.sha256(json.dumps(run.to_dict(), sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()

    @staticmethod
    def _valid_run(run: Any, tweak_id: str, value: str) -> bool:
        tweak = BY_ID.get(tweak_id)
        return bool(tweak and run and run.run_id and run.action_id == tweak.action_id
                    and run.parameters == {"value": value}
                    and run.state == "succeeded" and run.completed_at is not None
                    and (run.verification_result or {}).get("success") is True)

    def save(self, result: ProfileResult, review: ProfileReview, selected_ids: tuple[str, ...]) -> str:
        """Accept a complete successful aggregate, never a partial result."""
        entries = result.entries
        selected = [entry for entry in entries if entry.status == "succeeded"]
        if (not result.success or not selected or len(entries) > 128
                or len({entry.id for entry in entries}) != len(entries)
                or any(entry.status not in {"succeeded", "skipped"} for entry in entries)
                or len({entry.run_id for entry in selected}) != len(selected)):
            raise ValueError("Only independently successful selected profile settings may be linked.")
        reviewed = {entry.id: entry for entry in review.entries}
        if (len(reviewed) != len(review.entries) or len(set(selected_ids)) != len(selected_ids)
                or set(selected_ids) != {entry.id for entry in selected}
                or {entry.id for entry in entries} != set(reviewed)):
            raise ValueError("Profile results must match the complete reviewed selection.")
        runs = {run.run_id: run for run in ActionRunStore().list_read_only(limit=100, strict=True)}
        references = []
        for entry in selected:
            run = runs.get(entry.run_id)
            approved = reviewed[entry.id]
            if (approved.status != "ready" or entry.id not in BY_ID or approved.action_id != BY_ID[entry.id].action_id
                    or not self._valid_run(run, entry.id, approved.value)):
                raise ValueError("A profile action result is unavailable or unverified.")
            references.append({"tweak_id": entry.id, "value": approved.value, "run_id": entry.run_id, "digest": self._fingerprint(run)})
        record = {"id": str(uuid.uuid4()), "timestamp": time.time(), "selected": references}
        with advisory_lock(self.path):
            records = (self._read() + [record])[-30:]
            payload = {"schema_id": "loofi.guide-profile-results", "schema_version": 1, "results": records}
            if len(json.dumps(payload).encode()) > 65536:
                raise ValueError("Profile result references exceed the size limit.")
            atomic_write_json(self.path, payload, mode=0o600)
        return str(record["id"])

    def available(self) -> tuple[tuple[str, float, int], ...]:
        """Fail closed if any selected result disappeared or changed."""
        records = self._read()
        runs = {run.run_id: run for run in ActionRunStore().list_read_only(limit=100, strict=True)}
        available = []
        for record in records:
            selected = record.get("selected")
            timestamp = record.get("timestamp")
            identifier = record.get("id")
            if (not isinstance(identifier, str) or not isinstance(timestamp, (int, float))
                    or isinstance(timestamp, bool)
                    or not isinstance(selected, list) or not 1 <= len(selected) <= 128):
                continue
            try:
                if not math.isfinite(timestamp) or timestamp <= 0:
                    continue
                uuid.UUID(identifier)
                ids = [reference["tweak_id"] for reference in selected]
                run_ids = [reference["run_id"] for reference in selected]
                if len(set(ids)) != len(ids) or len(set(run_ids)) != len(run_ids):
                    continue
                if all(self._valid_run(runs.get(reference["run_id"]), reference["tweak_id"], reference["value"])
                       and self._fingerprint(runs[reference["run_id"]]) == reference["digest"] for reference in selected):
                    available.append((identifier, float(timestamp), len(selected)))
            except (KeyError, TypeError, ValueError, AttributeError, OverflowError):
                continue
        return tuple(reversed(available))
