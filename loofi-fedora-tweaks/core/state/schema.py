"""Versioned schema registry independent of application versions."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable


Migration = Callable[[dict[str, Any]], dict[str, Any]]


@dataclass(frozen=True)
class SchemaDefinition:
    id: str
    current_version: int


class UnsupportedFutureSchema(ValueError):
    pass


class SchemaRegistry:
    def __init__(self):
        self._schemas: dict[str, SchemaDefinition] = {}
        self._migrations: dict[tuple[str, int], Migration] = {}

    def register(self, schema_id: str, current_version: int) -> None:
        self._schemas[schema_id] = SchemaDefinition(schema_id, current_version)

    def add_migration(self, schema_id: str, from_version: int, migration: Migration) -> None:
        self._migrations[(schema_id, from_version)] = migration

    def migrate(self, schema_id: str, payload: dict[str, Any], *, dry_run: bool = False) -> dict[str, Any]:
        definition = self._schemas[schema_id]
        result = dict(payload)
        version = int(result.get("schema_version", 0))
        if version > definition.current_version:
            raise UnsupportedFutureSchema(f"{schema_id} v{version} is newer than supported v{definition.current_version}")
        while version < definition.current_version:
            migration = self._migrations.get((schema_id, version))
            if migration is None:
                raise ValueError(f"Missing migration for {schema_id} v{version}")
            result = migration(dict(result))
            next_version = int(result.get("schema_version", version))
            if next_version != version + 1:
                raise ValueError("Migration must advance exactly one version")
            version = next_version
        return dict(payload) if dry_run else result
