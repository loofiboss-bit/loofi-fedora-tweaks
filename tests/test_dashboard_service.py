"""Deterministic, rootless dashboard availability and counter regressions."""

import subprocess
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import mock_open, patch

from services.hardware.temperature import TemperatureManager
from services.system.dashboard import DashboardService, MetricReading
from utils.performance import PerformanceCollector


class TestDashboardService(unittest.TestCase):
    def setUp(self):
        self.service = DashboardService(clock=lambda: 100.0)
        self.service._identity = {"os": "Test Fedora"}

    @patch.object(PerformanceCollector, "_read_proc_stat", side_effect=[[[10, 0, 0, 90]], [[20, 0, 0, 100]]])
    @patch.object(PerformanceCollector, "_read_proc_meminfo", return_value={"MemTotal": 1000, "MemAvailable": 500})
    @patch.object(PerformanceCollector, "_read_proc_net_dev", return_value=(100, 200))
    @patch.object(PerformanceCollector, "_read_proc_diskstats", return_value=(200, 300))
    def test_initial_differentials_are_sampling(self, *_):
        first = self.service.collect(slow=False)
        self.assertEqual(next(m for m in first.metrics if m.group == "cpu").status, "sampling")
        self.assertIsNone(next(m for m in first.metrics if m.group == "network").value)
        second = self.service.collect(slow=False)
        self.assertEqual(next(m for m in second.metrics if m.group == "cpu").value, 50.0)
        self.assertEqual(next(m for m in second.metrics if m.group == "memory").value, 50.0)
        self.service.reset_baselines()
        self.assertFalse(self.service.collector.has_baseline("cpu"))
        self.assertFalse(self.service.collector.has_baseline("network"))

    @patch.object(DashboardService, "_fast")
    def test_failure_preserves_last_good_value_as_stale(self, fast):
        fast.side_effect = [[MetricReading("cpu.usage", "cpu", "CPU", 23.0, "%", "ready", "/proc/stat", 90.0)],
                            [MetricReading("cpu.usage", "cpu", "CPU", None, "%", "error", "/proc/stat", None, "Read failed")]]
        self.service.collect(slow=False)
        metric = self.service.collect(slow=False).metrics[0]
        self.assertEqual((metric.value, metric.status, metric.sampled_at), (23.0, "stale", 90.0))
        self.assertEqual(metric.reason, "Read failed")

    @patch.object(DashboardService, "_fast", return_value=[])
    def test_fast_refresh_preserves_slow_sources(self, _):
        self.service._latest = self.service.latest_snapshot.__class__((MetricReading("temp", "temperature", "CPU", 42, "°C", "ready", "hwmon", 90),), {}, 90)
        self.assertEqual(self.service.collect(slow=False).metrics[0].value, 42)

    @patch.object(TemperatureManager, "get_all_sensors", return_value=[])
    @patch.object(DashboardService, "_paths", return_value=[])
    def test_missing_temperature_is_unavailable(self, *_):
        metric = self.service._temperatures()[0]
        self.assertEqual(metric.status, "unavailable")
        self.assertIsNone(metric.value)

    @patch.object(TemperatureManager, "get_all_sensors", return_value=[])
    @patch.object(DashboardService, "_paths", return_value=[Path("/sys/class/hwmon/hwmon0/temp1_input")])
    def test_failed_temperature_is_error(self, *_):
        self.assertEqual(self.service._temperatures()[0].status, "error")

    @patch.object(DashboardService, "_paths", return_value=[Path("/sys/class/power_supply/BAT0"), Path("/sys/class/power_supply/BAT1")])
    @patch.object(DashboardService, "_read")
    def test_multiple_batteries_and_health(self, read, _):
        data = {"type": "Battery", "capacity": "70", "status": "Discharging", "energy_full": "4000", "energy_full_design": "5000"}
        read.side_effect = lambda path: data.get(path.name)
        metrics = self.service._batteries()
        self.assertEqual(len(metrics), 4)
        self.assertEqual([m.value for m in metrics], [70, 80, 70, 80])
        self.assertNotEqual(metrics[0].id, metrics[2].id)

    @patch.object(DashboardService, "_paths", return_value=[Path("/sys/class/power_supply/BAT0")])
    @patch.object(DashboardService, "_read")
    def test_battery_charge_ratio_when_capacity_is_not_exposed(self, read, _):
        values = {"type": "Battery", "charge_now": "3000", "charge_full": "4000", "charge_full_design": "5000"}
        read.side_effect = lambda path: values.get(path.name)
        self.assertEqual([item.value for item in self.service._batteries()], [75, 80])

    @patch.object(DashboardService, "_paths", return_value=[])
    def test_no_battery_is_explicit(self, _):
        self.assertEqual(self.service._batteries()[0].reason, "No battery detected")

    @patch.object(DashboardService, "_paths", return_value=[Path("/sys/class/power_supply/BAT0")])
    @patch.object(DashboardService, "_read")
    def test_corrupt_battery_capacity_is_error(self, read, _):
        read.side_effect = lambda path: {"type": "Battery", "capacity": "nan"}.get(path.name)
        self.assertEqual(self.service._batteries()[0].status, "error")

    @patch.object(DashboardService, "_paths", return_value=[Path("/sys/class/drm/card0"), Path("/sys/class/drm/card1")])
    @patch.object(DashboardService, "_read")
    @patch("services.system.dashboard.subprocess.run")
    def test_suspended_and_unknown_gpus_are_not_queried(self, run, read, _):
        read.side_effect = lambda path: "0x10de" if path.name == "vendor" else "suspended" if "card0" in str(path) else None
        metrics = self.service._gpus()
        self.assertEqual(len(metrics), 2)
        self.assertTrue(all(m.status == "unavailable" for m in metrics))
        run.assert_not_called()

    @patch.object(DashboardService, "_paths", return_value=[Path("/sys/class/drm/card0")])
    @patch.object(DashboardService, "_read")
    def test_amd_load_and_vram(self, read, _):
        values = {"vendor": "0x1002", "runtime_status": "active", "gpu_busy_percent": "50", "mem_info_vram_used": "200", "mem_info_vram_total": "1000"}
        read.side_effect = lambda path: values.get(path.name)
        self.assertEqual([metric.value for metric in self.service._gpus()], [50, 20])

    @patch.object(DashboardService, "_paths", return_value=[Path("/sys/class/drm/card0")])
    @patch.object(DashboardService, "_read")
    def test_intel_freq_and_ratio(self, read, _):
        values = {"vendor": "0x8086", "runtime_status": "active", "gt_act_freq_mhz": "650", "gt_max_freq_mhz": "1300"}
        read.side_effect = lambda path: values.get(path.name)
        metrics = self.service._gpus()
        self.assertEqual(len(metrics), 1)
        self.assertEqual(metrics[0].value, 50.0)
        self.assertEqual(metrics[0].status, "ready")
        self.assertEqual(metrics[0].detail, "650 / 1300 MHz")

    @patch("services.system.dashboard.shutil.which", return_value="/usr/bin/nvidia-smi")
    @patch("services.system.dashboard.subprocess.run", side_effect=subprocess.TimeoutExpired("nvidia-smi", 2))
    @patch.object(Path, "resolve", return_value=Path("/sys/devices/0000:01:00.0"))
    def test_nvidia_timeout_is_error_and_bounded(self, _, run, which):
        metric = self.service._nvidia("gpu:card0", "NVIDIA card0", Path("/sys/class/drm/card0/device"))[0]
        self.assertEqual(metric.status, "error")
        self.assertIn("timed out", metric.reason)
        self.assertEqual(run.call_args.kwargs["timeout"], 2)
        self.assertIn("--id=0000:01:00.0", run.call_args.args[0])

    @patch("services.system.dashboard.shutil.which", return_value="/usr/bin/nvidia-smi")
    @patch("services.system.dashboard.subprocess.run", return_value=SimpleNamespace(returncode=0, stdout="30, 200, 1000"))
    @patch.object(Path, "resolve", return_value=Path("/sys/devices/0000:01:00.0"))
    def test_nvidia_measurement(self, *_):
        metrics = self.service._nvidia("gpu:card0", "NVIDIA card0", Path("/sys/class/drm/card0/device"))
        self.assertEqual([m.value for m in metrics], [30, 20])

    @patch("services.system.dashboard.os.statvfs", return_value=SimpleNamespace(f_fsid=1, f_blocks=1000, f_frsize=4096, f_bavail=200, f_bfree=250))
    @patch.object(Path, "home", return_value=Path("/home/test"))
    def test_storage_deduplicates_same_filesystem(self, *_):
        metrics = self.service._storage()
        self.assertEqual(len(metrics), 1)
        self.assertEqual(metrics[0].value, 75)

    @patch("services.system.dashboard.os.statvfs", side_effect=PermissionError("Unreadable filesystem"))
    @patch.object(Path, "home", return_value=Path("/home/test"))
    def test_storage_permission_error(self, *_):
        self.assertTrue(all(m.status == "error" for m in self.service._storage()))

    @patch.object(DashboardService, "_read", return_value="invalid")
    def test_number_reader_reports_invalid_data(self, _):
        self.assertIsNone(self.service._number(Path("/test")))

    @patch.object(DashboardService, "_maintenance", return_value={})
    @patch.object(DashboardService, "_temperatures", return_value=[])
    @patch.object(DashboardService, "_batteries", return_value=[])
    @patch.object(DashboardService, "_gpus", return_value=[])
    @patch.object(DashboardService, "_storage", return_value=[])
    def test_disappeared_sensor_retains_stale_observation(self, *_):
        old = MetricReading("temp", "temperature", "CPU", 42, "°C", "ready", "hwmon", 90)
        self.service._latest = self.service.latest_snapshot.__class__((old,), {}, 90)
        metric = self.service.collect(fast=False).metrics[0]
        self.assertEqual((metric.value, metric.status, metric.sampled_at), (42, "stale", 90))

    @patch.object(DashboardService, "_read")
    @patch("services.system.dashboard.SystemManager.get_platform_profile")
    @patch("services.system.dashboard.platform.node", return_value="test-host")
    @patch("services.system.dashboard.platform.release", return_value="test-kernel")
    def test_identity_uses_platform_profile(self, kernel, node, profile, read):
        profile.return_value = SimpleNamespace(desktop=SimpleNamespace(value="kde"), deployment_backend=SimpleNamespace(value="rpm_ostree"))
        read.side_effect = lambda path: 'model name : Test CPU' if path.name == "cpuinfo" else 'PRETTY_NAME="Fedora Test"'
        self.service._identity = None
        identity = self.service.collect(fast=False, slow=False).identity
        self.assertEqual(identity["os"], "Fedora Test")
        self.assertEqual(identity["cpu"], "Test CPU")
        self.assertEqual(identity["desktop"], "kde")
        self.assertEqual(identity["deployment"], "rpm_ostree")
        self.service.collect(fast=False, slow=False)
        profile.assert_called_once()

    @patch.object(Path, "open", side_effect=PermissionError)
    def test_file_permissions_return_unknown(self, _):
        self.assertIsNone(DashboardService._read(Path("/test")))

    @patch.object(Path, "open", mock_open(read_data="42"))
    def test_file_read(self):
        self.assertEqual(DashboardService._read(Path("/test")), "42")

    @patch("glob.glob", return_value=["/sys/class/drm/card0"])
    def test_paths_are_sorted(self, _):
        self.assertEqual(DashboardService._paths("/sys/class/drm/card*"), [Path("/sys/class/drm/card0")])

    @patch.object(DashboardService, "_paths", return_value=[Path("/sys/class/drm/card0"), Path("/sys/class/drm/card0-DP-1")])
    @patch.object(DashboardService, "_read")
    def test_intel_has_explicit_unavailable_load(self, read, _):
        read.side_effect = lambda path: "0x8086" if path.name == "vendor" else "active"
        metrics = self.service._gpus()
        self.assertEqual(len(metrics), 1)
        self.assertEqual(metrics[0].label, "Intel card0")
        self.assertEqual(metrics[0].status, "unavailable")

    @patch.object(DashboardService, "_paths", return_value=[])
    def test_no_gpu_is_unavailable(self, _):
        self.assertEqual(self.service._gpus()[0].reason, "No graphics adapter detected")

    @patch("services.system.dashboard.shutil.which", return_value=None)
    def test_missing_nvidia_tool(self, _):
        self.assertEqual(self.service._nvidia("gpu0", "GPU", Path("/device"))[0].status, "unavailable")

    @patch.object(TemperatureManager, "get_all_sensors")
    def test_temperature_zero_is_a_valid_reading(self, sensors):
        sensors.return_value = [SimpleNamespace(source="/hwmon/temp1_input", name="coretemp", label="Package", current=0.0, high=85.0, critical=100.0)]
        metric = self.service._temperatures()[0]
        self.assertEqual((metric.value, metric.status, metric.high, metric.critical), (0.0, "ready", 85.0, 100.0))

    @patch("services.system.dashboard.UpdateOverviewService")
    @patch("services.system.dashboard.HealthTimelineStore")
    @patch("services.system.dashboard.ActionRunStore")
    @patch("services.system.dashboard.subprocess.run")
    def test_maintenance_reads_only_saved_observations(self, run, actions, health, updates):
        updates.return_value.load.return_value = SimpleNamespace(storage_status="ok", sources=(SimpleNamespace(source="system", status="available", items=("pkg",), checked_at="2026-10-06T12:00:00+00:00", stale=False),))
        health.return_value.load_read_only.return_value = [SimpleNamespace(timestamp=100, daily_maintenance={"system_check": {"state": "partial", "findings": [{"id": "disk"}]}}, collection_errors=["unreadable"])]
        actions.return_value.list_read_only.return_value = [SimpleNamespace(updated_at=101, completed_at=101, action_id="set-tweak", state="failed", verification_result={"success": False})]
        result = self.service._maintenance()
        self.assertEqual(result["updates"]["sources"][0]["count"], 1)
        self.assertEqual(result["health"]["status"], "partial")
        self.assertEqual(result["health"]["findings"], ({"id": "disk"},))
        self.assertIn("1 sources unavailable", result["health"]["detail"])
        self.assertEqual(result["activity"]["status"], "failed")
        self.assertFalse(result["activity"]["verified"])
        self.assertEqual(result["activity"]["runs"][0]["action_id"], "set-tweak")
        updates.return_value.load.assert_called_once_with()
        updates.return_value.check.assert_not_called()
        health.return_value.load_read_only.assert_called_once_with()
        health.return_value.collect_and_append.assert_not_called()
        actions.return_value.list_read_only.assert_called_once_with(limit=100, strict=True)
        actions.return_value.save.assert_not_called()
        run.assert_not_called()

    @patch("services.system.dashboard.UpdateOverviewService")
    @patch("services.system.dashboard.HealthTimelineStore")
    @patch("services.system.dashboard.ActionRunStore")
    def test_empty_saved_maintenance_does_not_claim_success(self, actions, health, updates):
        updates.return_value.load.return_value = SimpleNamespace(storage_status="ok", sources=())
        health.return_value.load_read_only.return_value = []
        health.return_value.last_error = ""
        actions.return_value.list_read_only.return_value = []
        result = self.service._maintenance()
        self.assertEqual(result["health"]["status"], "unchecked")
        self.assertIsNone(result["updates"]["sampled_at"])
        self.assertEqual(result["activity"]["status"], "unchecked")

    @patch("services.system.dashboard.UpdateOverviewService")
    @patch("services.system.dashboard.HealthTimelineStore")
    @patch("services.system.dashboard.ActionRunStore")
    def test_saved_maintenance_errors_are_explicit(self, actions, health, updates):
        updates.return_value.load.side_effect = ValueError("corrupt")
        health.return_value.load_read_only.side_effect = OSError("permission")
        actions.return_value.list_read_only.side_effect = ValueError("future schema")
        self.assertTrue(all(item["status"] == "error" for item in self.service._maintenance().values()))

    @patch.object(PerformanceCollector, "_read_proc_stat", return_value=[[10, 0, 0, 90]])
    @patch.object(PerformanceCollector, "_read_proc_meminfo", return_value={"MemTotal": 1000, "MemAvailable": 500})
    @patch.object(PerformanceCollector, "_read_proc_net_dev", side_effect=[(100, 100), (120, 160), (5, 170), (25, 190), None])
    @patch.object(PerformanceCollector, "_read_proc_diskstats", side_effect=[(100, 100), (140, 180), (150, 5), (170, 45), None])
    @patch("utils.performance.time.monotonic", side_effect=[0] * 4 + [2] * 4 + [4] * 4 + [6] * 4 + [8] * 4)
    def test_counter_drop_is_sampling_then_uses_new_baseline(self, *_):
        self.service.collect(slow=False)
        ready = {metric.id: metric for metric in self.service.collect(slow=False).metrics}
        self.assertEqual(ready["network.send"].value, 30.0)
        self.assertEqual(ready["disk.write"].value, 40.0)
        reset = {metric.id: metric for metric in self.service.collect(slow=False).metrics}
        for name in ("network.send", "network.receive", "disk.read", "disk.write"):
            self.assertEqual(reset[name].status, "sampling")
            self.assertIsNone(reset[name].value)
        self.assertEqual(len(self.service.collector.get_network_history()), 2)
        self.assertEqual(len(self.service.collector.get_disk_io_history()), 2)
        resumed = {metric.id: metric for metric in self.service.collect(slow=False).metrics}
        self.assertEqual(resumed["network.send"].value, 10.0)
        self.assertEqual(resumed["network.receive"].value, 10.0)
        self.assertEqual(resumed["disk.read"].value, 10.0)
        self.assertEqual(resumed["disk.write"].value, 20.0)
        self.assertEqual(resumed["disk.write"].status, "ready")
        failed = {metric.id: metric for metric in self.service.collect(slow=False).metrics}
        self.assertEqual(failed["network.send"].status, "stale")
        self.assertEqual(failed["disk.write"].status, "stale")
        self.assertEqual(failed["disk.write"].value, 20.0)

    @patch.object(PerformanceCollector, "_read_proc_stat", side_effect=[[[100, 0, 0, 100]], [[110, 0, 0, 110]], [[5, 0, 0, 5]], [[15, 0, 0, 15]]])
    @patch.object(PerformanceCollector, "_read_proc_meminfo", return_value={"MemTotal": 1000, "MemAvailable": 500})
    @patch.object(PerformanceCollector, "_read_proc_net_dev", return_value=(100, 100))
    @patch.object(PerformanceCollector, "_read_proc_diskstats", return_value=(100, 100))
    def test_cpu_counter_drop_reestablishes_baseline(self, *_):
        self.service.collect(slow=False)
        self.service.collect(slow=False)
        reset = next(metric for metric in self.service.collect(slow=False).metrics if metric.group == "cpu")
        self.assertEqual(reset.status, "sampling")
        self.assertIsNone(reset.value)
        self.assertEqual(self.service.latest_snapshot.cpu_per_core, ())
        resumed = next(metric for metric in self.service.collect(slow=False).metrics if metric.group == "cpu")
        self.assertEqual((resumed.status, resumed.value), ("ready", 50.0))

    @patch("services.system.dashboard.UpdateOverviewService")
    @patch("services.system.dashboard.HealthTimelineStore")
    @patch("services.system.dashboard.ActionRunStore")
    def test_maintenance_accepts_real_store_models(self, actions, health, updates):
        from core.actions.contracts import ActionRun
        from core.observability.snapshot import HealthSnapshot
        from services.software.update_overview import UpdateOverviewSnapshot, UpdateSourceResult

        updates.return_value.load.return_value = UpdateOverviewSnapshot(sources=(UpdateSourceResult("system", "up_to_date", "2026-10-07T12:00:00+00:00"),))
        health.return_value.load_read_only.return_value = [HealthSnapshot(timestamp=100, app_version="test", app_codename="test", fedora_target="test", atomic=False, daily_maintenance={"system_check": {"state": "completed", "findings": []}}, action_center_summary={})]
        actions.return_value.list_read_only.return_value = [ActionRun(run_id="run", plan_id="plan", action_id="set-tweak", correlation_id="correlation", state="succeeded", updated_at=101, completed_at=101, verification_result={"success": True})]
        result = self.service._maintenance()
        self.assertEqual(result["health"]["status"], "completed")
        self.assertEqual(result["activity"]["status"], "succeeded")
        self.assertTrue(result["activity"]["verified"])


class TestCollectorErrorSemantics(unittest.TestCase):
    @patch.object(PerformanceCollector, "_read_proc_net_dev", side_effect=[(100, 100), None, (200, 200)])
    def test_failed_network_read_resets_baseline(self, _):
        collector = PerformanceCollector()
        collector.collect_network()
        self.assertIsNone(collector.collect_network())
        self.assertFalse(collector.has_baseline("network"))
        collector.collect_network()
        self.assertEqual(len(collector.get_network_history()), 2)

    @patch.object(PerformanceCollector, "_read_proc_meminfo", return_value={"MemTotal": 1000})
    def test_missing_memory_available_is_not_100_percent(self, _):
        self.assertIsNone(PerformanceCollector().collect_memory())

    @patch.object(PerformanceCollector, "_read_proc_stat", return_value=[[1, 0, 0, 1]])
    def test_history_is_bounded(self, _):
        collector = PerformanceCollector()
        for _ in range(100):
            collector.collect_cpu()
        self.assertEqual(len(collector.get_cpu_history()), 60)
