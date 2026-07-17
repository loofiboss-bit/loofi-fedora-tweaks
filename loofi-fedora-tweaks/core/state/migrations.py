"""Ordered and idempotent state migration runner."""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from core.state.atomic_io import advisory_lock, atomic_write_json
from core.state.schema import SchemaRegistry


class MigrationRunner:
    def __init__(self, registry: SchemaRegistry):
        self.registry = registry

    def migrate_json(self, schema_id: str, path: Path, *, dry_run: bool = False) -> dict[str, Any]:
        with advisory_lock(path):
            payload = json.loads(path.read_text(encoding="utf-8"))
            migrated = self.registry.migrate(schema_id, payload, dry_run=dry_run)
            if not dry_run and migrated != payload:
                atomic_write_json(path, migrated)
                verified = json.loads(path.read_text(encoding="utf-8"))
                if verified != migrated:
                    raise ValueError("Migration readback failed")
                atomic_write_json(path.with_suffix(path.suffix + ".migration.json"), {
                    "schema_id": schema_id, "completed_at": time.time(), "schema_version": migrated["schema_version"]
                }, keep_backup=False)
            return migrated


def registry_for_inventory(inventory: Any) -> SchemaRegistry:
    """Build the canonical registry from the inventory's typed contracts."""

    registry = SchemaRegistry()
    for domain in inventory.all():
        registry.register(domain.schema_id, domain.schema_version)
    if any(domain.schema_id == "loofi.health-snapshots" for domain in inventory.all()):
        registry.add_migration(
            "loofi.health-snapshots",
            0,
            lambda payload: {**payload, "schema_version": 1},
        )
    return registry
