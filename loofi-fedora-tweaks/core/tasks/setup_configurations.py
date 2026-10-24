"""Portable, data-only desktop setup intents and local setup progress."""
from __future__ import annotations

import hashlib
import json
import math
import re
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, List, Mapping, Sequence

from core.state.atomic_io import advisory_lock, atomic_write_json
from core.state.inventory import StateInventory
from core.tasks.tweak_profiles import TweakProfile, parse_profile
from core.tasks.tweaks import TweakState
from core.tweak_commands import values_equal
from services.software.installed_applications import InstalledApplication, InstalledInventory, validate_ref

SCHEMA = "loofi.setup/v1"
MAX_SETUP_BYTES = 256 * 1024
MAX_LIBRARY_BYTES = 1024 * 1024
MAX_SETUP_COUNT = 50
MAX_APPLICATIONS = 200
MAX_SETUP_STEPS = MAX_APPLICATIONS + 128
MAX_PROGRESS_RECORDS = 30
MAX_PROGRESS_BYTES = 256 * 1024
_SAFE_HINT = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
_SAFE_PACKAGE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9+._-]{0,127}$")
_APP_STATUSES = frozenset({"present", "missing", "unavailable", "other_installation", "needs_target"})
_TWEAK_STATUSES = frozenset({"matches", "differs", "unavailable", "wrong_desktop"})


@dataclass(frozen=True)
class SetupApplication:
    source: str
    app_id: str
    ref: str
    installation: str = "system"
    source_hint: str = ""
    name: str = ""

    def to_dict(self) -> dict[str, str]:
        return {"source": self.source, "app_id": self.app_id, "ref": self.ref,
                "installation": self.installation, "source_hint": self.source_hint, "name": self.name}

    @property
    def identity(self) -> str:
        return hashlib.sha256(f"{self.source}\0{self.installation}\0{self.ref}".encode()).hexdigest()[:24]


@dataclass(frozen=True)
class SetupDocument:
    name: str
    applications: tuple[SetupApplication, ...]
    profile: TweakProfile

    def to_dict(self) -> dict[str, Any]:
        return {"schema": SCHEMA, "name": self.name,
                "applications": [item.to_dict() for item in self.applications],
                "profile": self.profile.to_dict()}

    @property
    def digest(self) -> str:
        return hashlib.sha256(serialize_setup(self)).hexdigest()


@dataclass(frozen=True)
class SetupComparisonEntry:
    kind: str
    identity: str
    title: str
    status: str
    desired: str = ""
    current: str = ""
    message: str = ""

    def to_dict(self) -> dict[str, str]:
        return {"kind": self.kind, "identity": self.identity, "title": self.title,
                "status": self.status, "desired": self.desired, "current": self.current, "message": self.message}


@dataclass(frozen=True)
class SetupComparison:
    setup_id: str
    name: str
    sampled_at: float
    entries: tuple[SetupComparisonEntry, ...]
    errors: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {"schema": "loofi.setup-comparison/v1", "setup_id": self.setup_id,
                "name": self.name, "sampled_at": self.sampled_at,
                "entries": [item.to_dict() for item in self.entries], "errors": list(self.errors)}


def _clean_text(value: object, *, label: str, limit: int, required: bool = True) -> str:
    if not isinstance(value, str):
        raise ValueError(f"Setup {label} must be text.")
    result = value.strip()
    if (required and not result) or len(result) > limit or any(ord(char) < 32 or ord(char) == 127 for char in result):
        raise ValueError(f"Setup {label} is invalid.")
    return result


def _parse_app(value: object) -> SetupApplication:
    if not isinstance(value, dict) or set(value) - {"source", "app_id", "ref", "installation", "source_hint", "name"}:
        raise ValueError("Setup contains an invalid application entry.")
    source = _clean_text(value.get("source"), label="application source", limit=16)
    app_id = _clean_text(value.get("app_id"), label="application id", limit=256)
    ref = _clean_text(value.get("ref"), label="application reference", limit=300)
    installation = _clean_text(value.get("installation", "system"), label="installation", limit=128)
    source_hint = _clean_text(value.get("source_hint", ""), label="source hint", limit=128, required=False)
    name = _clean_text(value.get("name", ""), label="application name", limit=256, required=False)
    if source == "fedora":
        if not _SAFE_PACKAGE.fullmatch(app_id) or ref != app_id or installation != "system":
            raise ValueError("Setup RPM identity is invalid or version-specific.")
    elif source == "flatpak":
        if (not validate_ref(ref) or ref.split("/")[1] != app_id
                or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{1,255}", app_id)):
            raise ValueError("Setup Flatpak identity is invalid.")
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}", installation):
            raise ValueError("Setup Flatpak installation is invalid.")
    else:
        raise ValueError("Setup applications must use RPM or Flatpak.")
    if source_hint and not _SAFE_HINT.fullmatch(source_hint):
        raise ValueError("Setup source hints must be local identifiers, not URLs or paths.")
    return SetupApplication(source, app_id, ref, installation, source_hint, name)


def parse_setup(data: bytes) -> SetupDocument:
    """Parse a closed portable format; embedded settings reuse the profile schema."""
    if not isinstance(data, bytes) or len(data) > MAX_SETUP_BYTES:
        raise ValueError("Setup file exceeds the size limit.")
    try:
        payload = json.loads(data.decode("utf-8"), object_pairs_hook=_unique_object)
    except (UnicodeDecodeError, json.JSONDecodeError, RecursionError) as exc:
        raise ValueError("Setup file is not valid UTF-8 JSON.") from exc
    if not isinstance(payload, dict) or set(payload) != {"schema", "name", "applications", "profile"}:
        raise ValueError("Setup file has an unsupported structure.")
    if payload["schema"] != SCHEMA:
        raise ValueError("Unsupported setup version.")
    name = _clean_text(payload["name"], label="name", limit=128)
    raw_apps = payload["applications"]
    if not isinstance(raw_apps, list) or len(raw_apps) > MAX_APPLICATIONS:
        raise ValueError("Setup application list is invalid or too large.")
    applications = tuple(_parse_app(item) for item in raw_apps)
    identities = [(item.source, item.installation, item.ref) for item in applications]
    if len(set(identities)) != len(identities):
        raise ValueError("Setup contains duplicate application identities.")
    raw_profile = payload["profile"]
    if not isinstance(raw_profile, dict):
        raise ValueError("Setup settings profile is invalid.")
    profile = parse_profile(json.dumps(raw_profile, ensure_ascii=False, separators=(",", ":")).encode("utf-8"))
    return SetupDocument(name, applications, profile)


def serialize_setup(document: SetupDocument) -> bytes:
    payload = json.dumps(document.to_dict(), ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    parse_setup(payload)
    return payload


def _validated_target_installations(value: object) -> dict[str, str]:
    if not isinstance(value, Mapping) or len(value) > MAX_APPLICATIONS:
        raise ValueError("Confirmed Flatpak targets are invalid.")
    result: dict[str, str] = {}
    for identity, installation in value.items():
        if (not isinstance(identity, str) or not re.fullmatch(r"[a-f0-9]{24}", identity)
                or not isinstance(installation, str)
                or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}", installation)):
            raise ValueError("Confirmed Flatpak targets are invalid.")
        result[identity] = installation
    return result


def _encoded_json_size(payload: object) -> int:
    return len(json.dumps(payload, indent=2, sort_keys=True, default=str).encode("utf-8"))


def available_flatpak_targets(ref: str, installations: Sequence[str],
                              reserved_targets: set[tuple[str, str]]) -> tuple[str, ...]:
    """Keep equal Flatpak refs in separate requested scopes separate on this host."""
    return tuple(item for item in dict.fromkeys(str(value) for value in installations)
                 if (ref, item) not in reserved_targets)


def _unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Setup file contains duplicate JSON keys.")
        result[key] = value
    return result


def setup_app_from_installed(app: InstalledApplication, *, name: str | None = None, source_hint: str = "") -> SetupApplication:
    """Retain stable user intent and installation scope without pinning a build."""
    if app.source == "fedora":
        return _parse_app({"source": "fedora", "app_id": app.app_id, "ref": app.ref,
                           "installation": "system", "source_hint": source_hint, "name": name or app.name})
    if app.source != "flatpak":
        raise ValueError("Only installed RPM and Flatpak applications can be saved.")
    return _parse_app({"source": "flatpak", "app_id": app.app_id, "ref": app.ref,
                       "installation": app.installation, "source_hint": source_hint, "name": name or app.name})


def compare_setup(document: SetupDocument, setup_id: str, inventory: InstalledInventory,
                  tweak_states: Sequence[TweakState], *, target_installations: Mapping[str, str] | None = None,
                  current_desktop: str | None = None, sampled_at: float | None = None) -> SetupComparison:
    """Compare one fresh local inventory against portable intent without mutations."""
    now = time.time() if sampled_at is None else float(sampled_at)
    if not math.isfinite(now) or now <= 0:
        raise ValueError("Comparison timestamp is invalid.")
    try:
        targets = _validated_target_installations(target_installations or {})
    except ValueError:
        targets = {}
    entries: list[SetupComparisonEntry] = []
    installed = inventory.applications
    for app in document.applications:
        title = app.name or app.app_id
        if app.source in inventory.unknown_sources:
            entries.append(SetupComparisonEntry("application", app.identity, title, "unavailable", message="Installation source could not be checked."))
            continue
        target = app.installation
        if app.source == "flatpak" and target not in {"user", "system"}:
            target = str(targets.get(app.identity, ""))
            if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}", target):
                entries.append(SetupComparisonEntry("application", app.identity, title, "needs_target", message="Choose a local Flatpak installation."))
                continue
        exact = any(item.source == app.source and item.ref == app.ref and item.installation == target for item in installed)
        elsewhere = any(item.source == app.source and item.ref == app.ref for item in installed)
        if exact:
            status = "present"
            message = "Application is already installed in the selected installation."
        elif elsewhere:
            status = "other_installation"
            message = "The same application is installed in a different installation."
        else:
            status = "missing"
            message = "Application is not installed in the selected installation."
        entries.append(SetupComparisonEntry("application", app.identity, title, status,
                                            desired=f"{app.source} · {target} · {app.ref}", message=message))

    host_desktop = _desktop_from_states(tweak_states) if current_desktop is None else str(current_desktop)
    if document.profile.settings and document.profile.desktop != host_desktop:
        for key, value in document.profile.settings:
            entries.append(SetupComparisonEntry("setting", key, key, "wrong_desktop", desired=value,
                                                message="This profile targets a different desktop."))
    else:
        states = {state.tweak.id: state for state in tweak_states}
        for key, value in document.profile.settings:
            state = states.get(key)
            if state is None or state.status != "ready":
                entries.append(SetupComparisonEntry("setting", key, state.tweak.title if state else key,
                                                    "unavailable", desired=value,
                                                    message=state.message if state else "Setting was not checked."))
                continue
            matches = values_equal(key, state.value, value)
            entries.append(SetupComparisonEntry("setting", key, state.tweak.title,
                                                "matches" if matches else "differs", desired=value,
                                                current=state.value, message="" if matches else "Current value differs from the saved setting."))
    return SetupComparison(setup_id, document.name, now, tuple(entries), inventory.errors)


def _desktop_from_states(states: Sequence[TweakState]) -> str:
    desktops = {state.tweak.desktop for state in states if state.tweak.desktop in {"gnome", "kde"}}
    return next(iter(desktops)) if len(desktops) == 1 else ""


class SetupLibrary:
    """Bounded private store for portable setup documents."""

    def __init__(self, path: Path | None = None) -> None:
        self.path = path or StateInventory().get("setup_library").path

    def _read(self) -> list[dict[str, Any]]:
        if self.path.is_symlink():
            raise ValueError("Setup library must not be a symbolic link.")
        if not self.path.exists():
            return []
        if self.path.stat().st_size > MAX_LIBRARY_BYTES:
            raise ValueError("Setup library exceeds the size limit.")
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"), object_pairs_hook=_unique_object)
        except (OSError, UnicodeDecodeError, json.JSONDecodeError, ValueError, RecursionError) as exc:
            raise ValueError("Setup library is unreadable.") from exc
        if (not isinstance(payload, dict) or payload.get("schema_id") != "loofi.setup-library"
                or type(payload.get("schema_version")) is not int or payload["schema_version"] != 1
                or not isinstance(payload.get("setups"), list) or len(payload["setups"]) > MAX_SETUP_COUNT):
            raise ValueError("Setup library format is invalid or unsupported.")
        records = []
        for item in payload["setups"]:
            if not isinstance(item, dict) or set(item) != {"id", "document"} or not isinstance(item["id"], str):
                raise ValueError("Setup library contains an invalid record.")
            doc = parse_setup(json.dumps(item["document"], ensure_ascii=False, separators=(",", ":")).encode())
            digest = doc.digest
            if item["id"] != digest:
                raise ValueError("Setup library identity does not match its contents.")
            records.append({"id": digest, "document": doc.to_dict()})
        if len({item["id"] for item in records}) != len(records):
            raise ValueError("Setup library contains duplicate records.")
        return records

    def list(self, query: str = "") -> tuple[tuple[str, SetupDocument], ...]:
        needle = query.strip().casefold()
        records = self._read()
        result = []
        for item in records:
            doc = parse_setup(json.dumps(item["document"], ensure_ascii=False).encode())
            searchable = " ".join((doc.name, *(app.name + " " + app.app_id for app in doc.applications),
                                   *(key for key, _value in doc.profile.settings))).casefold()
            if not needle or needle in searchable:
                result.append((item["id"], doc))
        return tuple(sorted(result, key=lambda item: (item[1].name.casefold(), item[0])))

    def get(self, setup_id: str) -> SetupDocument:
        for identifier, document in self.list():
            if identifier == setup_id:
                return document
        raise ValueError("Setup was not found in the local library.")

    def add(self, document: SetupDocument) -> str:
        parsed = parse_setup(serialize_setup(document))
        identifier = parsed.digest
        with advisory_lock(self.path):
            records = self._read()
            if any(item["id"] == identifier for item in records):
                return identifier
            if len(records) >= MAX_SETUP_COUNT:
                raise ValueError("Setup library is full; remove an entry before adding another.")
            payload = {"schema_id": "loofi.setup-library", "schema_version": 1,
                       "setups": records + [{"id": identifier, "document": parsed.to_dict()}]}
            if _encoded_json_size(payload) > MAX_LIBRARY_BYTES:
                raise ValueError("Setup library exceeds the size limit.")
            atomic_write_json(self.path, payload, mode=0o600)
        return identifier

    def remove(self, setup_id: str) -> None:
        with advisory_lock(self.path):
            records = self._read()
            remaining = [item for item in records if item["id"] != setup_id]
            if len(remaining) == len(records):
                raise ValueError("Setup was not found in the local library.")
            atomic_write_json(self.path, {"schema_id": "loofi.setup-library", "schema_version": 1,
                                          "setups": remaining}, mode=0o600)


class SetupProgressStore:
    """Private crash-safe local progress references, never imported as approval."""

    def __init__(self, path: Path | None = None) -> None:
        self.path = path or StateInventory().get("setup_runs").path

    def list(self) -> tuple[dict[str, Any], ...]:
        if self.path.is_symlink():
            raise ValueError("Setup progress store must not be a symbolic link.")
        if not self.path.exists():
            return ()
        if self.path.stat().st_size > MAX_PROGRESS_BYTES:
            raise ValueError("Setup progress store exceeds the size limit.")
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"), object_pairs_hook=_unique_object)
        except (OSError, UnicodeDecodeError, json.JSONDecodeError, ValueError, RecursionError) as exc:
            raise ValueError("Setup progress is unreadable.") from exc
        records = payload.get("runs") if isinstance(payload, dict) else None
        if (not isinstance(payload, dict) or payload.get("schema_id") != "loofi.setup-runs" or type(payload.get("schema_version")) is not int
                or payload["schema_version"] != 1 or not isinstance(records, list) or len(records) > MAX_PROGRESS_RECORDS):
            raise ValueError("Setup progress format is invalid or unsupported.")
        for item in records:
            if not isinstance(item, dict) or not isinstance(item.get("id"), str):
                raise ValueError("Setup progress contains an invalid record.")
            _validated_target_installations(item.get("target_installations", {}))
            started_at = item.get("started_at")
            try:
                valid_started_at = isinstance(started_at, (int, float)) and not isinstance(started_at, bool) and math.isfinite(float(started_at)) and started_at > 0
            except (OverflowError, TypeError, ValueError):
                valid_started_at = False
            if (not valid_started_at
                    or not isinstance(item.get("status"), str) or item.get("status") not in {"running", "partial", "completed"}
                    or not re.fullmatch(r"[a-f0-9]{64}", str(item.get("setup_id", "")))
                    or not re.fullmatch(r"[a-f0-9]{64}", str(item.get("setup_digest", "")))
                    or item.get("setup_id") != item.get("setup_digest")
                    or not isinstance(item.get("steps"), dict) or not item["steps"] or len(item["steps"]) > MAX_SETUP_STEPS):
                raise ValueError("Setup progress contains an invalid record.")
            try:
                if str(uuid.UUID(item["id"])) != item["id"]:
                    raise ValueError("Setup progress contains an invalid record.")
            except (TypeError, ValueError, AttributeError) as exc:
                raise ValueError("Setup progress contains an invalid record.") from exc
            for step, state in item["steps"].items():
                if (not isinstance(step, str) or not isinstance(state, dict)
                        or not re.fullmatch(r"(?:app:[a-f0-9]{24}|setting:[A-Za-z0-9][A-Za-z0-9._-]{0,127})", step)
                        or not isinstance(state.get("status"), str)
                        or state.get("status") not in {"not_started", "running", "succeeded", "satisfied", "failed", "skipped", "unavailable", "interrupted"}):
                    raise ValueError("Setup progress contains an invalid step.")
                for reference in ("plan_id", "run_id"):
                    value = state.get(reference, "")
                    if not isinstance(value, str) or len(value) > 128 or any(ord(char) < 32 or ord(char) == 127 for char in value):
                        raise ValueError("Setup progress contains an invalid action reference.")
        return tuple(records)

    def start(self, setup_id: str, setup_digest: str, steps: Sequence[str], *,
              target_installations: Mapping[str, str] | None = None) -> str:
        if (not isinstance(setup_id, str) or not isinstance(setup_digest, str)
                or not re.fullmatch(r"[a-f0-9]{64}", setup_id) or setup_id != setup_digest):
            raise ValueError("Setup identity is invalid.")
        if (not isinstance(steps, (tuple, list)) or not steps or len(steps) > MAX_SETUP_STEPS
                or any(not isinstance(step, str) or not re.fullmatch(r"(?:app:[a-f0-9]{24}|setting:[A-Za-z0-9][A-Za-z0-9._-]{0,127})", step) for step in steps)
                or len(set(steps)) != len(steps)):
            raise ValueError("Setup progress steps are invalid.")
        targets = _validated_target_installations(target_installations or {})
        record_id = str(uuid.uuid4())
        record = {"id": record_id, "setup_id": setup_id, "setup_digest": setup_digest,
                  "started_at": time.time(), "status": "running", "target_installations": targets,
                  "steps": {step: {"status": "not_started"} for step in steps}}
        with advisory_lock(self.path):
            records = list(self.list())
            self._write(records + [record], protected_id=record_id)
        return record_id

    def update(self, run_id: str, step: str, status: str, *, plan_id: str = "", action_run_id: str = "") -> None:
        if not isinstance(status, str) or status not in {"not_started", "running", "succeeded", "satisfied", "failed", "skipped", "unavailable", "interrupted"}:
            raise ValueError("Setup step status is invalid.")
        if any(not isinstance(value, str) or len(value) > 128 or any(ord(char) < 32 or ord(char) == 127 for char in value)
               for value in (plan_id, action_run_id)):
            raise ValueError("Setup action reference is invalid.")
        with advisory_lock(self.path):
            records = [dict(item) for item in self.list()]
            record = next((item for item in records if item.get("id") == run_id), None)
            if record is None or step not in record.get("steps", {}):
                raise ValueError("Setup run or step was not found.")
            row = dict(record["steps"][step])
            row.update(status=status, updated_at=time.time())
            if plan_id:
                row["plan_id"] = plan_id
            if action_run_id:
                row["run_id"] = action_run_id
            record["steps"][step] = row
            states = [value.get("status") for value in record["steps"].values()]
            if all(value in {"succeeded", "satisfied"} for value in states):
                record["status"] = "completed"
            elif any(value in {"failed", "unavailable", "interrupted", "skipped"} for value in states):
                record["status"] = "partial"
            else:
                record["status"] = "running"
            self._write(records, protected_id=run_id)

    def _write(self, records: List[dict[str, Any]], *, protected_id: str) -> None:
        kept: List[dict[str, Any]] = records.copy()
        while True:
            payload = {"schema_id": "loofi.setup-runs", "schema_version": 1,
                       "runs": kept[-MAX_PROGRESS_RECORDS:]}
            if len(kept) <= MAX_PROGRESS_RECORDS and _encoded_json_size(payload) <= MAX_PROGRESS_BYTES:
                atomic_write_json(self.path, payload, mode=0o600)
                return
            removable = next((index for index, item in enumerate(kept)
                              if item.get("id") != protected_id and item.get("status") == "completed"), None)
            if removable is None:
                raise ValueError("Setup progress store is full; remove completed history before starting another review.")
            kept.pop(removable)

    def reconcile(self, setup_id: str, setup_digest: str, comparison: SetupComparison, *, active_run_id: str = "",
                  target_installations: Mapping[str, str] | None = None) -> None:
        """Close old attempts from fresh observations without replaying an action."""
        if (not isinstance(setup_id, str) or not isinstance(setup_digest, str)
                or not re.fullmatch(r"[a-f0-9]{64}", setup_id) or setup_id != setup_digest
                or comparison.setup_id != setup_id):
            raise ValueError("Setup reconciliation identity is invalid.")
        current_targets = _validated_target_installations(target_installations or {})
        observed = {
            f"app:{entry.identity}" if entry.kind == "application" else f"setting:{entry.identity}": entry.status
            for entry in comparison.entries if entry.kind in {"application", "setting"}
        }
        with advisory_lock(self.path):
            records = [dict(item) for item in self.list()]
            changed = False
            for record in records:
                if record.get("setup_id") != setup_id or record.get("setup_digest") != setup_digest:
                    continue
                if record.get("status") not in {"running", "partial"}:
                    continue
                is_active = bool(active_run_id) and record.get("id") == active_run_id
                previous_targets = _validated_target_installations(record.get("target_installations", {}))
                steps = {key: dict(value) for key, value in record["steps"].items()}
                for step, state in steps.items():
                    status = state.get("status")
                    if status not in {"not_started", "running"}:
                        continue
                    if step.startswith("app:"):
                        identity = step.partition(":")[2]
                        if previous_targets.get(identity) != current_targets.get(identity):
                            state.update(status="unavailable", updated_at=time.time(),
                                         message="Confirmed Flatpak target changed since this review.")
                            changed = True
                            continue
                    current = observed.get(step)
                    if current in {"present", "matches"}:
                        state.update(status="satisfied", updated_at=time.time())
                        changed = True
                    elif status == "running":
                        replacement = "interrupted" if current in {"missing", "other_installation", "differs"} else "unavailable"
                        state.update(status=replacement, updated_at=time.time())
                        changed = True
                record["steps"] = steps
                states = [value.get("status") for value in steps.values()]
                if all(status in {"succeeded", "satisfied"} for status in states):
                    record["status"] = "completed"
                elif is_active and not any(status in {"failed", "unavailable", "interrupted", "skipped"} for status in states):
                    record["status"] = "running"
                else:
                    record["status"] = "partial"
                record["updated_at"] = time.time()
                changed = True
            if changed:
                self._write(records, protected_id=active_run_id)


def compare_profile(document: SetupDocument, setup_id: str, states: Sequence[TweakState], *, sampled_at: float | None = None) -> SetupComparison:
    return compare_setup(document, setup_id, InstalledInventory(), states, sampled_at=sampled_at)
