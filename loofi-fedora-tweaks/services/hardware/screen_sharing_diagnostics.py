"""Bounded screen-sharing metadata probes without capture or activation."""
from __future__ import annotations

import os
import re
import shutil
import subprocess
import time
from typing import Any, Callable

from services.hardware.diagnostic_probes import HardwareDiagnosticResult, _service_state


class ScreenSharingDiagnosticProbe:
    """Inspect only existing user services and an already-owned portal bus name."""

    def __init__(self, *, runner: Callable[..., Any] = subprocess.run,
                 which: Callable[[str], str | None] = shutil.which,
                 monotonic: Callable[[], float] = time.monotonic) -> None:
        self.runner, self.which, self.monotonic = runner, which, monotonic

    def collect(self, *, cancellation: Any, budget: float = 14.0) -> HardwareDiagnosticResult:
        deadline = self.monotonic() + max(0.0, min(14.0, budget))
        session_type = os.environ.get("XDG_SESSION_TYPE", "").lower()
        facts: dict[str, Any] = {"session_type": session_type if session_type in {"wayland", "x11"} else None}
        errors = [] if facts["session_type"] else ["session-type-unknown"]
        probes: list[tuple[str, list[str], Callable[[str], Any]]] = [
            (f"{service}_state", ["systemctl", "--user", "is-active", f"{service}.service"], _service_state)
            for service in ("pipewire", "wireplumber", "xdg-desktop-portal")
        ]
        probes.append((
            "available_source_types",
            ["busctl", "--user", "--auto-start=no", "get-property",
             "org.freedesktop.portal.Desktop", "/org/freedesktop/portal/desktop",
             "org.freedesktop.portal.ScreenCast", "AvailableSourceTypes"],
            _source_types,
        ))
        for key, vector, parser in probes:
            facts[key] = None
            if cancellation.is_cancelled():
                errors.append("cancelled")
                break
            remaining = deadline - self.monotonic()
            if remaining <= 0:
                errors.append("timed-out")
                break
            resolved = self.which(vector[0])
            if not resolved:
                errors.append("tool-unavailable")
                continue
            try:
                result = self.runner([resolved, *vector[1:]], capture_output=True, text=True, check=False,
                                     timeout=min(2.0, remaining), env={**os.environ, "LC_ALL": "C"})
                if result.returncode != 0 and not (vector[0] == "systemctl" and result.returncode == 3):
                    errors.append("probe-failed")
                    continue
                if len(result.stdout) > 65536:
                    raise ValueError("Response exceeds the bounded limit.")
                facts[key] = parser(result.stdout)
            except subprocess.TimeoutExpired:
                errors.append("timed-out")
            except (OSError, subprocess.SubprocessError):
                errors.append("probe-failed")
            except (TypeError, ValueError):
                errors.append("invalid-response")
        if cancellation.is_cancelled() and "cancelled" not in errors:
            errors.append("cancelled")
        usable = any(value is not None for value in facts.values())
        return HardwareDiagnosticResult(facts, "partial" if usable and errors else "completed" if usable else "unavailable",
                                        "cancelled" if cancellation.is_cancelled() else errors[0] if errors else "")


def _source_types(output: str) -> int:
    match = re.fullmatch(r"u\s+(\d+)\s*", output)
    if match is None or not 0 <= int(match.group(1)) <= 7:
        raise ValueError("Unknown ScreenCast source-type response.")
    return int(match.group(1))
