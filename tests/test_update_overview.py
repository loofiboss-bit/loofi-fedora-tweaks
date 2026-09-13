"""Deterministic discovery and persistence tests; no host queries."""

import json
import subprocess
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import Mock, patch

from core.executor.action_result import ActionResult
from services.software.update_overview import OverviewCancelled, OverviewRuntime, UpdateOverviewService


class TestUpdateOverview(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name) / "overview.json"
        self.now = datetime(2026, 1, 1, tzinfo=timezone.utc)
        self.runtime = Mock()
        self.runtime.is_atomic.return_value = False
        self.runtime.package_manager.return_value = "dnf5"
        self.which = Mock(return_value="/usr/bin/tool")
        self.service = UpdateOverviewService(self.runtime, self.path, lambda: self.now, self.which)
        self.responses = {
            "system": ActionResult(True, "", 0),
            "flatpak": ActionResult(True, "", 0),
            "firmware": ActionResult(True, "", 0, stdout='{"Devices": []}'),
        }
        self.runtime.execute_read_only.side_effect = lambda vector, action_id, timeout: self.responses[action_id.removeprefix("update-overview-")]

    def test_cancel_before_check_never_probes_or_writes(self):
        self.service.cancel()
        with self.assertRaises(OverviewCancelled):
            self.service.check()
        self.assertEqual(self.runtime.method_calls, [])
        self.assertFalse(self.path.exists())

    def test_cancel_during_query_stops_next_source_and_preserves_cache(self):
        self.service.check()
        original = self.path.read_bytes()
        self.runtime.execute_read_only.reset_mock()

        def cancel_query(*args, **kwargs):
            self.service.cancel()
            return self.responses["system"]

        self.runtime.execute_read_only.side_effect = cancel_query
        with self.assertRaises(OverviewCancelled):
            self.service.check()
        self.assertEqual(self.runtime.execute_read_only.call_count, 1)
        self.assertEqual(self.path.read_bytes(), original)

    @patch("services.software.update_overview.MAX_BYTES", 1100)
    def test_total_snapshot_size_limit_preserves_cache(self):
        self.service.check()
        original = self.path.read_bytes()
        self.responses["system"] = ActionResult(False, "", 100, stdout="a.x86_64 " + "1" * 400 + " updates")
        self.assertEqual(self.service.check().storage_status, "unavailable")
        self.assertEqual(self.path.read_bytes(), original)

    def test_constructor_and_load_never_probe_or_write(self):
        snapshot = self.service.load()
        self.assertEqual([source.status for source in snapshot.sources], ["unchecked"] * 3)
        self.assertTrue(all(source.stale for source in snapshot.sources))
        self.runtime.assert_not_called()
        self.assertEqual(self.runtime.method_calls, [])
        self.which.assert_not_called()
        self.assertFalse(self.path.exists())

    def test_traditional_candidates_and_persisted_reload(self):
        self.responses["system"] = ActionResult(False, "", 100, stdout="kernel.x86_64 6.9-1.fc44 updates\n")
        self.responses["flatpak"] = ActionResult(True, "", 0, stdout="app/org.test.App/x86_64/stable\t" + "a" * 64)
        self.responses["firmware"] = ActionResult(True, "", 0, stdout=json.dumps({"Devices": [{"Name": "BIOS", "Version": "1", "Releases": [{"Version": "2"}]}]}))
        snapshot = self.service.check()
        self.assertEqual([source.status for source in snapshot.sources], ["available"] * 3)
        self.assertEqual(snapshot.sources[2].items[0].old_version, "1")
        self.assertEqual(snapshot, self.service.load())
        self.assertEqual(self.path.stat().st_mode & 0o777, 0o600)
        self.assertIn("dnf5", self.runtime.execute_read_only.call_args_list[0].args[0])

    def test_stale_independent_of_available_status(self):
        self.responses["system"] = ActionResult(False, "", 100, stdout="a.x86_64 1 updates")
        self.service.check()
        self.now += timedelta(days=2)
        source = self.service.load().sources[0]
        self.assertEqual(source.status, "available")
        self.assertTrue(source.stale)

    def test_atomic_candidates_require_preview_evidence(self):
        self.runtime.is_atomic.return_value = True
        self.responses["system"] = ActionResult(True, "", 0, stdout="Checking for updates\nUpgraded:\n foo 1 -> 2\nAdded bar 3")
        snapshot = self.service.check()
        self.assertEqual(snapshot.system_mode, "atomic")
        self.assertEqual(snapshot.sources[0].status, "available")
        self.assertTrue(snapshot.sources[0].reboot_required)
        self.assertEqual(snapshot.sources[0].items[0].old_version, "1")
        self.assertEqual(self.runtime.execute_read_only.call_args_list[0].args[0], ["rpm-ostree", "upgrade", "--preview"])

    def test_atomic_empty_output_is_not_success(self):
        self.runtime.is_atomic.return_value = True
        self.assertEqual(self.service.check().sources[0].error_code, "invalid_output")
        self.responses["system"].stdout = "No upgrade available."
        self.assertEqual(self.service.check().sources[0].status, "up_to_date")

    def test_failure_does_not_hide_other_sources(self):
        self.responses["system"] = ActionResult(False, "offline", 1)
        self.assertEqual([source.status for source in self.service.check().sources], ["error", "up_to_date", "up_to_date"])

    def test_missing_tools_are_distinct(self):
        self.which.side_effect = lambda tool: None if tool == "flatpak" else tool
        snapshot = self.service.check()
        self.assertEqual(snapshot.sources[1].status, "missing_tool")
        self.assertEqual(self.runtime.execute_read_only.call_count, 2)

    def test_unsupported_manager_does_not_run_system_query(self):
        self.runtime.package_manager.return_value = "apt"
        self.assertEqual(self.service.check().sources[0].status, "unsupported")
        self.assertEqual(self.runtime.execute_read_only.call_count, 2)

    def test_timeout_isolated(self):
        def execute(vector, action_id, timeout):
            if vector[0] == "dnf5":
                raise subprocess.TimeoutExpired(vector, timeout)
            return self.responses[action_id.removeprefix("update-overview-")]
        self.runtime.execute_read_only.side_effect = execute
        snapshot = self.service.check()
        self.assertEqual(snapshot.sources[0].error_code, "timeout")
        self.assertEqual(snapshot.sources[2].status, "up_to_date")

    def test_malformed_output_never_means_no_updates(self):
        for source, output in (("system", "unexpected output"), ("flatpak", "malformed"), ("firmware", "{}")):
            with self.subTest(source=source):
                self.responses[source].stdout = output
                found = next(item for item in self.service.check().sources if item.source == source)
                self.assertEqual(found.error_code, "invalid_output")

    def test_dnf_available_code_without_candidates_is_error(self):
        self.responses["system"] = ActionResult(False, "", 100)
        self.assertEqual(self.service.check().sources[0].status, "error")

    def test_fwupd_nothing_to_do_exit(self):
        for output in ('{"Devices": []}', "No updates available"):
            self.responses["firmware"] = ActionResult(False, "", 2, stdout=output)
            self.assertEqual(self.service.check().sources[2].status, "up_to_date")
        self.responses["firmware"] = ActionResult(False, "", 2, stdout="garbage")
        self.assertEqual(self.service.check().sources[2].status, "error")

    def test_fwupd_no_supported_devices(self):
        self.responses["firmware"] = ActionResult(False, "", 2, stderr="No supported devices found")
        self.assertEqual(self.service.check().sources[2].status, "unsupported")

    def test_future_schema_never_overwritten_even_without_load(self):
        raw = '{"schema_version": 99, "private_future_data": [1]}'
        self.path.write_text(raw)
        self.assertEqual(self.service.load().storage_status, "future_schema")
        self.assertEqual(self.service.check().storage_status, "future_schema")
        self.assertEqual(self.path.read_text(), raw)

    def test_future_schema_created_during_check_preserved(self):
        def execute(vector, action_id, timeout):
            self.path.write_text('{"schema_version": 2}')
            return self.responses[action_id.removeprefix("update-overview-")]
        self.runtime.execute_read_only.side_effect = execute
        self.assertEqual(self.service.check().storage_status, "future_schema")
        self.assertEqual(json.loads(self.path.read_text())["schema_version"], 2)

    def test_corrupt_storage_retained_and_reported(self):
        self.path.write_text("broken")
        self.assertEqual(self.service.load().storage_status, "unavailable")
        self.assertEqual(self.service.check().storage_status, "unavailable")
        self.assertEqual(self.path.read_text(), "broken")

    @patch("services.software.update_overview.atomic_write_json", side_effect=OSError("disk full"))
    def test_storage_failure_does_not_hide_results(self, write):
        snapshot = self.service.check()
        self.assertEqual(snapshot.storage_status, "unavailable")
        self.assertTrue(all(source.status == "up_to_date" for source in snapshot.sources))

    def test_invalid_cache_timestamp_does_not_crash(self):
        self.service.check()
        payload = json.loads(self.path.read_text())
        payload["sources"][0]["checked_at"] = "bad timestamp"
        self.path.write_text(json.dumps(payload))
        self.assertEqual(self.service.load().storage_status, "unavailable")

    def test_oversized_candidates_report_error(self):
        self.responses["system"].stdout = "a.x86_64 " + "v" * 513 + " updates"
        self.assertEqual(self.service.check().sources[0].error_code, "invalid_output")

    def test_large_normal_list_is_not_truncated(self):
        self.responses["system"].stdout = "a.x86_64 1 updates\n" * 300
        source = self.service.check().sources[0]
        self.assertEqual(source.status, "available")
        self.assertEqual(len(source.items), 300)

    def test_runtime_output_limit_reported(self):
        self.responses["system"] = ActionResult(False, "", -2)
        self.assertEqual(self.service.check().sources[0].error_code, "output_truncated")

    def test_runtime_missing_tool_race_and_firmware_timeout(self):
        self.responses["system"] = ActionResult(False, "", 127)
        self.responses["firmware"] = ActionResult(False, "", -1)
        snapshot = self.service.check()
        self.assertEqual(snapshot.sources[0].status, "missing_tool")
        self.assertEqual(snapshot.sources[2].error_code, "timeout")


class TestOverviewRuntime(unittest.TestCase):
    @patch("services.software.update_overview.selectors.DefaultSelector")
    @patch("services.software.update_overview.subprocess.Popen")
    def test_cancel_running_process_kills_reaps_and_closes_pipes(self, popen, selector_factory):
        runtime = OverviewRuntime(Mock(), Mock())
        process = popen.return_value
        process.poll.return_value = None
        selector = selector_factory.return_value.__enter__.return_value
        selector.get_map.return_value = True
        selector.select.side_effect = lambda timeout: runtime.cancelled.set() or []
        with self.assertRaises(OverviewCancelled):
            runtime.execute_read_only(["dnf5", "check-update", "--quiet"], action_id="test")
        process.kill.assert_called_once()
        process.wait.assert_called_once_with(timeout=5)
        process.stdout.close.assert_called_once()
        process.stderr.close.assert_called_once()

    @patch("services.software.update_overview.subprocess.Popen")
    def test_only_closed_read_only_vectors(self, popen):
        runtime = OverviewRuntime(Mock(), Mock())
        self.assertEqual(runtime.execute_read_only(["dnf5", "update", "-y"], action_id="test").exit_code, 126)
        popen.assert_not_called()

    @patch("services.software.update_overview.os.read")
    @patch("services.software.update_overview.selectors.DefaultSelector")
    @patch("services.software.update_overview.subprocess.Popen")
    def test_full_output_and_c_locale(self, popen, selector_factory, read):
        process = popen.return_value
        process.wait.return_value = 100
        process.poll.return_value = 100
        selector = selector_factory.return_value.__enter__.return_value
        selector.get_map.side_effect = [True, True, False]
        out = Mock(fileobj=process.stdout, data="stdout")
        err = Mock(fileobj=process.stderr, data="stderr")
        selector.select.side_effect = [[(out, 1)], [(out, 1), (err, 1)]]
        read.side_effect = [b"a" * 8000, b"", b""]
        result = OverviewRuntime(Mock(), Mock()).execute_read_only(["dnf5", "check-update", "--quiet"], action_id="test")
        self.assertEqual(len(result.stdout), 8000)
        self.assertEqual(popen.call_args.kwargs["env"]["LC_ALL"], "C")
        process.stdout.close.assert_called_once()

    @patch("services.software.update_overview.MAX_BYTES", 8)
    @patch("services.software.update_overview.os.read", return_value=b"123456789")
    @patch("services.software.update_overview.selectors.DefaultSelector")
    @patch("services.software.update_overview.subprocess.Popen")
    def test_output_is_bounded_and_process_killed(self, popen, selector_factory, read):
        process = popen.return_value
        process.poll.return_value = None
        selector = selector_factory.return_value.__enter__.return_value
        selector.get_map.return_value = True
        selector.select.return_value = [(Mock(fileobj=process.stdout, data="stdout"), 1)]
        result = OverviewRuntime(Mock(), Mock()).execute_read_only(["dnf5", "check-update", "--quiet"], action_id="test")
        self.assertEqual(result.exit_code, -2)
        self.assertEqual(read.call_args.args[1], 9)
        process.kill.assert_called_once()
        process.wait.assert_called_once_with(timeout=5)
