"""Small, read-only storage observations for the existing Health workflow."""
from __future__ import annotations

import os
import math
import time
from collections.abc import Callable
from dataclasses import asdict, dataclass

from services.hardware.disk import DiskManager
from services.storage.reclaim import ReclaimProbeService


@dataclass(frozen=True)
class FilesystemObservation:
    paths: tuple[str, ...]
    state: str
    total_bytes: int | None = None
    used_bytes: int | None = None
    free_bytes: int | None = None
    percent_used: float | None = None


@dataclass(frozen=True)
class SpaceGuide:
    sampled_at: float
    atomic: bool
    filesystems: tuple[FilesystemObservation, ...]
    package_cache_bytes: int | None
    journal_bytes: int | None

    @property
    def partial(self) -> bool:
        return (any(row.state != "observed" for row in self.filesystems)
                or (not self.atomic and self.package_cache_bytes is None) or self.journal_bytes is None)

    def to_dict(self) -> dict:
        data = asdict(self)
        data["filesystems"] = [{**asdict(row), "paths": ", ".join(row.paths)} for row in self.filesystems]
        return data


class SpaceGuideService:
    """Measure three public paths, grouping shared devices without summing them."""

    def __init__(self, *, clock: Callable[[], float] = time.time):
        self.clock = clock

    def collect(self) -> SpaceGuide:
        rows: list[FilesystemObservation] = []
        devices: dict[int, int] = {}
        for path in ("/", "/home", "/var"):
            try:
                device = os.stat(path).st_dev
            except OSError:
                rows.append(FilesystemObservation((path,), "unknown"))
                continue
            if device in devices:
                index = devices[device]
                old = rows[index]
                rows[index] = FilesystemObservation((*old.paths, path), old.state, old.total_bytes,
                                                    old.used_bytes, old.free_bytes, old.percent_used)
                continue
            usage = DiskManager.get_disk_usage(path)
            if (usage is None or usage.total_bytes <= 0 or not 0 <= usage.used_bytes <= usage.total_bytes
                    or usage.free_bytes < 0 or not math.isfinite(usage.percent_used) or not 0 <= usage.percent_used <= 100):
                rows.append(FilesystemObservation((path,), "unknown"))
                continue
            devices[device] = len(rows)
            rows.append(FilesystemObservation((path,), "observed", usage.total_bytes, usage.used_bytes,
                                              usage.free_bytes, usage.percent_used))
        analysis = ReclaimProbeService().analyze()
        measured = {row.id: row.estimated_bytes for row in analysis.categories}
        return SpaceGuide(self.clock(), analysis.atomic, tuple(rows), measured.get("package-cache"), measured.get("journal"))
