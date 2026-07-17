"""Privacy-safe, manifest-based state backup and two-step restore."""

from __future__ import annotations

import hashlib
import io
import json
import stat
import time
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any

from core.state.atomic_io import advisory_locks, atomic_write_bytes, atomic_write_json, durable_unlink
from core.state.inventory import StateDomain, StateInventory

ARCHIVE_SCHEMA_VERSION = 1
RESTORE_PLAN_SCHEMA_VERSION = 2
RESTORE_PLAN_TTL_SECONDS = 30 * 60
MAX_ARCHIVE_BYTES = 64 * 1024 * 1024
MAX_ENTRY_BYTES = 16 * 1024 * 1024
MAX_TOTAL_UNCOMPRESSED_BYTES = 64 * 1024 * 1024
MAX_ARCHIVE_ENTRIES = 256


class InvalidStateArchive(ValueError):
    pass


class StateRestoreError(RuntimeError):
    """A restore failed after validation; automatic rollback was attempted."""


class StateArchiveService:
    def __init__(self, inventory: StateInventory | None = None):
        self.inventory = inventory or StateInventory()

    def backup(self, output: Path, domain_ids: list[str] | None = None) -> dict[str, Any]:
        requested = set(domain_ids or [domain.id for domain in self.inventory.all()])
        domains = [
            domain
            for domain in self.inventory.all()
            if (
                domain.id in requested
                and domain.category not in {"cache", "runtime"}
                and domain.sensitivity not in {"secret", "derived"}
            )
        ]
        with advisory_locks([domain.path for domain in domains]):
            content, manifest = self._build_archive(domains)
            atomic_write_bytes(output, content, keep_backup=False)
        return manifest

    def plan_restore(self, archive_path: Path) -> dict[str, Any]:
        manifest, _, archive_digest = self._validate(archive_path)
        domains = [self.inventory.get(entry["domain"]) for entry in manifest["entries"]]
        actions: list[dict[str, Any]] = []
        with advisory_locks([domain.path for domain in domains]):
            for entry, domain in zip(manifest["entries"], domains):
                baseline = self._target_baseline(domain.path)
                actions.append({
                    "domain": domain.id,
                    "status": "replace" if baseline["exists"] else "add",
                    "target": str(domain.path),
                    "sha256": entry["sha256"],
                    "target_baseline": baseline,
                })
        created_at = time.time()
        binding = {
            "archive": str(archive_path.resolve()),
            "archive_sha256": archive_digest,
            "actions": actions,
        }
        plan_id = self._plan_id(binding)
        plan = {
            "schema_id": "loofi.restore-plan",
            "schema_version": RESTORE_PLAN_SCHEMA_VERSION,
            "plan_id": plan_id,
            **binding,
            "created_at": created_at,
            "expires_at": created_at + RESTORE_PLAN_TTL_SECONDS,
        }
        plan_path = self.inventory.paths.cache / "restore-plans" / f"{plan_id}.json"
        atomic_write_json(plan_path, plan, keep_backup=False)
        return plan

    def apply_restore(self, archive_path: Path, plan_id: str) -> dict[str, Any]:
        if len(plan_id) != 24 or any(character not in "0123456789abcdef" for character in plan_id):
            raise InvalidStateArchive("Restore plan id is invalid")
        plan_path = self.inventory.paths.cache / "restore-plans" / f"{plan_id}.json"
        try:
            plan = json.loads(plan_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise InvalidStateArchive("Restore plan is missing or invalid") from exc
        self._validate_plan(plan, archive_path, plan_id)
        manifest, contents, archive_digest = self._validate(archive_path)
        if archive_digest != plan["archive_sha256"]:
            raise InvalidStateArchive("Restore archive changed after planning")

        entries = {entry["domain"]: entry for entry in manifest["entries"]}
        actions = plan["actions"]
        if set(entries) != {action.get("domain") for action in actions}:
            raise InvalidStateArchive("Restore plan actions do not match archive")
        domains = [self.inventory.get(action["domain"]) for action in actions]
        for action, domain in zip(actions, domains):
            entry = entries[domain.id]
            if action.get("target") != str(domain.path) or action.get("sha256") != entry["sha256"]:
                raise InvalidStateArchive("Restore plan target does not match inventory")

        rollback = self.inventory.paths.data / "backups" / f"rollback-{time.time_ns()}.zip"
        applied: list[StateDomain] = []
        previous: dict[str, bytes | None] = {}
        with advisory_locks([domain.path for domain in domains]):
            if time.time() > float(plan["expires_at"]):
                raise InvalidStateArchive("Restore plan expired while waiting for state locks; create a new plan")
            for action, domain in zip(actions, domains):
                if self._target_baseline(domain.path) != action.get("target_baseline"):
                    raise InvalidStateArchive(f"Restore target changed after planning: {domain.id}")
            for domain in domains:
                previous[domain.id] = domain.path.read_bytes() if domain.path.is_file() else None
            rollback_content, _ = self._build_archive(domains)
            atomic_write_bytes(rollback, rollback_content, keep_backup=False)
            attempted: list[StateDomain] = []
            try:
                for domain in domains:
                    entry = entries[domain.id]
                    # A durable write can replace the target and then fail its
                    # final readback/fsync. Include the in-flight domain in
                    # rollback before crossing that boundary.
                    attempted.append(domain)
                    atomic_write_bytes(domain.path, contents[entry["path"]])
                    applied.append(domain)
            except OSError as exc:
                rollback_errors: list[str] = []
                for domain in reversed(attempted):
                    try:
                        original = previous[domain.id]
                        if original is None:
                            durable_unlink(domain.path)
                        else:
                            atomic_write_bytes(domain.path, original, keep_backup=False)
                    except OSError as rollback_exc:  # pragma: no cover - catastrophic I/O path
                        rollback_errors.append(f"{domain.id}: {rollback_exc}")
                detail = "automatic rollback completed"
                if rollback_errors:
                    detail = f"automatic rollback incomplete ({'; '.join(rollback_errors)})"
                raise StateRestoreError(f"Restore failed; {detail}: {exc}") from exc

        from core.actions.history import ActionHistoryStore

        result = {
            "status": "applied",
            "domains": [domain.id for domain in applied],
            "rollback_archive": str(rollback),
            "archive_sha256": archive_digest,
        }
        ActionHistoryStore(self.inventory.get("action_history").path).append({
            "event": "state-restore-applied",
            "plan_id": plan_id,
            "domains": result["domains"],
            "rollback_archive": str(rollback),
            "archive_sha256": archive_digest,
        })
        return result

    def _build_archive(self, domains: list[StateDomain]) -> tuple[bytes, dict[str, Any]]:
        entries: list[dict[str, Any]] = []
        state_content: list[tuple[str, bytes]] = []
        total_size = 0
        for domain in domains:
            if domain.path.is_symlink():
                raise InvalidStateArchive(f"State source is a symbolic link: {domain.id}")
            if not domain.path.is_file():
                continue
            content = domain.path.read_bytes()
            if len(content) > MAX_ENTRY_BYTES:
                continue
            total_size += len(content)
            if total_size > MAX_TOTAL_UNCOMPRESSED_BYTES:
                raise InvalidStateArchive("State snapshot is oversized")
            name = f"state/{domain.id}/{domain.path.name}"
            state_content.append((name, content))
            entries.append({
                "domain": domain.id,
                "path": name,
                "sha256": hashlib.sha256(content).hexdigest(),
                "size": len(content),
                "schema_id": domain.schema_id,
                "schema_version": self._content_schema_version(domain, content),
                "sensitivity": domain.sensitivity,
            })
        manifest = {
            "archive_schema_version": ARCHIVE_SCHEMA_VERSION,
            "created_at": time.time(),
            "entries": entries,
        }
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for name, content in state_content:
                archive.writestr(name, content)
            archive.writestr("manifest.json", json.dumps(manifest, indent=2, sort_keys=True))
        encoded = buffer.getvalue()
        if len(encoded) > MAX_ARCHIVE_BYTES:
            raise InvalidStateArchive("State snapshot archive is oversized")
        return encoded, manifest

    @staticmethod
    def _content_schema_version(domain: StateDomain, content: bytes) -> int:
        if domain.path.suffix != ".json":
            return domain.schema_version
        try:
            payload = json.loads(content)
            if isinstance(payload, dict) and "schema_version" in payload:
                return int(payload["schema_version"])
        except (UnicodeDecodeError, json.JSONDecodeError, TypeError, ValueError):
            pass
        return domain.schema_version

    @staticmethod
    def _target_baseline(path: Path) -> dict[str, Any]:
        if path.is_symlink():
            raise InvalidStateArchive(f"Restore target is a symbolic link: {path}")
        if not path.exists():
            return {"exists": False, "sha256": None, "size": 0}
        if not path.is_file():
            raise InvalidStateArchive(f"Restore target is not a regular file: {path}")
        content = path.read_bytes()
        return {"exists": True, "sha256": hashlib.sha256(content).hexdigest(), "size": len(content)}

    @staticmethod
    def _plan_id(binding: dict[str, Any]) -> str:
        canonical = json.dumps(binding, sort_keys=True, separators=(",", ":")).encode("utf-8")
        return hashlib.sha256(canonical).hexdigest()[:24]

    def _validate_plan(self, plan: Any, archive_path: Path, plan_id: str) -> None:
        if not isinstance(plan, dict) or plan.get("schema_version") != RESTORE_PLAN_SCHEMA_VERSION:
            raise InvalidStateArchive("Restore plan schema is unsupported; create a new plan")
        if plan.get("plan_id") != plan_id:
            raise InvalidStateArchive("Restore plan identity mismatch")
        if plan.get("archive") != str(archive_path.resolve()):
            raise InvalidStateArchive("Restore plan does not match archive path")
        try:
            expires_at = float(plan["expires_at"])
        except (KeyError, TypeError, ValueError) as exc:
            raise InvalidStateArchive("Restore plan expiry is invalid") from exc
        if time.time() > expires_at:
            raise InvalidStateArchive("Restore plan expired; create a new plan")
        binding = {
            "archive": plan.get("archive"),
            "archive_sha256": plan.get("archive_sha256"),
            "actions": plan.get("actions"),
        }
        if not isinstance(binding["actions"], list) or self._plan_id(binding) != plan_id:
            raise InvalidStateArchive("Restore plan was modified after creation")

    def _validate(self, archive_path: Path) -> tuple[dict[str, Any], dict[str, bytes], str]:
        try:
            if archive_path.is_symlink() or not archive_path.is_file():
                raise InvalidStateArchive("Archive must be a regular non-symlink file")
            raw_archive = archive_path.read_bytes()
        except OSError as exc:
            raise InvalidStateArchive("Archive is unreadable") from exc
        if len(raw_archive) > MAX_ARCHIVE_BYTES:
            raise InvalidStateArchive("Archive is oversized")
        contents: dict[str, bytes] = {}
        try:
            with zipfile.ZipFile(io.BytesIO(raw_archive)) as archive:
                infos = archive.infolist()
                if len(infos) > MAX_ARCHIVE_ENTRIES:
                    raise InvalidStateArchive("Archive contains too many entries")
                names = [info.filename for info in infos]
                if len(names) != len(set(names)):
                    raise InvalidStateArchive("Archive contains duplicate entries")
                total_size = 0
                for info in infos:
                    path = PurePosixPath(info.filename)
                    unix_mode = (info.external_attr >> 16) & 0xFFFF
                    is_symlink = bool(unix_mode and stat.S_ISLNK(unix_mode))
                    total_size += info.file_size
                    if (
                        not info.filename
                        or "\\" in info.filename
                        or path.is_absolute()
                        or ".." in path.parts
                        or info.is_dir()
                        or is_symlink
                        or info.file_size > MAX_ENTRY_BYTES
                        or total_size > MAX_TOTAL_UNCOMPRESSED_BYTES
                    ):
                        raise InvalidStateArchive(f"Unsafe archive entry: {info.filename}")
                    contents[info.filename] = archive.read(info)
        except (OSError, RuntimeError, zipfile.BadZipFile) as exc:
            raise InvalidStateArchive("Archive content is invalid") from exc
        try:
            manifest = json.loads(contents["manifest.json"])
        except (KeyError, json.JSONDecodeError, UnicodeDecodeError) as exc:
            raise InvalidStateArchive("Manifest is missing or invalid") from exc
        if not isinstance(manifest, dict) or manifest.get("archive_schema_version") != ARCHIVE_SCHEMA_VERSION:
            raise InvalidStateArchive("Unsupported archive schema")
        entries = manifest.get("entries")
        if not isinstance(entries, list):
            raise InvalidStateArchive("Manifest entries are invalid")
        seen_domains: set[str] = set()
        declared_paths: set[str] = set()
        for entry in entries:
            if not isinstance(entry, dict):
                raise InvalidStateArchive("Manifest entry is invalid")
            domain_id = entry.get("domain")
            if not isinstance(domain_id, str) or domain_id in seen_domains:
                raise InvalidStateArchive("Duplicate or invalid domain entry")
            seen_domains.add(domain_id)
            try:
                domain = self.inventory.get(domain_id)
                entry_path = entry["path"]
                expected_path = f"state/{domain.id}/{domain.path.name}"
                if entry_path != expected_path:
                    raise InvalidStateArchive("Manifest state path is invalid")
                content = contents[entry_path]
                version = int(entry.get("schema_version", 0))
            except (KeyError, TypeError, ValueError) as exc:
                if isinstance(exc, InvalidStateArchive):
                    raise
                raise InvalidStateArchive("Manifest references unknown content") from exc
            declared_paths.add(entry_path)
            # Restore never writes an older payload directly into a newer
            # domain. Migrations operate on local state through the registered
            # migration runner; archives must match the current schema exactly.
            if entry.get("schema_id") != domain.schema_id or version != domain.schema_version:
                raise InvalidStateArchive("Incompatible state schema")
            if entry.get("size", len(content)) != len(content):
                raise InvalidStateArchive("State archive size mismatch")
            if hashlib.sha256(content).hexdigest() != entry.get("sha256"):
                raise InvalidStateArchive("State archive hash mismatch")
        if set(contents) != declared_paths | {"manifest.json"}:
            raise InvalidStateArchive("Archive contains undeclared content")
        return manifest, contents, hashlib.sha256(raw_archive).hexdigest()
