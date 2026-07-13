"""Privacy-safe, manifest-based state backup and two-step restore."""

from __future__ import annotations

import hashlib
import json
import time
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any

from core.state.atomic_io import advisory_lock, atomic_write_bytes, atomic_write_json
from core.state.inventory import StateInventory

ARCHIVE_SCHEMA_VERSION = 1
MAX_ARCHIVE_BYTES = 64 * 1024 * 1024
MAX_ENTRY_BYTES = 16 * 1024 * 1024


class InvalidStateArchive(ValueError):
    pass


class StateArchiveService:
    def __init__(self, inventory: StateInventory | None = None):
        self.inventory = inventory or StateInventory()

    def backup(self, output: Path, domain_ids: list[str] | None = None) -> dict[str, Any]:
        requested = set(domain_ids or [domain.id for domain in self.inventory.all()])
        domains = [domain for domain in self.inventory.all() if domain.id in requested and domain.sensitivity not in {"secret", "derived"}]
        entries: list[dict[str, Any]] = []
        output.parent.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for domain in domains:
                if not domain.path.is_file():
                    continue
                content = domain.path.read_bytes()
                if len(content) > MAX_ENTRY_BYTES:
                    continue
                name = f"state/{domain.id}/{domain.path.name}"
                archive.writestr(name, content)
                entries.append({
                    "domain": domain.id, "path": name, "sha256": hashlib.sha256(content).hexdigest(),
                    "size": len(content), "schema_id": domain.schema_id, "schema_version": domain.schema_version,
                    "sensitivity": domain.sensitivity,
                })
            manifest = {"archive_schema_version": ARCHIVE_SCHEMA_VERSION, "created_at": time.time(), "entries": entries}
            archive.writestr("manifest.json", json.dumps(manifest, indent=2, sort_keys=True))
        return manifest

    def plan_restore(self, archive_path: Path) -> dict[str, Any]:
        manifest, _ = self._validate(archive_path)
        actions: list[dict[str, Any]] = []
        for entry in manifest["entries"]:
            domain = self.inventory.get(entry["domain"])
            status = "replace" if domain.path.exists() else "add"
            actions.append({"domain": domain.id, "status": status, "target": str(domain.path), "sha256": entry["sha256"]})
        plan_id = hashlib.sha256((str(archive_path.resolve()) + json.dumps(actions, sort_keys=True)).encode()).hexdigest()[:24]
        plan = {"plan_id": plan_id, "archive": str(archive_path.resolve()), "created_at": time.time(), "actions": actions}
        plan_path = self.inventory.paths.cache / "restore-plans" / f"{plan_id}.json"
        atomic_write_json(plan_path, plan, keep_backup=False)
        return plan

    def apply_restore(self, archive_path: Path, plan_id: str) -> dict[str, Any]:
        plan_path = self.inventory.paths.cache / "restore-plans" / f"{plan_id}.json"
        try:
            plan = json.loads(plan_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise InvalidStateArchive("Restore plan is missing or invalid") from exc
        expected = self.plan_restore(archive_path)
        if expected["plan_id"] != plan_id:
            raise InvalidStateArchive("Restore plan does not match archive")
        _, contents = self._validate(archive_path)
        rollback = self.inventory.paths.data / "backups" / f"rollback-{int(time.time())}.zip"
        self.backup(rollback, [action["domain"] for action in plan["actions"]])
        applied: list[str] = []
        for action in plan["actions"]:
            domain = self.inventory.get(action["domain"])
            entry_name = next(name for name in contents if name.startswith(f"state/{domain.id}/"))
            with advisory_lock(domain.path):
                atomic_write_bytes(domain.path, contents[entry_name])
            applied.append(domain.id)
        from core.actions.history import ActionHistoryStore

        result = {"status": "applied", "domains": applied, "rollback_archive": str(rollback)}
        ActionHistoryStore(self.inventory.get("action_history").path).append(
            {"event": "state-restore-applied", "plan_id": plan_id, "domains": applied, "rollback_archive": str(rollback)}
        )
        return result

    def _validate(self, archive_path: Path) -> tuple[dict[str, Any], dict[str, bytes]]:
        if archive_path.stat().st_size > MAX_ARCHIVE_BYTES:
            raise InvalidStateArchive("Archive is oversized")
        contents: dict[str, bytes] = {}
        with zipfile.ZipFile(archive_path) as archive:
            names = archive.namelist()
            if len(names) != len(set(names)):
                raise InvalidStateArchive("Archive contains duplicate entries")
            for info in archive.infolist():
                path = PurePosixPath(info.filename)
                if path.is_absolute() or ".." in path.parts or info.file_size > MAX_ENTRY_BYTES:
                    raise InvalidStateArchive(f"Unsafe archive entry: {info.filename}")
                contents[info.filename] = archive.read(info)
        try:
            manifest = json.loads(contents["manifest.json"])
        except (KeyError, json.JSONDecodeError) as exc:
            raise InvalidStateArchive("Manifest is missing or invalid") from exc
        if manifest.get("archive_schema_version") != ARCHIVE_SCHEMA_VERSION:
            raise InvalidStateArchive("Unsupported archive schema")
        seen_domains: set[str] = set()
        for entry in manifest.get("entries", []):
            domain_id = entry.get("domain")
            if domain_id in seen_domains:
                raise InvalidStateArchive("Duplicate domain entry")
            seen_domains.add(domain_id)
            try:
                domain = self.inventory.get(domain_id)
                content = contents[entry["path"]]
            except (KeyError, TypeError) as exc:
                raise InvalidStateArchive("Manifest references unknown content") from exc
            if entry.get("schema_id") != domain.schema_id or int(entry.get("schema_version", 0)) > domain.schema_version:
                raise InvalidStateArchive("Incompatible state schema")
            if hashlib.sha256(content).hexdigest() != entry.get("sha256"):
                raise InvalidStateArchive("State archive hash mismatch")
        return manifest, contents
