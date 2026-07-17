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


class UnknownSchema(KeyError):
    pass


class SchemaRegistry:
    def __init__(self):
        self._schemas: dict[str, SchemaDefinition] = {}
        self._migrations: dict[tuple[str, int], Migration] = {}

    def register(self, schema_id: str, current_version: int) -> None:
        if not schema_id or current_version < 1:
            raise ValueError("Schema id and positive current version are required")
        existing = self._schemas.get(schema_id)
        if existing and existing.current_version != current_version:
            raise ValueError(f"Schema already registered with a different version: {schema_id}")
        self._schemas[schema_id] = SchemaDefinition(schema_id, current_version)

    def add_migration(self, schema_id: str, from_version: int, migration: Migration) -> None:
        if schema_id not in self._schemas:
            raise UnknownSchema(schema_id)
        self._migrations[(schema_id, from_version)] = migration

    def definition(self, schema_id: str) -> SchemaDefinition:
        try:
            return self._schemas[schema_id]
        except KeyError as exc:
            raise UnknownSchema(schema_id) from exc

    def validate_version(self, schema_id: str, version: int) -> None:
        definition = self.definition(schema_id)
        if version > definition.current_version:
            raise UnsupportedFutureSchema(
                f"{schema_id} v{version} is newer than supported v{definition.current_version}"
            )

    def migrate(self, schema_id: str, payload: dict[str, Any], *, dry_run: bool = False) -> dict[str, Any]:
        definition = self.definition(schema_id)
        result = dict(payload)
        version = int(result.get("schema_version", 0))
        self.validate_version(schema_id, version)
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
