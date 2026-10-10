"""Bounded, read-only size probes for the v15 disk reclaim preview."""

from __future__ import annotations

import re
import os
import subprocess
from collections.abc import Callable

from core.workflows import ReclaimAnalysis, ReclaimAnalysisService
from services.system import SystemManager

Runner = Callable[[list[str], int], subprocess.CompletedProcess[str] | None]


class ReclaimProbeService:
    """Measure supported reclaim categories without deleting or planning work."""

    def __init__(self, runner: Runner | None = None):
        self._runner = runner or self._run

    @staticmethod
    def _run(command: list[str], timeout: int) -> subprocess.CompletedProcess[str] | None:
        try:
            return subprocess.run(
                command,
                capture_output=True,
                text=True,
                check=False,
                timeout=timeout,
            )
        except (OSError, subprocess.SubprocessError, subprocess.TimeoutExpired):
            return None

    def analyze(self) -> ReclaimAnalysis:
        atomic = SystemManager.is_atomic()
        package_bytes = None if atomic else self._package_cache_bytes()
        return ReclaimAnalysisService.build(
            atomic=atomic,
            package_cache_bytes=package_bytes,
            journal_bytes=self._journal_bytes(),
        )

    def _package_cache_bytes(self) -> int | None:
        paths = []
        for path in ("/var/cache/dnf", "/var/cache/libdnf5"):
            try:
                os.stat(path)
            except FileNotFoundError:
                continue
            except OSError:
                return None
            paths.append(path)
        if not paths:
            return 0
        result = self._runner(["du", "-sb", *paths], 10)
        if result is None or result.returncode != 0:
            return None
        sizes = {}
        for line in result.stdout.splitlines():
            fields = line.split(maxsplit=1)
            if len(fields) != 2 or not fields[0].isdigit() or fields[1] not in paths or fields[1] in sizes:
                return None
            sizes[fields[1]] = int(fields[0])
        return sum(sizes.values()) if set(sizes) == set(paths) else None

    def _journal_bytes(self) -> int | None:
        result = self._runner(["journalctl", "--disk-usage", "--no-pager"], 10)
        if result is None or result.returncode != 0:
            return None
        return _parse_human_size(result.stdout)


def _parse_human_size(text: str) -> int | None:
    match = re.search(
        r"(\d+(?:\.\d+)?)\s*([KMGT])(?:i?B)?\b|(\d+(?:\.\d+)?)\s*(?:B|bytes?)\b",
        str(text),
        re.IGNORECASE,
    )
    if not match:
        return None
    value = float(match.group(1) or match.group(3))
    factor = {"": 1, "K": 1024, "M": 1024**2, "G": 1024**3, "T": 1024**4}[(match.group(2) or "").upper()]
    return int(value * factor)
