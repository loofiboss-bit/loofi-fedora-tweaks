"""Read-only audio and Bluetooth probes with one shared deadline.

Only aggregate device metadata is retained; names, addresses and raw output
never enter troubleshooting history. Individual commands are bounded so that
cancellation is observed between probes within two seconds.
"""

from __future__ import annotations

import json
import math
import os
import re
import shutil
import subprocess
import time
from dataclasses import dataclass
from typing import Any, Callable


@dataclass(frozen=True)
class HardwareDiagnosticResult:
    facts: dict[str, Any]
    state: str
    reason_code: str = ""


class HardwareDiagnosticProbe:
    """Run a fixed collection profile without service or device mutations."""

    def __init__(
        self, *, runner: Callable[..., Any] = subprocess.run,
        which: Callable[[str], str | None] = shutil.which,
        monotonic: Callable[[], float] = time.monotonic,
    ) -> None:
        self.runner = runner
        self.which = which
        self.monotonic = monotonic

    def collect(self, kind: str, *, cancellation: Any, budget: float = 14.0) -> HardwareDiagnosticResult:
        if kind not in {"audio", "bluetooth"}:
            raise ValueError("Unknown hardware diagnostic profile.")
        deadline = self.monotonic() + min(budget, 14.0)
        facts: dict[str, Any] = {}
        errors: list[str] = []

        def read(key: str, vector: list[str], parser: Callable[[str], Any], *, inactive_ok: bool = False) -> None:
            facts[key] = None
            if cancellation.is_cancelled():
                errors.append("cancelled")
                return
            remaining = deadline - self.monotonic()
            if remaining <= 0:
                errors.append("timed-out")
                return
            resolved = self.which(vector[0])
            if not resolved:
                errors.append("tool-unavailable")
                return
            try:
                result = self.runner(
                    [resolved, *vector[1:]], capture_output=True, text=True, check=False,
                    timeout=min(2.0, remaining), env={**os.environ, "LC_ALL": "C"},
                )
                # systemctl is-active uses exit status 3 for a known inactive unit.
                if result.returncode != 0 and not (inactive_ok and result.returncode == 3):
                    errors.append("probe-failed")
                    return
                if len(result.stdout) > 65536:
                    errors.append("invalid-response")
                    return
                facts[key] = parser(result.stdout)
            except subprocess.TimeoutExpired:
                errors.append("timed-out")
            except (OSError, subprocess.SubprocessError):
                errors.append("probe-failed")
            except (TypeError, ValueError, KeyError):
                errors.append("invalid-response")

        if kind == "audio":
            for service in ("pipewire", "wireplumber"):
                read(f"{service}_state", ["systemctl", "--user", "is-active", f"{service}.service"], _service_state, inactive_ok=True)
            read("default_sink_id", ["wpctl", "inspect", "@DEFAULT_AUDIO_SINK@"], _sink_id)
            read("output_volume", ["wpctl", "get-volume", "@DEFAULT_AUDIO_SINK@"], _volume)
        else:
            read("service_state", ["systemctl", "is-active", "bluetooth.service"], _service_state, inactive_ok=True)
            read("adapter", ["bluetoothctl", "show"], _adapter)
            read("radio", ["rfkill", "--json", "--output", "TYPE,SOFT,HARD"], _radio)
            read("paired_device_count", ["bluetoothctl", "devices", "Paired"], _paired_count)
        usable = any(value is not None for value in facts.values())
        if cancellation.is_cancelled():
            reason = "cancelled"
        elif "timed-out" in errors:
            reason = "timed-out"
        elif errors:
            reason = errors[0]
        else:
            reason = ""
        state = "partial" if usable and errors else "completed" if usable else "unavailable"
        return HardwareDiagnosticResult(facts, state, reason)


def _service_state(output: str) -> str:
    state = output.strip()
    if state not in {"active", "inactive", "failed", "activating", "deactivating"}:
        raise ValueError("Unknown service state.")
    return state


def _sink_id(output: str) -> int:
    match = re.search(r"^id (\d+), type PipeWire:Interface:Node", output, re.MULTILINE)
    if match is None:
        raise ValueError("No default output was verified.")
    return int(match.group(1))


def _volume(output: str) -> dict[str, Any]:
    match = re.fullmatch(r"Volume:\s*(\d+(?:\.\d+)?)\s*(\[MUTED\])?\s*", output)
    if match is None:
        raise ValueError("Unknown volume response.")
    volume = float(match.group(1))
    if not math.isfinite(volume) or not 0 <= volume <= 10:
        raise ValueError("Volume is outside the supported range.")
    return {"level": volume, "muted": bool(match.group(2))}


def _adapter(output: str) -> dict[str, Any]:
    if not re.search(r"^Controller [0-9A-Fa-f:]{17}\b", output, re.MULTILINE):
        raise ValueError("No controller metadata was returned.")
    match = re.search(r"^\s*Powered:\s*(yes|no)\s*$", output, re.MULTILINE)
    if match is None:
        raise ValueError("Controller power state is unknown.")
    return {"present": True, "powered": match.group(1) == "yes"}


def _radio(output: str) -> dict[str, Any]:
    rows = json.loads(output)["rfkilldevices"]
    if not isinstance(rows, list) or len(rows) > 128:
        raise ValueError("Invalid radio inventory.")
    if any(not isinstance(row, dict) for row in rows):
        raise ValueError("Invalid radio row.")
    bluetooth = [row for row in rows if row.get("type") == "bluetooth"]
    if any(row.get(key) not in {"blocked", "unblocked"} for row in bluetooth for key in ("soft", "hard")):
        raise ValueError("Unknown radio block state.")
    return {"adapter_count": len(bluetooth), "soft_blocked": any(row["soft"] == "blocked" for row in bluetooth),
            "hard_blocked": any(row["hard"] == "blocked" for row in bluetooth)}


def _paired_count(output: str) -> int:
    lines = [line for line in output.splitlines() if line.strip()]
    if len(lines) > 128 or any(not re.fullmatch(r"Device [0-9A-Fa-f:]{17} .+", line) for line in lines):
        raise ValueError("Unknown paired-device response.")
    return len(lines)
