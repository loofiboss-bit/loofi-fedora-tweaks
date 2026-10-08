"""Local profile library; portable profiles remain the sole settings format."""
from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path

from core.state.paths import StatePaths
from core.tasks.tweak_presets import list_presets, profile_for_preset
from core.tasks.tweak_profiles import TweakProfile, load_profile, parse_profile, save_profile


@dataclass(frozen=True)
class LibraryEntry:
    id: str
    profile: TweakProfile
    builtin: bool = False
    description: str = ""

    def to_dict(self) -> dict:
        return {"id": self.id, "builtin": self.builtin, "description": self.description,
                "profile": self.profile.to_dict()}


class ProfileLibrary:
    """Store validated user profiles by content identity, never by supplied paths."""

    def __init__(self, root: Path | None = None) -> None:
        self.root = root if root is not None else StatePaths.from_environment().data / "tweak-profiles"

    def _path(self, entry_id: str) -> Path:
        if re.fullmatch(r"[a-f0-9]{64}", entry_id) is None:
            raise ValueError("Only custom library profiles can be changed.")
        return self.root / f"{entry_id}.json"

    def list(self, platform: object) -> tuple[LibraryEntry, ...]:
        entries = []
        for preset in list_presets():
            try:
                profile = profile_for_preset(preset.id, platform)
            except ValueError:
                continue
            entries.append(LibraryEntry(preset.id, profile, True, preset.description))
        if self.root.exists():
            for path in sorted(self.root.glob("*.json")):
                try:
                    self._path(path.stem)
                    if path.is_symlink():
                        continue
                    profile = load_profile(path)
                except (OSError, ValueError):
                    continue
                entries.append(LibraryEntry(path.stem, profile))
        return tuple(entries)

    def add(self, profile: TweakProfile) -> LibraryEntry:
        data = json.dumps(profile.to_dict(), sort_keys=True).encode("utf-8")
        validated = parse_profile(data)
        entry_id = hashlib.sha256(data).hexdigest()
        self.root.mkdir(parents=True, exist_ok=True, mode=0o700)
        path = self._path(entry_id)
        if path.is_symlink():
            raise ValueError("Library profile must not be a symbolic link.")
        save_profile(path, validated)
        return LibraryEntry(entry_id, validated)

    def remove(self, entry_id: str) -> None:
        self._path(entry_id).unlink()
