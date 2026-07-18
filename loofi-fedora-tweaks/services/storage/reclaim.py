"""Bounded, read-only size probes for the v15 disk reclaim preview."""

from __future__ import annotations

import re
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
        result = self._runner(["du", "-sb", "/var/cache/dnf", "/var/cache/libdnf5"], 10)
        if result is None or result.returncode not in {0, 1}:
            return None
        sizes = []
        for line in result.stdout.splitlines():
            token = line.split(maxsplit=1)[0] if line.split() else ""
            if token.isdigit():
                sizes.append(int(token))
        return sum(sizes) if sizes else None

    def _journal_bytes(self) -> int | None:
        result = self._runner(["journalctl", "--disk-usage", "--no-pager"], 10)
        if result is None or result.returncode != 0:
            return None
        return _parse_human_size(result.stdout)


def _parse_human_size(text: str) -> int | None:
    match = re.search(
        r"(\d+(?:\.\d+)?)\s*([KMGT]?)(?:i?B|bytes?)?\b",
        str(text),
        re.IGNORECASE,
    )
    if not match:
        return None
    value = float(match.group(1))
    factor = {"": 1, "K": 1024, "M": 1024**2, "G": 1024**3, "T": 1024**4}[match.group(2).upper()]
    return int(value * factor)
