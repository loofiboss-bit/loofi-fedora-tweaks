"""Bounded, read-only dashboard metrics, shared by visible monitoring views."""

from __future__ import annotations

import math
import os
import platform
import re
import shutil
import subprocess
import time
from dataclasses import dataclass, field, replace
from datetime import datetime
from pathlib import Path
from typing import Callable

from core.actions.stores import ActionRunStore
from core.observability.timeline import HealthTimelineStore
from services.hardware.temperature import TemperatureManager
from services.software.update_overview import UpdateOverviewService
from services.system.system import SystemManager
from utils.performance import CpuSample, MemorySample, PerformanceCollector


@dataclass(frozen=True)
class MetricReading:
    """A measurement with explicit availability and provenance."""

    id: str
    group: str
    label: str
    value: float | None
    unit: str
    status: str
    source: str
    sampled_at: float | None
    reason: str = ""
    detail: str = ""
    high: float | None = None
    critical: float | None = None


@dataclass(frozen=True)
class DashboardSnapshot:
    metrics: tuple[MetricReading, ...]
    identity: dict[str, str]
    collected_at: float
    maintenance: dict[str, dict[str, object]] = field(default_factory=dict)
    cpu_per_core: tuple[float, ...] = ()


class DashboardService:
    """Synchronous domain adapter; callers schedule it outside the UI thread.

    Fast and slow groups can be refreshed independently. All differential
    counters use the existing monotonic collector and its 60-point buffers.
    Failed reads preserve a previous good measurement as explicitly stale.
    """

    FAST_GROUPS = frozenset({"cpu", "memory", "network", "disk"})
    SLOW_GROUPS = frozenset({"temperature", "battery", "gpu", "storage"})

    def __init__(self, *, collector: PerformanceCollector | None = None,
                 clock: Callable[[], float] = time.time) -> None:
        self.collector = collector or PerformanceCollector()
        self._clock = clock
        self._identity: dict[str, str] | None = None
        self._latest = DashboardSnapshot((), {}, 0.0)
        self._cpu_per_core: tuple[float, ...] = ()

    @property
    def latest_snapshot(self) -> DashboardSnapshot:
        return self._latest

    def reset_baselines(self) -> None:
        self.collector.reset_baselines()

    @staticmethod
    def _read(path: Path) -> str | None:
        try:
            with path.open(encoding="utf-8", errors="replace") as stream:
                return stream.read(4096).strip()
        except OSError:
            return None

    @classmethod
    def _number(cls, path: Path) -> float | None:
        text = cls._read(path)
        try:
            number = float(text) if text is not None else None
            return number if number is not None and math.isfinite(number) else None
        except ValueError:
            return None

    @staticmethod
    def _paths(pattern: str) -> list[Path]:
        import glob
        return [Path(item) for item in sorted(glob.glob(pattern))]

    def _facts(self) -> dict[str, str]:
        facts = {"hostname": platform.node(), "kernel": platform.release(),
                 "cpu": "Unknown", "os": "Unknown", "desktop": "Unknown", "deployment": "Unknown"}
        text = self._read(Path("/proc/cpuinfo")) or ""
        for line in text.splitlines():
            if line.startswith(("model name", "Hardware")) and ":" in line:
                facts["cpu"] = line.split(":", 1)[1].strip()
                break
        release = self._read(Path("/etc/os-release")) or ""
        for line in release.splitlines():
            if line.startswith("PRETTY_NAME="):
                facts["os"] = line.split("=", 1)[1].strip('"\'')
                break
        try:
            profile = SystemManager.get_platform_profile()
            facts["desktop"] = profile.desktop.value
            facts["deployment"] = profile.deployment_backend.value
        except (OSError, ValueError, AttributeError):
            pass
        return facts

    def _metric(self, identifier: str, group: str, label: str, value: float | None,
                unit: str, source: str, *, status: str | None = None,
                reason: str = "", detail: str = "", high: float | None = None,
                critical: float | None = None) -> MetricReading:
        state = status or ("ready" if value is not None else "error")
        return MetricReading(identifier, group, label, value, unit, state, source,
                             self._clock() if value is not None else None, reason, detail, high, critical)

    def _fast(self) -> list[MetricReading]:
        samples = self.collector.collect_all()
        cpu = samples["cpu"]
        self._cpu_per_core = tuple(cpu.per_core) if isinstance(cpu, CpuSample) and self.collector.sample_status("cpu") == "ready" else ()
        readings = []
        specs = [("cpu.usage", "cpu", "CPU", "percent", "%", "/proc/stat"),
                 ("memory.usage", "memory", "Memory", "percent", "%", "/proc/meminfo"),
                 ("network.receive", "network", "Network receive", "recv_rate", "B/s", "/proc/net/dev"),
                 ("network.send", "network", "Network send", "send_rate", "B/s", "/proc/net/dev"),
                 ("disk.read", "disk", "Disk read", "read_rate", "B/s", "/proc/diskstats"),
                 ("disk.write", "disk", "Disk write", "write_rate", "B/s", "/proc/diskstats")]
        for identifier, group, label, attribute, unit, source in specs:
            sample = samples["disk_io" if group == "disk" else group]
            sampling = group in {"cpu", "network", "disk"} and self.collector.sample_status(group) == "sampling"
            value = getattr(sample, attribute) if sample is not None and not sampling else None
            detail = ""
            if group == "memory" and isinstance(sample, MemorySample):
                detail = f"{self._human(sample.used_bytes)} / {self._human(sample.total_bytes)}"
            reason = "Collecting a new differential baseline" if sampling else ""
            if sample is None and not sampling:
                reason = "Counters could not be read or validated"
            readings.append(self._metric(identifier, group, label, value, unit, source,
                                         status="sampling" if sampling else None, reason=reason, detail=detail))
        return readings

    def _temperatures(self) -> list[MetricReading]:
        sensors = TemperatureManager.get_all_sensors()
        readings = [self._metric(f"temperature:{sensor.source or sensor.name + ':' + sensor.label}",
                                 "temperature", sensor.label, sensor.current, "°C", sensor.source or "/sys/class/hwmon",
                                 detail=sensor.name, high=sensor.high or None, critical=sensor.critical or None)
                    for sensor in sensors]
        if readings:
            return readings
        has_inputs = bool(self._paths("/sys/class/hwmon/hwmon*/temp*_input"))
        return [self._metric("temperature.none", "temperature", "Temperature", None, "°C", "/sys/class/hwmon",
                             status="error" if has_inputs else "unavailable",
                             reason="Sensors are unreadable or suspended" if has_inputs else "No temperature sensors detected")]

    def _batteries(self) -> list[MetricReading]:
        readings = []
        for directory in self._paths("/sys/class/power_supply/*"):
            if self._read(directory / "type") != "Battery":
                continue
            identifier = f"battery:{directory.name}"
            present = self._read(directory / "present")
            capacity = self._number(directory / "capacity") if present != "0" else None
            if capacity is not None and not 0 <= capacity <= 100:
                capacity = None
            if capacity is None and present != "0":
                for family in ("energy", "charge"):
                    current = self._number(directory / f"{family}_now")
                    full = self._number(directory / f"{family}_full")
                    if current is not None and full is not None and full > 0 and 0 <= current <= full:
                        capacity = round(current / full * 100, 1)
                        break
            state = self._read(directory / "status") or "Unknown charging status"
            readings.append(self._metric(identifier, "battery", directory.name, capacity, "%", str(directory),
                                         status="unavailable" if present == "0" else None,
                                         reason="Battery is not present" if present == "0" else "" if capacity is not None else "Charge level is unreadable",
                                         detail=state))
            if present == "0":
                continue
            health = None
            for family in ("energy", "charge"):
                full = self._number(directory / f"{family}_full")
                design = self._number(directory / f"{family}_full_design")
                if full is not None and full >= 0 and design is not None and design > 0:
                    health = round(full / design * 100, 1)
                    break
            readings.append(self._metric(identifier + ".health", "battery", f"{directory.name} health", health, "%",
                                         str(directory), status="ready" if health is not None else "unavailable",
                                         reason="" if health is not None else "Battery design capacity is unavailable"))
        return readings or [self._metric("battery.none", "battery", "Battery", None, "%", "/sys/class/power_supply",
                                         status="unavailable", reason="No battery detected")]

    def _storage(self) -> list[MetricReading]:
        readings = []
        seen = set()
        for label, path in (("System", Path("/")), ("Home", Path.home())):
            try:
                stat = os.statvfs(path)
                device = getattr(stat, "f_fsid", None)
                if device is None:
                    device = path.stat().st_dev
                if device in seen:
                    continue
                seen.add(device)
                total = stat.f_blocks * stat.f_frsize
                free = stat.f_bavail * stat.f_frsize
                if total <= 0:
                    raise ValueError("Filesystem capacity is unavailable")
                used = total - stat.f_bfree * stat.f_frsize
                readings.append(self._metric(f"storage:{path}", "storage", label, used / total * 100, "%", str(path),
                                             detail=f"{self._human(free)} available / {self._human(total)} total"))
            except (OSError, ValueError) as error:
                readings.append(self._metric(f"storage:{path}", "storage", label, None, "%", str(path), reason=str(error)))
        return readings

    def _gpus(self) -> list[MetricReading]:
        readings = []
        for card in self._paths("/sys/class/drm/card*"):
            if not re.fullmatch(r"card\d+", card.name):
                continue
            device = card / "device"
            vendor = self._read(device / "vendor")
            name = {"0x1002": "AMD", "0x10de": "NVIDIA", "0x8086": "Intel"}.get(vendor or "", "GPU")
            label = f"{name} {card.name}"
            identifier = f"gpu:{card.name}"
            status = self._read(device / "power/runtime_status")
            if status != "active":
                readings.append(self._metric(identifier, "gpu", label, None, "%", str(device), status="unavailable",
                                             reason="GPU is suspended" if status == "suspended" else "GPU power state is unknown; metrics were not queried"))
                continue
            if vendor == "0x1002":
                load = self._number(device / "gpu_busy_percent")
                if load is not None and not 0 <= load <= 100:
                    load = None
                readings.append(self._metric(identifier, "gpu", label, load, "%", str(device / "gpu_busy_percent"),
                                             reason="" if load is not None else "GPU utilization is unavailable"))
                used = self._number(device / "mem_info_vram_used")
                total = self._number(device / "mem_info_vram_total")
                valid = used is not None and total is not None and 0 <= used <= total and total > 0
                percent = used / total * 100 if used is not None and total is not None and valid else None
                readings.append(self._metric(identifier + ".vram", "gpu", f"{label} VRAM", percent,
                                             "%", str(device), status="ready" if valid else "unavailable",
                                             detail=f"{self._human(used)} / {self._human(total)}" if used is not None and total is not None and valid else "",
                                             reason="" if valid else "VRAM counters are unavailable"))
            elif vendor == "0x10de":
                readings.extend(self._nvidia(identifier, label, device))
            elif vendor == "0x8086":
                readings.extend(self._intel(identifier, label, card))
            else:
                readings.append(self._metric(identifier, "gpu", label, None, "%", str(device), status="unavailable",
                                             reason="GPU utilization is not exposed by this driver"))
        return readings or [self._metric("gpu.none", "gpu", "GPU", None, "%", "/sys/class/drm",
                                         status="unavailable", reason="No graphics adapter detected")]

    def _intel(self, identifier: str, label: str, card: Path) -> list[MetricReading]:
        act = self._number(card / "gt_act_freq_mhz")
        if act is None:
            act = self._number(card / "gt/gt0/rps_act_freq_mhz")
        if act is None:
            act = self._number(card / "gt_cur_freq_mhz")
        max_freq = self._number(card / "gt_max_freq_mhz")
        if max_freq is None:
            max_freq = self._number(card / "gt/gt0/rps_max_freq_mhz")
        if act is not None and max_freq is not None and max_freq > 0 and 0 <= act <= max_freq:
            pct = round(act / max_freq * 100.0, 1)
            detail = f"{int(act)} / {int(max_freq)} MHz"
            return [self._metric(identifier, "gpu", label, pct, "%", str(card),
                                 detail=detail, status="ready")]
        if act is not None:
            return [self._metric(identifier, "gpu", label, float(act), "MHz", str(card),
                                 detail=f"{int(act)} MHz", status="ready")]
        return [self._metric(identifier, "gpu", label, None, "%", str(card), status="unavailable",
                             reason="Intel GPU frequency counters are unavailable")]

    def _nvidia(self, identifier: str, label: str, device: Path) -> list[MetricReading]:
        executable = shutil.which("nvidia-smi")
        if not executable:
            return [self._metric(identifier, "gpu", label, None, "%", str(device), status="unavailable",
                                 reason="NVIDIA measurement tool is unavailable")]
        # Exact PCI identity prevents a query for one active card from waking
        # another suspended NVIDIA card. No query is issued without this ID.
        try:
            pci_id = device.resolve().name
        except OSError:
            pci_id = ""
        if not re.fullmatch(r"[0-9a-fA-F]{4}:[0-9a-fA-F]{2}:[0-9a-fA-F]{2}\.[0-7]", pci_id):
            return [self._metric(identifier, "gpu", label, None, "%", str(device), status="unavailable",
                                 reason="GPU PCI identity is unavailable")]
        try:
            result = subprocess.run([executable, "--id=" + pci_id,
                                     "--query-gpu=utilization.gpu,memory.used,memory.total", "--format=csv,noheader,nounits"],
                                    capture_output=True, text=True, timeout=2, check=False)
            if result.returncode != 0:
                raise ValueError("NVIDIA query failed")
            parts = result.stdout.strip().split(",")
            load, used, total = (float(value.strip()) for value in parts)
            if not all(math.isfinite(value) for value in (load, used, total)) or not 0 <= load <= 100 or not 0 <= used <= total or total <= 0:
                raise ValueError("NVIDIA returned invalid counters")
            return [self._metric(identifier, "gpu", label, load, "%", "nvidia-smi"),
                    self._metric(identifier + ".vram", "gpu", f"{label} VRAM", used / total * 100, "%", "nvidia-smi",
                                 detail=f"{used:.0f} / {total:.0f} MiB")]
        except (OSError, ValueError, subprocess.TimeoutExpired) as error:
            return [self._metric(identifier, "gpu", label, None, "%", "nvidia-smi",
                                 reason="NVIDIA query timed out" if isinstance(error, subprocess.TimeoutExpired) else "NVIDIA query failed or returned invalid data")]

    @staticmethod
    def _human(value: float) -> str:
        formatted = PerformanceCollector.bytes_to_human(value)
        for old, new in (("KB", "KiB"), ("MB", "MiB"), ("GB", "GiB"), ("TB", "TiB"), ("PB", "PiB")):
            formatted = formatted.replace(old, new)
        return formatted

    @staticmethod
    def _saved_timestamp(value: str) -> float | None:
        if not value:
            return None
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp()
        except (ValueError, OverflowError):
            return None

    def _maintenance(self) -> dict[str, dict[str, object]]:
        """Read saved observations only; never run an update or health scan."""
        result: dict[str, dict[str, object]] = {}
        try:
            snapshot = UpdateOverviewService().load()
            sources = tuple({"source": source.source, "status": source.status,
                             "count": len(source.items), "sampled_at": self._saved_timestamp(source.checked_at),
                             "stale": source.stale} for source in snapshot.sources)
            timestamps = [stamp for source in snapshot.sources if (stamp := self._saved_timestamp(source.checked_at)) is not None]
            result["updates"] = {"status": snapshot.storage_status,
                                 "detail": "; ".join(f"{source.source}: {source.status} ({len(source.items)})" for source in snapshot.sources),
                                 "sampled_at": max(timestamps) if timestamps else None, "sources": sources}
        except (OSError, ValueError):
            result["updates"] = {"status": "error", "detail": "Saved update observations are unreadable", "sampled_at": None}
        try:
            store = HealthTimelineStore()
            snapshots = store.load_read_only()
            if snapshots:
                latest = max(snapshots, key=lambda item: item.timestamp)
                check = latest.daily_maintenance.get("system_check", {})
                state = str(check.get("state", "recorded")) if isinstance(check, dict) else "recorded"
                findings = check.get("findings", []) if isinstance(check, dict) else []
                count = len(findings) if isinstance(findings, list) else 0
                detail = f"Saved check: {state}; {count} findings"
                if latest.collection_errors:
                    detail += f"; {len(latest.collection_errors)} sources unavailable"
                result["health"] = {"status": state, "detail": detail, "sampled_at": latest.timestamp,
                                    "findings": tuple(item for item in findings if isinstance(item, dict)) if isinstance(findings, list) else ()}
            else:
                result["health"] = {"status": "error" if store.last_error else "unchecked",
                                    "detail": "Saved health results are unreadable" if store.last_error else "No saved health check",
                                    "sampled_at": None}
        except (OSError, ValueError):
            result["health"] = {"status": "error", "detail": "Saved health results are unreadable", "sampled_at": None}
        try:
            runs = ActionRunStore().list_read_only(limit=100, strict=True)
            if runs:
                latest_run = max(runs, key=lambda run: run.updated_at)
                result["activity"] = {"status": latest_run.state, "detail": latest_run.action_id,
                                      "sampled_at": latest_run.completed_at or latest_run.updated_at,
                                      "verified": bool((latest_run.verification_result or {}).get("success", False)),
                                      "runs": tuple({"status": run.state, "action_id": run.action_id, "run_id": run.run_id,
                                                     "sampled_at": run.completed_at or run.updated_at}
                                                    for run in runs)}
            else:
                result["activity"] = {"status": "unchecked", "detail": "No saved changes", "sampled_at": None}
        except (OSError, ValueError):
            result["activity"] = {"status": "error", "detail": "Saved activity is unreadable", "sampled_at": None}
        return result

    def collect(self, *, fast: bool = True, slow: bool = True) -> DashboardSnapshot:
        if self._identity is None:
            self._identity = self._facts()
        fresh = []
        maintenance = self._latest.maintenance
        groups: set[str] = set()
        if fast:
            groups.update(self.FAST_GROUPS)
            fresh.extend(self._fast())
        if slow:
            groups.update(self.SLOW_GROUPS)
            fresh.extend(self._temperatures())
            fresh.extend(self._batteries())
            fresh.extend(self._gpus())
            fresh.extend(self._storage())
            maintenance = self._maintenance()
        previous = {metric.id: metric for metric in self._latest.metrics}
        merged = [metric for metric in self._latest.metrics if metric.group not in groups]
        for metric in fresh:
            prior = previous.pop(metric.id, None)
            if metric.status in {"error", "unavailable"} and prior is not None and prior.value is not None:
                metric = replace(prior, status="stale", reason=metric.reason)
            merged.append(metric)
        # A disappeared sensor must not silently erase the last observation.
        for prior in previous.values():
            if prior.group in groups and prior.value is not None:
                merged.append(replace(prior, status="stale", reason="Source is no longer available"))
        self._latest = DashboardSnapshot(tuple(merged), dict(self._identity), self._clock(), maintenance, self._cpu_per_core)
        return self._latest
