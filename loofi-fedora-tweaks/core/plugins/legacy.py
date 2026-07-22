"""Read-only inventory for external extensions quarantined by Haven."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path

from core.state.atomic_io import atomic_write_json


@dataclass(frozen=True)
class LegacyExtensionRecord:
    name: str
    path: str
    manifest_present: bool


class LegacyExtensionService:
    """List/export legacy files without importing, enabling, or deleting them."""

    @staticmethod
    def default_directory() -> Path:
        return Path.home() / ".config" / "loofi-fedora-tweaks" / "plugins"

    @classmethod
    def list_extensions(cls, directory: Path | None = None) -> list[LegacyExtensionRecord]:
        root = directory or cls.default_directory()
        if not root.is_dir():
            return []
        records: list[LegacyExtensionRecord] = []
        for item in sorted(root.iterdir(), key=lambda candidate: candidate.name.casefold()):
            if item.is_dir() and not item.is_symlink():
                records.append(
                    LegacyExtensionRecord(
                        name=item.name,
                        path=str(item),
                        manifest_present=(item / "plugin.json").is_file(),
                    )
                )
        return records

    @classmethod
    def export_manifest(cls, destination: Path, directory: Path | None = None) -> None:
        records = cls.list_extensions(directory)
        atomic_write_json(
            destination,
            {
                "schema_version": 1,
                "execution": "disabled",
                "extensions": [asdict(record) for record in records],
            },
            mode=0o600,
            keep_backup=False,
        )
