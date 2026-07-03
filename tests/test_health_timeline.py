"""Tests for v12 health timeline storage and legacy metric timeline."""

import csv
import json
import os
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, mock_open, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "loofi-fedora-tweaks"))

from core.diagnostics.health_timeline import HealthTimeline
from core.observability import HealthSnapshot, HealthTimelineStore


def _snapshot(timestamp):
    return HealthSnapshot(
        timestamp=timestamp,
        app_version="12.0.0",
        app_codename="Lighthouse",
        fedora_target="44",
        atomic=False,
        daily_maintenance={"cards": []},
        action_center_summary={},
    )


class TestHealthTimelineStore(unittest.TestCase):
    """Timeline retention and corrupt file handling are deterministic."""

    def test_retention_limits_saved_snapshots(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            store = HealthTimelineStore(Path(tmpdir) / "timeline.json", retention=2)
            store.append(_snapshot(1.0))
            store.append(_snapshot(2.0))
            store.append(_snapshot(3.0))

            self.assertEqual([item.timestamp for item in store.load()], [2.0, 3.0])

    def test_corrupt_history_returns_empty_without_crashing(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "timeline.json"
            path.write_text("{not-json", encoding="utf-8")
            store = HealthTimelineStore(path)

            self.assertEqual(store.load(), [])
            self.assertIn("corrupt-history", store.last_error)


class TestLegacyHealthTimeline(unittest.TestCase):
    """SQLite health metric timeline remains covered for release gates."""

    def setUp(self):
        self.timeline = HealthTimeline(db_path=":memory:")

    def test_record_query_summary_and_prune(self):
        self.assertTrue(self.timeline.record_metric("cpu_temp", 50.0, "C").success)
        self.assertTrue(self.timeline.record_metric("cpu_temp", 70.0, "C", {"sensor": "core0"}).success)
        self.assertTrue(self.timeline.record_metric("ram_usage", 60.0, "%").success)
        self.assertFalse(self.timeline.record_metric("", 1.0).success)

        metrics = self.timeline.get_metrics("cpu_temp", hours=1)
        self.assertEqual([metric["value"] for metric in metrics], [50.0, 70.0])
        self.assertEqual(metrics[1]["metadata"], {"sensor": "core0"})

        summary = self.timeline.get_summary(hours=1)
        self.assertEqual(summary["cpu_temp"]["min"], 50.0)
        self.assertEqual(summary["cpu_temp"]["max"], 70.0)
        self.assertEqual(summary["cpu_temp"]["avg"], 60.0)
        self.assertEqual(summary["cpu_temp"]["count"], 2)
        self.assertIn("ram_usage", summary)

        result = self.timeline.prune_old_data(days=1)
        self.assertTrue(result.success)
        self.assertEqual(result.data["deleted"], 0)

    def test_file_database_initialization_and_prune_old_rows(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "nested", "health.db")
            timeline = HealthTimeline(db_path=db_path)
            self.assertTrue(os.path.isdir(os.path.dirname(db_path)))

            conn = sqlite3.connect(db_path)
            try:
                columns = {row[1] for row in conn.execute("PRAGMA table_info(metrics)")}
                self.assertEqual(columns, {"id", "timestamp", "metric_type", "value", "unit", "metadata"})
                conn.execute(
                    "INSERT INTO metrics (timestamp, metric_type, value, unit) VALUES (?, ?, ?, ?)",
                    ("2020-01-01T00:00:00", "cpu_temp", 45.0, "C"),
                )
                conn.commit()
            finally:
                conn.close()

            timeline.record_metric("cpu_temp", 65.0, "C")
            result = timeline.prune_old_data(days=1)
            self.assertTrue(result.success)
            self.assertEqual(result.data["deleted"], 1)

    def test_exports_json_csv_and_rejects_bad_format_or_path(self):
        self.timeline.record_metric("cpu_temp", 55.0, "C")
        self.timeline.record_metric("ram_usage", 50.0, "%")

        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as json_file:
            json_path = json_file.name
        with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as csv_file:
            csv_path = csv_file.name

        try:
            json_result = self.timeline.export_metrics(json_path, format="json")
            self.assertTrue(json_result.success)
            self.assertEqual(json_result.data["count"], 2)
            with open(json_path, encoding="utf-8") as handle:
                self.assertEqual(len(json.load(handle)), 2)

            csv_result = self.timeline.export_metrics(csv_path, format="csv")
            self.assertTrue(csv_result.success)
            with open(csv_path, encoding="utf-8") as handle:
                rows = list(csv.reader(handle))
            self.assertEqual(len(rows), 3)

            self.assertFalse(self.timeline.export_metrics("/tmp/out.xml", format="xml").success)
            self.assertFalse(self.timeline.export_metrics("/nonexistent/dir/out.json", format="json").success)
        finally:
            os.unlink(json_path)
            os.unlink(csv_path)

    def test_export_empty_csv_writes_header(self):
        with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as csv_file:
            csv_path = csv_file.name

        try:
            result = self.timeline.export_metrics(csv_path, format="csv")
            self.assertTrue(result.success)
            with open(csv_path, encoding="utf-8") as handle:
                rows = list(csv.reader(handle))
            self.assertEqual(rows, [["id", "timestamp", "metric_type", "value", "unit", "metadata"]])
        finally:
            os.unlink(csv_path)

    def test_detect_anomalies_paths(self):
        self.assertEqual(self.timeline.detect_anomalies("cpu_temp", hours=1), [])

        for value in [50.0, 50.5, 51.0, 49.5, 50.0, 51.5, 49.0, 50.0, 100.0]:
            self.timeline.record_metric("cpu_temp", value, "C")

        anomalies = self.timeline.detect_anomalies("cpu_temp", hours=1)
        self.assertEqual(anomalies[0]["value"], 100.0)
        self.assertIn("deviation", anomalies[0])

        flat = HealthTimeline(db_path=":memory:")
        for _ in range(5):
            flat.record_metric("load_avg", 1.0)
        self.assertEqual(flat.detect_anomalies("load_avg", hours=1), [])

    @patch.object(HealthTimeline, "_get_load_average", return_value=1.5)
    @patch.object(HealthTimeline, "_get_disk_usage", return_value=45.0)
    @patch.object(HealthTimeline, "_get_ram_usage", return_value=60.0)
    @patch.object(HealthTimeline, "_get_cpu_temp", return_value=55.0)
    def test_record_snapshot_success(self, mock_temp, mock_ram, mock_disk, mock_load):
        result = self.timeline.record_snapshot()
        self.assertTrue(result.success)
        self.assertEqual(len(result.data["recorded"]), 4)
        self.assertEqual(self.timeline.get_summary(hours=1)["cpu_temp"]["count"], 1)

    @patch.object(HealthTimeline, "_get_load_average", side_effect=RuntimeError("load"))
    @patch.object(HealthTimeline, "_get_disk_usage", side_effect=RuntimeError("disk"))
    @patch.object(HealthTimeline, "_get_ram_usage", return_value=60.0)
    @patch.object(HealthTimeline, "_get_cpu_temp", side_effect=RuntimeError("temp"))
    def test_record_snapshot_partial_success(self, mock_temp, mock_ram, mock_disk, mock_load):
        result = self.timeline.record_snapshot()
        self.assertTrue(result.success)
        self.assertEqual(result.data["recorded"], ["ram=60.0%"])
        self.assertEqual(len(result.data["errors"]), 3)

    @patch.object(HealthTimeline, "_get_load_average", side_effect=RuntimeError("load"))
    @patch.object(HealthTimeline, "_get_disk_usage", side_effect=RuntimeError("disk"))
    @patch.object(HealthTimeline, "_get_ram_usage", side_effect=RuntimeError("ram"))
    @patch.object(HealthTimeline, "_get_cpu_temp", side_effect=RuntimeError("temp"))
    def test_record_snapshot_all_fail(self, mock_temp, mock_ram, mock_disk, mock_load):
        result = self.timeline.record_snapshot()
        self.assertFalse(result.success)
        self.assertIn("Snapshot failed", result.message)


class TestLegacyHealthTimelineReaders(unittest.TestCase):
    """System metric readers are mocked and deterministic."""

    @patch("os.listdir", return_value=["thermal_zone0", "cooling_device0"])
    @patch("os.path.isdir", return_value=True)
    @patch("os.path.isfile", return_value=True)
    @patch("builtins.open", mock_open(read_data="65000\n"))
    def test_cpu_temp_reads_thermal_zone(self, mock_isfile, mock_isdir, mock_listdir):
        self.assertEqual(HealthTimeline._get_cpu_temp(), 65.0)

    @patch("os.path.isdir", return_value=False)
    @patch("core.diagnostics.health_timeline.cached_which", return_value="/usr/bin/sensors")
    @patch("core.diagnostics.health_timeline.subprocess.run")
    def test_cpu_temp_falls_back_to_sensors(self, mock_run, mock_which, mock_isdir):
        mock_run.return_value.returncode = 0
        mock_run.return_value.stdout = "Tctl:         +61.2 C\n"
        self.assertEqual(HealthTimeline._get_cpu_temp(), 61.2)

    @patch("os.path.isdir", return_value=False)
    @patch("core.diagnostics.health_timeline.cached_which", return_value=None)
    def test_cpu_temp_no_source_raises(self, mock_which, mock_isdir):
        with self.assertRaises(RuntimeError):
            HealthTimeline._get_cpu_temp()

    @patch(
        "builtins.open",
        mock_open(read_data="MemTotal: 16000000 kB\nMemAvailable: 8000000 kB\nBadLine: nope kB\n"),
    )
    def test_ram_usage_calculation(self):
        self.assertEqual(HealthTimeline._get_ram_usage(), 50.0)

    @patch("builtins.open", mock_open(read_data="MemAvailable: 8000000 kB\n"))
    def test_ram_usage_invalid_total(self):
        with self.assertRaises(RuntimeError):
            HealthTimeline._get_ram_usage()

    @patch("builtins.open", side_effect=OSError("permission denied"))
    def test_ram_usage_read_error(self, mock_file):
        with self.assertRaises(RuntimeError):
            HealthTimeline._get_ram_usage()

    @patch("os.statvfs")
    def test_disk_usage_calculation(self, mock_statvfs):
        statvfs_result = MagicMock()
        statvfs_result.f_blocks = 1000
        statvfs_result.f_bfree = 400
        statvfs_result.f_frsize = 4096
        mock_statvfs.return_value = statvfs_result
        self.assertEqual(HealthTimeline._get_disk_usage(), 60.0)

    @patch("os.statvfs", side_effect=OSError("fail"))
    def test_disk_usage_oserror(self, mock_statvfs):
        self.assertEqual(HealthTimeline._get_disk_usage(), 0.0)

    @patch("os.getloadavg", return_value=(2.5, 1.5, 0.8))
    def test_load_average_reads_one_minute(self, mock_load):
        self.assertEqual(HealthTimeline._get_load_average(), 2.5)

    @patch("os.getloadavg", side_effect=OSError("not available"))
    def test_load_average_oserror(self, mock_load):
        self.assertEqual(HealthTimeline._get_load_average(), 0.0)


if __name__ == "__main__":
    unittest.main()
