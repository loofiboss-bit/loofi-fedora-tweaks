"""Read-only validation of all registered application state."""

from __future__ import annotations

import json
import os
import sqlite3
import time
from dataclasses import asdict, dataclass
from typing import Any

from core.state.inventory import StateDomain, StateInventory


@dataclass(frozen=True)
class DoctorFinding:
    domain: str
    severity: str
    summary: str
    evidence: str
    next_step: str

    def to_dict(self) -> dict[str, str]:
        return asdict(self)


class StateDoctor:
    """Produces evidence and guidance without mutating any path."""

    def __init__(self, inventory: StateInventory | None = None):
        self.inventory = inventory or StateInventory()

    def run(self) -> dict[str, Any]:
        before = self._fingerprints()
        findings = [finding for domain in self.inventory.all() for finding in self._check(domain)]
        if before != self._fingerprints():
            raise RuntimeError("State Doctor invariant violated: state changed during validation")
        worst = "healthy" if not findings else ("error" if any(item.severity == "error" for item in findings) else "warning")
        return {
            "schema_id": "loofi.state-doctor",
            "schema_version": 1,
            "status": worst,
            "checked_at": time.time(),
            "domains": [self._domain_dict(item) for item in self.inventory.all()],
            "findings": [item.to_dict() for item in findings],
        }

    def _fingerprints(self) -> dict[str, tuple[int, int] | None]:
        result: dict[str, tuple[int, int] | None] = {}
        for domain in self.inventory.all():
            try:
                stat = domain.path.stat()
                result[domain.id] = (stat.st_mtime_ns, stat.st_size)
            except OSError:
                result[domain.id] = None
        return result

    @staticmethod
    def _domain_dict(domain: StateDomain) -> dict[str, Any]:
        payload = asdict(domain)
        payload["path"] = str(domain.path)
        payload["exists"] = domain.path.exists()
        return payload

    def _check(self, domain: StateDomain) -> list[DoctorFinding]:
        path = domain.path
        if not path.exists():
            return [] if domain.optional else [DoctorFinding(domain.id, "warning", "Required state is missing", str(path), "Start the owning component to recreate it.")]
        findings: list[DoctorFinding] = []
        try:
            mode = path.stat().st_mode & 0o777
            if domain.sensitivity in {"secret", "sensitive", "private"} and mode & 0o077:
                findings.append(DoctorFinding(domain.id, "warning", "Permissions are broader than recommended", oct(mode), "Restrict access to the current user after reviewing ownership."))
            if path.is_file() and not os.access(path, os.R_OK):
                findings.append(DoctorFinding(domain.id, "error", "State is unreadable", str(path), "Review file ownership and permissions."))
            if path.suffix == ".json":
                json.loads(path.read_text(encoding="utf-8"))
            elif path.suffix == ".jsonl":
                for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
                    if line.strip():
                        json.loads(line)
            elif path.suffix == ".db":
                connection = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
                try:
                    result = connection.execute("PRAGMA integrity_check").fetchone()
                    if not result or result[0] != "ok":
                        raise sqlite3.DatabaseError(str(result))
                finally:
                    connection.close()
        except (OSError, ValueError, json.JSONDecodeError, sqlite3.DatabaseError) as exc:
            findings.append(DoctorFinding(domain.id, "error", "State validation failed", str(exc), f"Preserve {path} and use a domain-specific recovery plan."))
        lock = path.with_name(path.name + ".lock")
        if lock.exists() and time.time() - lock.stat().st_mtime > 3600:
            findings.append(DoctorFinding(domain.id, "warning", "Lock file appears stale", str(lock), "Confirm no owner is active before archiving the stale lock."))
        return findings
