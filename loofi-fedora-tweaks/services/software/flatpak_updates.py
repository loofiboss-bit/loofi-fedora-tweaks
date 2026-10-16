"""Installation-bound Flatpak update evidence; no Qt or implicit mutation."""
from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Sequence

from core.state.paths import StatePaths
from core.state.atomic_io import advisory_lock, atomic_write_json

from services.software.flatpak_maintenance import DIGEST_PATTERN, INSTALLATION_PATTERN, REF_PATTERN, FlatpakMaintenanceService, helper_command


def update_digest(installation: str, candidates: Sequence[dict[str, Any]], operations: Sequence[dict[str, Any]], source_digest: str = "") -> str:
    payload = {"installation": installation, "candidates": sorted(candidates, key=lambda item: item["ref"]),
               "operations": sorted(operations, key=lambda item: item["ref"])}
    if source_digest:
        payload["source_digest"] = source_digest
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


@dataclass(frozen=True)
class UpdateCandidate:
    installation: str
    ref: str
    origin: str
    installed_commit: str
    expected_commit: str
    name: str = ""
    installed_version: str = ""
    available_version: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class UpdateOperation(UpdateCandidate):
    operation: str = "update"
    selected: bool = False


@dataclass(frozen=True)
class InstallationUpdates:
    installation: str
    available: bool = False
    error: str = ""
    candidates: tuple[UpdateCandidate, ...] = ()
    operations: tuple[UpdateOperation, ...] = ()
    digest: str = ""
    source_digest: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class UpdateSnapshot:
    available: bool = False
    status: str = "unavailable"
    checked_at: str = ""
    error: str = ""
    candidates: tuple[UpdateCandidate, ...] = ()
    installations: tuple[InstallationUpdates, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def review_facts(self) -> dict[str, Any]:
        """Stable review authority deliberately excludes the observation timestamp."""
        return {"evidence_version": 1, "installations": [item.to_dict() for item in self.installations]}


def apply_vector(snapshot: UpdateSnapshot) -> list[str]:
    if not snapshot.available or any(not item.available for item in snapshot.installations):
        raise ValueError("Every selected installation needs fresh update evidence.")
    args = [helper_command(), "update-apply"]
    for item in snapshot.installations:
        if not item.operations:
            continue
        args.extend(("--installation", item.installation, "--snapshot-digest", item.digest))
        for candidate in item.candidates:
            args.extend(("--ref", candidate.ref, "--commit", candidate.expected_commit))
    if len(args) == 2:
        raise ValueError("No Flatpak updates are available.")
    return args


def snapshot_from_facts(facts: Any) -> UpdateSnapshot:
    """Validate persisted review evidence without guessing an installation."""
    if not isinstance(facts, dict) or facts.get("evidence_version") != 1 or not isinstance(facts.get("installations"), list):
        raise ValueError("Fresh installation-bound update review is required.")
    scopes = facts["installations"]
    if not scopes or any(not isinstance(scope, dict) or not isinstance(scope.get("installation"), str) for scope in scopes):
        raise ValueError("Update installation evidence is invalid.")
    identities = [scope["installation"] for scope in scopes]
    if len(set(identities)) != len(identities):
        raise ValueError("Duplicate update installation evidence.")

    def probe(vector):
        if vector[1] == "installations":
            return {"available": True, "installations": identities}
        return next(scope for scope in scopes if scope["installation"] == vector[3])
    snapshot = FlatpakUpdatesService(probe=probe).preview()
    if not snapshot.available or any(not scope.available for scope in snapshot.installations):
        raise ValueError("Update review evidence is invalid.")
    return snapshot


class FlatpakUpdatesService:
    def __init__(self, *, probe: Callable[[Sequence[str]], dict[str, Any]] | None = None, cache_path: Path | None = None) -> None:
        self.probe = probe
        self.cache_path = cache_path or (StatePaths.from_environment().cache / "flatpak-update-observations.json")
        self._cache_enabled = probe is None or cache_path is not None

    def _probe(self, vector, cancelled=None):
        if self.probe is not None:
            return self.probe(vector)
        return FlatpakMaintenanceService._probe(vector, cancelled=cancelled)

    def discover(self, installation: str | None = None, refs: tuple[str, ...] = (), cancelled: Callable[[], bool] | None = None) -> UpdateSnapshot:
        snapshot = self._inspect("updates", installation, refs, cancelled)
        self._save_observation(snapshot)
        return snapshot

    def preview(self, installation: str | None = None, refs: tuple[str, ...] = (), cancelled: Callable[[], bool] | None = None) -> UpdateSnapshot:
        return self._inspect("update-preview", installation, refs, cancelled)

    def last_observation(self) -> dict[str, Any] | None:
        """Informational cache only; never replayed as update authority."""
        try:
            if self.cache_path.is_symlink() or self.cache_path.stat().st_size > 1024 * 1024:
                return None
            payload = json.loads(self.cache_path.read_text(encoding="utf-8"))
            if not isinstance(payload, dict) or payload.get("schema_version") != 1 or not isinstance(payload.get("observation"), dict):
                return None
            return dict(payload["observation"])
        except (OSError, ValueError):
            return None

    def _save_observation(self, snapshot: UpdateSnapshot) -> None:
        if not self._cache_enabled or snapshot.status == "cancelled":
            return
        try:
            with advisory_lock(self.cache_path):
                if self.cache_path.is_symlink() or (self.cache_path.exists() and self.last_observation() is None):
                    return  # Preserve malformed and future state for inspection.
                payload = {"schema_version": 1, "observation": snapshot.to_dict()}
                if len(json.dumps(payload).encode()) <= 1024 * 1024:
                    atomic_write_json(self.cache_path, payload, keep_backup=False)
        except (OSError, ValueError):
            pass

    def _inspect(self, mode: str, selected: str | None, refs: tuple[str, ...], cancelled: Callable[[], bool] | None) -> UpdateSnapshot:
        checked = datetime.now(timezone.utc).isoformat()
        if ((selected is not None and (not isinstance(selected, str) or not INSTALLATION_PATTERN.fullmatch(selected)))
                or not isinstance(refs, (tuple, list)) or len(refs) > 256
                or any(not isinstance(ref, str) or not REF_PATTERN.fullmatch(ref) for ref in refs) or len(set(refs)) != len(refs)):
            return UpdateSnapshot(checked_at=checked, error="Invalid Flatpak update identity.")
        payload = self._probe((helper_command(), "installations"), cancelled) if selected is None else {"available": True, "installations": [selected]}
        names = payload.get("installations", [])
        if not payload.get("available") or not isinstance(names, list) or not names or len(names) > 64 or any(not isinstance(name, str) or not INSTALLATION_PATTERN.fullmatch(name) for name in names):
            return UpdateSnapshot(checked_at=checked, error="Local Flatpak support or installation inventory is unavailable.")
        installations: list[InstallationUpdates] = []
        for name in dict.fromkeys(names):
            if cancelled and cancelled():
                return UpdateSnapshot(status="cancelled", checked_at=checked, candidates=tuple(candidate for item in installations for candidate in item.candidates), installations=tuple(installations))
            scoped_refs = refs
            if refs and selected is None:
                inventory = self._inspect("updates", name, (), cancelled)
                if inventory.status == "cancelled":
                    return UpdateSnapshot(status="cancelled", checked_at=checked, candidates=tuple(candidate for item in installations for candidate in item.candidates), installations=tuple(installations))
                if not inventory.available:
                    installations.extend(inventory.installations or (InstallationUpdates(name, error=inventory.error),))
                    continue
                scoped_refs = tuple(item.ref for item in inventory.candidates if item.ref in refs)
                if not scoped_refs:
                    scope = inventory.installations[0]
                    installations.append(replace(scope, candidates=(), operations=(), digest=update_digest(name, [], [], scope.source_digest)))
                    continue
            args = [helper_command(), mode, "--installation", name]
            for ref in scoped_refs:
                args.extend(("--ref", ref))
            current = self._probe(args, cancelled)
            if current.get("cancelled") or (cancelled and cancelled()):
                return UpdateSnapshot(status="cancelled", checked_at=checked, candidates=tuple(candidate for item in installations for candidate in item.candidates), installations=tuple(installations))
            try:
                if not current.get("available") or current.get("installation") != name:
                    raise ValueError
                candidates = tuple(UpdateCandidate(**item) for item in current["candidates"])
                operations = tuple(UpdateOperation(**item) for item in current.get("operations", []))
                for item in (*candidates, *operations):
                    if (item.installation != name or not REF_PATTERN.fullmatch(item.ref) or not INSTALLATION_PATTERN.fullmatch(item.origin)
                            or not DIGEST_PATTERN.fullmatch(item.expected_commit)
                            or (item.installed_commit and not DIGEST_PATTERN.fullmatch(item.installed_commit))
                            or any(not isinstance(value, str) or len(value) > 1024 or any(ord(c) < 32 or ord(c) == 127 for c in value)
                                   for value in (item.name, item.installed_version, item.available_version))):
                        raise ValueError
                if len(candidates) > 256 or len(operations) > 512 or len({item.ref for item in candidates}) != len(candidates) or len({item.ref for item in operations}) != len(operations):
                    raise ValueError
                candidate_refs = {item.ref for item in candidates}
                if refs and (not candidate_refs.issubset(refs) or (mode == "update-preview" and selected is not None and candidate_refs != set(refs))):
                    raise ValueError
                if any(item.operation not in {"update", "install"} or type(item.selected) is not bool for item in operations):
                    raise ValueError
                if any(not item.installed_commit for item in candidates):
                    raise ValueError
                if any((item.operation == "update" and not item.installed_commit) or (item.operation == "install" and item.installed_commit) for item in operations):
                    raise ValueError
                selected_operations = {item.ref: item for item in operations if item.selected}
                if mode == "update-preview":
                    if set(selected_operations) != {item.ref for item in candidates}:
                        raise ValueError
                    for candidate in candidates:
                        expected = {**candidate.to_dict(), "operation": "update", "selected": True}
                        if selected_operations[candidate.ref].to_dict() != expected:
                            raise ValueError
                source_digest = current.get("source_digest", "")
                if not isinstance(source_digest, str) or not DIGEST_PATTERN.fullmatch(source_digest):
                    raise ValueError
                digest = update_digest(name, [item.to_dict() for item in candidates], [item.to_dict() for item in operations], source_digest)
                if current.get("digest") != digest:
                    raise ValueError
                installations.append(InstallationUpdates(name, True, candidates=candidates, operations=operations, digest=digest, source_digest=source_digest))
            except (KeyError, TypeError, ValueError, AttributeError):
                installations.append(InstallationUpdates(name, error="The selected installation's update evidence is unavailable or invalid."))
        available = any(item.available for item in installations)
        status = "partial" if available and any(not item.available for item in installations) else "available" if available else "unavailable"
        return UpdateSnapshot(available, status, checked, candidates=tuple(candidate for item in installations for candidate in item.candidates), installations=tuple(installations))
