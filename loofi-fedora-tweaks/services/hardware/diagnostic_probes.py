"""Read-only audio and Bluetooth probes with one shared deadline.

Only aggregate device metadata is retained; names, addresses and raw output
never enter troubleshooting history. Individual commands are bounded so that
cancellation is observed between probes within two seconds.
"""

from __future__ import annotations

import json
import math
import os
import pwd
import re
import selectors
import shutil
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

MAX_OUTPUT_BYTES = 65536


@dataclass(frozen=True)
class HardwareDiagnosticResult:
    facts: dict[str, Any]
    state: str
    reason_code: str = ""
    errors: dict[str, str] = field(default_factory=dict)


class HardwareDiagnosticProbe:
    """Run a fixed collection profile without service or device mutations."""

    def __init__(
        self, *, runner: Callable[..., Any] | None = None,
        which: Callable[[str], str | None] = shutil.which,
        monotonic: Callable[[], float] = time.monotonic,
        read_text: Callable[[str], str] = lambda path: Path(path).read_text(encoding="utf-8"),
        listdir: Callable[[str], list[str]] = os.listdir,
        current_user: Callable[[], str] = lambda: pwd.getpwuid(os.getuid()).pw_name,
    ) -> None:
        self.runner = runner or _run_bounded
        self.which = which
        self.monotonic = monotonic
        self.read_text = read_text
        self.listdir = listdir
        self.current_user = current_user

    def collect(self, kind: str, *, cancellation: Any, budget: float = 14.0) -> HardwareDiagnosticResult:
        if kind not in {"audio", "bluetooth", "energy", "display", "input", "printer"}:
            raise ValueError("Unknown hardware diagnostic profile.")
        deadline = self.monotonic() + min(budget, 14.0)
        facts: dict[str, Any] = {}
        errors: list[str] = []
        field_errors: dict[str, str] = {}

        def fail(key: str, reason: str) -> None:
            errors.append(reason)
            field_errors[key] = reason

        def read(key: str, vector: list[str], parser: Callable[[str], Any], *, inactive_ok: bool = False) -> None:
            facts[key] = None
            if cancellation.is_cancelled():
                fail(key, "cancelled")
                return
            remaining = deadline - self.monotonic()
            if remaining <= 0:
                fail(key, "timed-out")
                return
            resolved = self.which(vector[0])
            if not resolved:
                fail(key, "tool-unavailable")
                return
            try:
                result = self.runner(
                    [resolved, *vector[1:]], capture_output=True, text=True, check=False,
                    timeout=min(2.0, remaining), env={**os.environ, "LC_ALL": "C"},
                    cancel_check=cancellation.is_cancelled,
                )
                if getattr(result, "cancelled", False):
                    fail(key, "cancelled")
                    return
                if getattr(result, "output_truncated", False) or len(result.stdout.encode("utf-8", errors="replace")) > MAX_OUTPUT_BYTES:
                    fail(key, "output-too-large")
                    return
                # systemctl is-active uses exit status 3 for a known inactive unit.
                if result.returncode != 0 and not (inactive_ok and result.returncode == 3):
                    fail(key, "probe-failed")
                    return
                facts[key] = parser(result.stdout)
                field_errors.pop(key, None)
            except subprocess.TimeoutExpired:
                fail(key, "timed-out")
            except (OSError, subprocess.SubprocessError):
                fail(key, "probe-failed")
            except (TypeError, ValueError, KeyError):
                fail(key, "invalid-response")

        if kind == "audio":
            for service in ("pipewire", "wireplumber"):
                read(f"{service}_state", ["systemctl", "--user", "is-active", f"{service}.service"], _service_state, inactive_ok=True)
            read("default_sink_id", ["wpctl", "inspect", "@DEFAULT_AUDIO_SINK@"], _sink_id)
            read("output_volume", ["wpctl", "get-volume", "@DEFAULT_AUDIO_SINK@"], _volume)
        elif kind == "bluetooth":
            read("service_state", ["systemctl", "is-active", "bluetooth.service"], _service_state, inactive_ok=True)
            read("adapter", ["bluetoothctl", "show"], _adapter)
            read("radio", ["rfkill", "--json", "--output", "TYPE,SOFT,HARD"], _radio)
            read("paired_device_count", ["bluetoothctl", "devices", "Paired"], _paired_count)
        elif kind == "energy":
            error_count = len(errors)
            facts.update(_battery_facts(self.listdir, self.read_text, errors, cancellation))
            if len(errors) > error_count:
                field_errors["battery_inventory"] = errors[error_count]
            read("power_profile", ["powerprofilesctl", "get"], _power_profile)
        elif kind == "display":
            read("displays", ["kscreen-doctor", "--json"], _displays)
        elif kind == "input":
            error_count = len(errors)
            input_facts, touchpad_names = _input_facts(self.listdir, self.read_text, errors, cancellation)
            facts.update(input_facts)
            if len(errors) > error_count:
                field_errors["input_devices"] = errors[error_count]
            error_count = len(errors)
            facts["touchpad_setting"] = _touchpad_setting(
                self.read_text, errors, touchpad_names, cancellation=cancellation,
            )
            if len(errors) > error_count:
                field_errors["touchpad_setting"] = errors[error_count]
        else:
            read("cups_state", ["systemctl", "is-active", "cups.service"], _service_state, inactive_ok=True)
            read("queues", ["lpstat", "-p"], _printer_queues)
            read("queue_acceptance", ["lpstat", "-a"], _printer_acceptance)
            try:
                user = self.current_user()
            except (KeyError, OSError, TypeError):
                user = ""
            if not user or len(user) > 256 or any(ord(char) < 32 for char in user):
                facts["pending_job_count"] = None
                fail("pending_job_count", "current-user-unavailable")
            else:
                read("pending_job_count", ["lpstat", "-W", "not-completed", "-u", user], _printer_jobs)
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
        return HardwareDiagnosticResult(facts, state, reason, field_errors)


def _run_bounded(
    args: list[str], *, capture_output: bool, text: bool, check: bool,
    timeout: float, env: dict[str, str], cancel_check: Callable[[], bool],
) -> subprocess.CompletedProcess[str]:
    """Read stdout incrementally and terminate as soon as its fixed cap is exceeded."""
    del capture_output, check, text  # stderr is intentionally discarded to avoid retaining private details.
    process = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, env=env)
    output = bytearray()
    truncated = False
    cancelled = False
    deadline = time.monotonic() + timeout
    selector = selectors.DefaultSelector()
    assert process.stdout is not None
    selector.register(process.stdout, selectors.EVENT_READ)
    try:
        while selector.get_map():
            if cancel_check():
                cancelled = True
                process.kill()
                break
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                process.kill()
                raise subprocess.TimeoutExpired(args, timeout)
            ready = selector.select(min(remaining, 0.05))
            if not ready:
                continue
            chunk = os.read(process.stdout.fileno(), min(8192, MAX_OUTPUT_BYTES + 1 - len(output)))
            if not chunk:
                selector.unregister(process.stdout)
                break
            output.extend(chunk)
            if len(output) > MAX_OUTPUT_BYTES:
                truncated = True
                process.kill()
                break
        returncode = process.wait(timeout=max(0.01, deadline - time.monotonic()))
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait()
        raise
    finally:
        selector.close()
        process.stdout.close()
    decoded = output.decode("utf-8", errors="replace")
    result: subprocess.CompletedProcess[str] = subprocess.CompletedProcess[str](args, returncode, decoded, "")
    result.output_truncated = truncated  # type: ignore[attr-defined]
    result.cancelled = cancelled  # type: ignore[attr-defined]
    return result


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


def _power_profile(output: str) -> str:
    value = output.strip()
    if value not in {"power-saver", "balanced", "performance"}:
        raise ValueError("Unknown power profile.")
    return value


def _battery_facts(listdir: Callable[[str], list[str]], read_text: Callable[[str], str], errors: list[str], cancellation: Any) -> dict[str, Any]:
    root = "/sys/class/power_supply"
    facts: dict[str, Any] = {"battery_count": None, "batteries": None, "ac_online": None}
    try:
        entries = sorted(listdir(root))
        if len(entries) > 128:
            errors.append("incomplete-observation")
            entries = entries[:128]
        batteries = []
        ac_values = []
        for entry in entries:
            if cancellation.is_cancelled():
                errors.append("cancelled")
                break
            base = f"{root}/{entry}"
            try:
                kind = read_text(f"{base}/type").strip()
                if kind == "Battery":
                    item: dict[str, Any] = {
                        "status": None,
                        "capacity_percent": None,
                        "capacity_vs_design_percent": None,
                        "capacity_basis": None,
                    }
                    try:
                        status = read_text(f"{base}/status").strip()
                        if status not in {"Charging", "Discharging", "Full", "Not charging", "Unknown"}:
                            raise ValueError
                        item["status"] = status
                    except (OSError, ValueError):
                        errors.append("incomplete-observation")
                    # Capacity is the kernel-reported charge level, not a health report.
                    try:
                        capacity = read_text(f"{base}/capacity").strip()
                        if re.fullmatch(r"\d{1,3}", capacity) and 0 <= int(capacity) <= 100:
                            item["capacity_percent"] = int(capacity)
                        else:
                            errors.append("incomplete-observation")
                    except OSError:
                        errors.append("incomplete-observation")
                    for full_field, design_field, basis in (
                        ("energy_full", "energy_full_design", "energy"),
                        ("charge_full", "charge_full_design", "charge"),
                    ):
                        try:
                            full = read_text(f"{base}/{full_field}").strip()
                            design = read_text(f"{base}/{design_field}").strip()
                        except OSError:
                            continue
                        if full.isdigit() and design.isdigit() and int(design) > 0:
                            estimate = round(100 * int(full) / int(design))
                            if 0 <= estimate <= 150:
                                item["capacity_vs_design_percent"] = min(100, estimate)
                                item["capacity_basis"] = basis
                                break
                    if item["capacity_vs_design_percent"] is None:
                        # Some batteries expose neither charge nor energy capacity.
                        # Keep their observed status/capacity and report the limitation.
                        errors.append("incomplete-observation")
                    batteries.append(item)
                elif kind in {"Mains", "USB", "USB_C"}:
                    online = read_text(f"{base}/online").strip()
                    if online in {"0", "1"}:
                        ac_values.append(online == "1")
            except (OSError, ValueError):
                errors.append("incomplete-observation")
        facts["battery_count"] = len(batteries)
        facts["batteries"] = batteries
        facts["ac_online"] = any(ac_values) if ac_values else None
    except OSError:
        errors.append("probe-failed")
    return facts


def _displays(output: str) -> dict[str, Any]:
    data = json.loads(output)
    rows = data.get("outputs", data) if isinstance(data, dict) else data
    if not isinstance(rows, list) or len(rows) > 64 or any(not isinstance(row, dict) for row in rows):
        raise ValueError("Invalid display inventory.")
    displays = []
    for row in rows:
        if not isinstance(row.get("connected"), bool):
            raise ValueError("Display connection state is unknown.")
        item: dict[str, Any] = {"connected": row["connected"], "enabled": row.get("enabled") if isinstance(row.get("enabled"), bool) else None,
                                "width": None, "height": None, "refresh_hz": None, "scale": None}
        mode = row.get("currentMode") or row.get("mode")
        if mode is None:
            modes = row.get("modes", [])
            if not isinstance(modes, list) or len(modes) > 128 or any(not isinstance(candidate, dict) for candidate in modes):
                raise ValueError("Invalid KScreen mode inventory.")
            current_mode_id = row.get("currentModeId")
            if current_mode_id is not None and (isinstance(current_mode_id, bool) or not isinstance(current_mode_id, (str, int))):
                raise ValueError("Invalid KScreen current mode identifier.")
            matching_modes = [candidate for candidate in modes if str(candidate.get("id")) == str(current_mode_id)]
            if len(matching_modes) > 1:
                raise ValueError("KScreen returned duplicate current mode identifiers.")
            if matching_modes:
                mode = matching_modes[0]
        if isinstance(mode, dict):
            size = mode.get("size")
            rate = mode.get("refreshRate")
            if isinstance(rate, (int, float)) and math.isfinite(rate) and 0 < rate <= 1000:
                item["refresh_hz"] = round(float(rate), 2)
        else:
            size = None
        if size is None:
            size = row.get("size")
        if isinstance(size, dict):
            for key in ("width", "height"):
                value = size.get(key)
                if isinstance(value, int) and not isinstance(value, bool) and 0 < value <= 32768:
                    item[key] = value
        scale = row.get("scale")
        if isinstance(scale, (int, float)) and math.isfinite(scale) and 0 < scale <= 10:
            item["scale"] = round(float(scale), 2)
        displays.append(item)
    return {"count": len(displays), "connected_count": sum(d["connected"] for d in displays),
            "active_count": sum(d["enabled"] is True for d in displays), "displays": displays}


def _input_facts(
    listdir: Callable[[str], list[str]], read_text: Callable[[str], str], errors: list[str], cancellation: Any,
) -> tuple[dict[str, Any], tuple[str, ...]]:
    root = "/sys/class/input"
    counts: dict[str, Any] = {"devices": None, "keyboards": None, "pointers": None, "touchpads": None}
    try:
        entries = sorted(name for name in listdir(root) if name.startswith("event"))
        counts = {"devices": 0, "keyboards": 0, "pointers": 0, "touchpads": 0}
        touchpad_names: list[str] = []
        if len(entries) > 256:
            errors.append("incomplete-observation")
            entries = entries[:256]
        for name in entries:
            if cancellation.is_cancelled():
                errors.append("cancelled")
                break
            try:
                device_name = read_text(f"{root}/{name}/device/name").strip()
                device = device_name.casefold()
            except OSError:
                errors.append("incomplete-observation")
                continue
            counts["devices"] += 1
            if "keyboard" in device:
                counts["keyboards"] += 1
            if any(word in device for word in ("mouse", "touchpad", "trackpoint", "tablet")):
                counts["pointers"] += 1
            if "touchpad" in device:
                counts["touchpads"] += 1
                touchpad_names.append(device_name)
    except OSError:
        errors.append("probe-failed")
        touchpad_names = []
    return counts, tuple(dict.fromkeys(touchpad_names))


def _touchpad_setting(
    read_text: Callable[[str], str], errors: list[str], touchpad_names: tuple[str, ...], *, cancellation: Any,
) -> bool | None:
    if not touchpad_names:
        return None
    if cancellation.is_cancelled():
        errors.append("cancelled")
        return None
    try:
        config = read_text(os.path.expanduser("~/.config/kcminputrc"))
    except OSError:
        errors.append("incomplete-observation")
        return None
    if len(config.encode("utf-8", errors="replace")) > MAX_OUTPUT_BYTES:
        errors.append("output-too-large")
        return None
    values_by_name: dict[str, list[bool]] = {}
    section_name: str | None = None
    for line in config.splitlines():
        stripped = line.strip()
        if stripped.startswith("["):
            section = re.fullmatch(r"\[Libinput\]\[[^\]]+\]\[[^\]]+\]\[([^\]]+)\]", stripped, re.IGNORECASE)
            section_name = section.group(1).casefold() if section else None
        elif section_name is not None:
            value = re.fullmatch(r"\s*Enabled=(true|false)\s*", line, re.IGNORECASE)
            if value:
                values_by_name.setdefault(section_name, []).append(value.group(1).casefold() == "true")
    values = []
    for name in touchpad_names:
        matches = values_by_name.get(name.casefold(), [])
        if not matches or len(set(matches)) != 1:
            errors.append("incomplete-observation")
            return None
        values.append(matches[0])
    if len(set(values)) != 1:
        errors.append("incomplete-observation")
        return None
    return values[0]


def _printer_queues(output: str) -> dict[str, int]:
    lines = [line for line in output.splitlines() if line.strip()]
    if len(lines) > 256:
        raise ValueError("Printer inventory is too large.")
    # lpstat output contains private queue names; retain only aggregate states.
    counts = {"total": 0, "enabled": 0, "disabled": 0}
    previous_disabled = False
    for line in lines:
        if line[:1].isspace():
            if previous_disabled:
                continue
            raise ValueError("Unknown printer status response.")
        match = re.match(r"^printer\s+\S+\s+(.+)$", line, re.IGNORECASE)
        if match is None:
            raise ValueError("Unknown printer status response.")
        status = re.search(r"\b(enabled|disabled)\s+since\b", match.group(1), re.IGNORECASE)
        if status is None:
            raise ValueError("Unknown printer enabled state.")
        disabled = status.group(1).casefold() == "disabled"
        counts["total"] += 1
        counts["disabled"] += int(disabled)
        counts["enabled"] += int(not disabled)
        previous_disabled = disabled
    return counts


def _printer_acceptance(output: str) -> dict[str, int]:
    lines = [line for line in output.splitlines() if line.strip()]
    if len(lines) > 256:
        raise ValueError("Printer acceptance inventory is too large.")
    counts = {"total": 0, "accepting": 0, "rejecting": 0}
    previous_rejecting = False
    for line in lines:
        if line[:1].isspace():
            if previous_rejecting:
                continue
            raise ValueError("Unknown printer acceptance response.")
        # lpstat -a begins each row with the queue name. It is parsed only to
        # locate the state and is never retained.
        match = re.match(r"^\S+\s+(accepts|not accepting)\s+requests\b", line, re.IGNORECASE)
        if match is None:
            raise ValueError("Unknown printer acceptance response.")
        accepting = match.group(1).casefold() == "accepts"
        counts["total"] += 1
        counts["accepting"] += int(accepting)
        counts["rejecting"] += int(not accepting)
        previous_rejecting = not accepting
    return counts


def _printer_jobs(output: str) -> int:
    lines = [line for line in output.splitlines() if line.strip()]
    if len(lines) > 4096 or any(not re.match(r"^\S+-\d+\s+", line) for line in lines):
        raise ValueError("Unknown pending-job response.")
    return len(lines)
