"""Fixed, read-only resolution for native Plasma desktop handoffs.

The product catalog stores opaque ``NativeHandoffId`` values only. This module
owns the complete command allowlist and verifies that a destination exists
before the UI may request a non-blocking launch.
"""

from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass
from types import MappingProxyType
from typing import Callable, Mapping, Sequence

from core.catalog_models import CapabilityState, NativeHandoffId


@dataclass(frozen=True)
class NativeHandoffTarget:
    """One immutable allowlisted desktop destination."""

    handoff_id: NativeHandoffId
    label: str
    executable: str
    arguments: tuple[str, ...] = ()
    kcm_id: str | None = None


@dataclass(frozen=True)
class NativeHandoffAvailability:
    """Truthful presentation state for one native destination."""

    target: NativeHandoffTarget
    state: CapabilityState
    detail: str

    @property
    def available(self) -> bool:
        return self.state is CapabilityState.NATIVE_HANDOFF


@dataclass(frozen=True)
class NativeHandoffLaunch:
    """Ephemeral launch vector resolved from the fixed allowlist."""

    program: str
    arguments: tuple[str, ...]


_TARGETS: Mapping[NativeHandoffId, NativeHandoffTarget] = MappingProxyType(
    {
        NativeHandoffId.PLASMA_DISCOVER: NativeHandoffTarget(
            NativeHandoffId.PLASMA_DISCOVER,
            "Plasma Discover",
            "plasma-discover",
        ),
        NativeHandoffId.PLASMA_NETWORK_CONNECTIONS: NativeHandoffTarget(
            NativeHandoffId.PLASMA_NETWORK_CONNECTIONS,
            "Plasma Network Connections",
            "kcmshell6",
            ("kcm_networkmanagement",),
            "kcm_networkmanagement",
        ),
        NativeHandoffId.PLASMA_APPEARANCE: NativeHandoffTarget(
            NativeHandoffId.PLASMA_APPEARANCE,
            "Plasma Global Theme",
            "kcmshell6",
            ("kcm_lookandfeel",),
            "kcm_lookandfeel",
        ),
        NativeHandoffId.PLASMA_DISPLAY: NativeHandoffTarget(
            NativeHandoffId.PLASMA_DISPLAY,
            "Plasma Display Configuration",
            "kcmshell6",
            ("kcm_kscreen",),
            "kcm_kscreen",
        ),
        NativeHandoffId.PLASMA_WINDOW_MANAGEMENT: NativeHandoffTarget(
            NativeHandoffId.PLASMA_WINDOW_MANAGEMENT,
            "Plasma Window Management",
            "kcmshell6",
            ("kcm_kwinoptions",),
            "kcm_kwinoptions",
        ),
    }
)


class NativeHandoffService:
    """Resolve and verify native handoffs without importing PyQt."""

    def __init__(
        self,
        *,
        which: Callable[[str], str | None] = shutil.which,
        runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
        probe_timeout: float = 3.0,
    ) -> None:
        self._which = which
        self._runner = runner
        self._probe_timeout = probe_timeout

    @staticmethod
    def target(handoff_id: NativeHandoffId | str) -> NativeHandoffTarget:
        """Return static metadata for an allowlisted ID."""
        normalized = NativeHandoffId(handoff_id)
        return _TARGETS[normalized]

    @staticmethod
    def targets() -> tuple[NativeHandoffTarget, ...]:
        """Return the complete allowlist in enum order."""
        return tuple(_TARGETS[handoff_id] for handoff_id in NativeHandoffId)

    def availability(
        self,
        handoff_id: NativeHandoffId | str,
    ) -> NativeHandoffAvailability:
        """Probe an executable and, for KCM targets, the exact module ID."""
        target = self.target(handoff_id)
        resolved = self._which(target.executable)
        if not resolved:
            return NativeHandoffAvailability(
                target,
                CapabilityState.UNAVAILABLE,
                f"{target.label} is not installed on this system.",
            )

        if target.kcm_id is not None:
            try:
                result = self._runner(
                    [resolved, "--list"],
                    capture_output=True,
                    text=True,
                    check=False,
                    timeout=self._probe_timeout,
                )
            except (OSError, subprocess.SubprocessError):
                return NativeHandoffAvailability(
                    target,
                    CapabilityState.UNAVAILABLE,
                    "Plasma System Settings modules could not be inspected.",
                )
            if result.returncode != 0 or target.kcm_id not in self._listed_kcm_ids(
                result.stdout
            ):
                return NativeHandoffAvailability(
                    target,
                    CapabilityState.UNAVAILABLE,
                    f"The required module {target.kcm_id} is not available.",
                )

        return NativeHandoffAvailability(
            target,
            CapabilityState.NATIVE_HANDOFF,
            f"Open {target.label} in the native Plasma interface.",
        )

    def prepare_launch(
        self,
        handoff_id: NativeHandoffId | str,
    ) -> NativeHandoffLaunch | None:
        """Revalidate a target and return its fixed, ephemeral launch vector."""
        availability = self.availability(handoff_id)
        if not availability.available:
            return None
        resolved = self._which(availability.target.executable)
        if not resolved:
            return None
        return NativeHandoffLaunch(resolved, availability.target.arguments)

    @staticmethod
    def _listed_kcm_ids(output: str) -> frozenset[str]:
        """Extract exact module identifiers from ``kcmshell6 --list`` output."""
        identifiers = []
        for line in output.splitlines():
            fields: Sequence[str] = line.strip().split(maxsplit=1)
            if fields and fields[0].startswith("kcm_"):
                identifiers.append(fields[0])
        return frozenset(identifiers)


if frozenset(_TARGETS) != frozenset(NativeHandoffId):
    raise RuntimeError("Native handoff allowlist must cover every NativeHandoffId")
