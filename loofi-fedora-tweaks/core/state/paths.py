"""XDG-compliant application paths with testable roots."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class StatePaths:
    config: Path
    data: Path
    cache: Path
    runtime: Path

    @classmethod
    def from_environment(cls, env: dict[str, str] | None = None) -> "StatePaths":
        values = os.environ if env is None else env
        home = Path(values.get("HOME", "~")).expanduser()
        app = "loofi-fedora-tweaks"
        runtime_base = Path(values.get("XDG_RUNTIME_DIR", values.get("XDG_CACHE_HOME", str(home / ".cache"))))
        return cls(
            config=Path(values.get("XDG_CONFIG_HOME", str(home / ".config"))) / app,
            data=Path(values.get("XDG_DATA_HOME", str(home / ".local/share"))) / app,
            cache=Path(values.get("XDG_CACHE_HOME", str(home / ".cache"))) / app,
            runtime=runtime_base / app,
        )

    def ensure(self) -> None:
        for path in (self.config, self.data, self.cache, self.runtime):
            path.mkdir(parents=True, exist_ok=True, mode=0o700)
