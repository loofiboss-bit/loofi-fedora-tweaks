"""Read-only Overview presentation and shared sampler lifecycle regressions."""
from __future__ import annotations

from datetime import datetime, timezone, timedelta
from threading import Event, get_ident
from time import monotonic
from types import SimpleNamespace
import unittest
from unittest.mock import MagicMock

from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QApplication, QWidget

from ui.dashboard_controller import DashboardController
from ui.overview_page import OverviewPage, MetricGraph


def snapshot(value=None, status="sampling", stamp=None):
    stamp = stamp or datetime.now(timezone.utc)
    return SimpleNamespace(identity={"hostname": "Fixture", "os": "Fedora"}, collected_at=stamp,
                           metrics=(SimpleNamespace(id="cpu", group="cpu", label="CPU usage", value=value,
                                                    unit="%", status=status, source="/proc/stat", sampled_at=stamp,
                                                    reason="First sample" if status == "sampling" else "", detail="",
                                                    high=None, critical=None),))


class TestDashboardUi(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_ctor_does_not_start_sampling(self):
        page = OverviewPage()
        controller = MagicMock()
        controller.latest_snapshot = None
        page.set_controller(controller)
        controller.set_consumer_active.assert_called_once_with("overview", False)
        controller.refresh.assert_not_called()
        page.cleanup()

    def test_first_sample_and_unavailable_never_present_fake_zero(self):
        page = OverviewPage()
        page.set_snapshot(snapshot())
        row = page._rows["cpu"]
        self.assertIn("Waiting", row.value.text())
        self.assertIn("First sample", row.reason.text())
        self.assertNotIn("0 %", row.value.text())
        page.set_snapshot(snapshot(25.0, "ready"))
        self.assertIn("25.0 %", row.value.text())
        self.assertEqual(list(row.graph.points)[-1], 25)
        page.set_snapshot(snapshot(None, "error"))
        self.assertEqual(row.badge.text_label.text(), "Read failed")
        self.assertIsNone(list(row.graph.points)[-1])
        page.cleanup()

    def test_out_of_order_snapshot_is_rejected(self):
        page = OverviewPage()
        now = datetime.now(timezone.utc)
        page.set_snapshot(snapshot(30.0, "ok", now))
        page.set_snapshot(snapshot(15.0, "ok", now - timedelta(seconds=10)))
        self.assertIn("30.0 %", page._rows["cpu"].value.text())

    def test_responsive_grid_and_accessible_actions(self):
        page = OverviewPage()
        for width, columns in ((1200, 4), (960, 4), (800, 2), (500, 1), (400, 1)):
            page._reflow(width)
            self.assertEqual(page._columns, columns)
            self.assertEqual(page.main_grid.getItemPosition(3)[:2], (3 // columns, 3 % columns))
        self.assertTrue(page.refresh_button.accessibleName())
        self.assertTrue(page.pause_button.accessibleName())
        self.assertEqual(page._maintenance["updates"][1].text(), "No recorded result yet")

    def test_pause_updates_consumer_and_preserves_snapshot(self):
        page = OverviewPage()
        controller = MagicMock()
        controller.latest_snapshot = None
        page.set_controller(controller)
        page.set_active(True)
        page._toggle_pause()
        controller.set_consumer_active.assert_called_with("overview", False)
        self.assertFalse(page.refresh_button.isEnabled())
        page._toggle_pause()
        controller.set_consumer_active.assert_called_with("overview", True)
        page.cleanup()

    def test_snapshot_presents_only_real_cached_maintenance(self):
        page = OverviewPage()
        sample = snapshot(20, "ready")
        sample.maintenance = {"updates": {"summary": "Two updates available", "checked_at": sample.collected_at}}
        page.set_snapshot(sample)
        self.assertIn("Two updates available", page._maintenance["updates"][1].text())
        self.assertEqual(page._maintenance["health"][1].text(), "No recorded result yet")

    def test_maintenance_buttons_request_existing_routes(self):
        page = OverviewPage()
        routes = []
        page.routeRequested.connect(routes.append)
        for card, label in page._maintenance.values():
            card.body.itemAt(card.body.count() - 1).widget().click()
        self.assertEqual(routes, ["maintenance:updates", "maintenance:health-timeline", "activity"])

    def test_next_steps_show_routes_and_preserve_keyboard_focus_targets(self):
        page = OverviewPage()
        sample = snapshot(20, "ready")
        sample.maintenance = {"activity": {"status": "awaiting_reboot", "detail": "update-fedora-system",
                                            "sampled_at": sample.collected_at}}
        page.set_snapshot(sample)
        self.assertEqual(len(page._next_step_rows), 3)
        routes = []
        page.routeRequested.connect(routes.append)
        rows = list(page._next_step_rows)
        for row in rows:
            button = row.layout().itemAt(2).widget()
            self.assertTrue(button.accessibleName())
            button.click()
        self.assertEqual(routes, ["maintenance:updates", "health", "maintenance:updates"])
        page.set_snapshot(sample)
        self.assertEqual(page._next_step_rows, rows)
        sample.maintenance["activity"]["sampled_at"] += timedelta(seconds=5)
        page.set_snapshot(sample)
        self.assertEqual(page._next_step_rows, rows)
        page.cleanup()

    def test_paused_view_ignores_updates_from_other_consumer(self):
        page = OverviewPage()
        page.set_snapshot(snapshot(20.0, "ready"))
        page._toggle_pause()
        page.set_snapshot(snapshot(90.0, "ready"))
        self.assertIn("20.0 %", page._rows["cpu"].value.text())
        self.assertEqual(page.notice.title_label.text(), "Measurements paused")

    def test_graph_history_is_bounded_and_keeps_gaps(self):
        graph = MetricGraph("CPU", "%")
        for value in range(80):
            graph.add_sample(value)
        graph.add_sample(None)
        self.assertEqual(len(graph.points), 60)
        self.assertIsNone(graph.points[-1])

    def test_battery_card_hides_when_unavailable_and_reflows(self):
        page = OverviewPage()
        page.resize(900, 650)
        sample = snapshot(20.0, "ready")
        sample.metrics = (*sample.metrics, SimpleNamespace(
            id="battery.none", group="battery", label="Battery", value=None,
            unit="%", status="unavailable", source="/sys/class/power_supply",
            sampled_at=None, reason="No battery detected", detail="", high=None, critical=None
        ))
        page.set_snapshot(sample)
        self.assertTrue(page._cards["battery"].isHidden())

        sample_with_bat = snapshot(20.0, "ready")
        sample_with_bat.metrics = (*sample_with_bat.metrics, SimpleNamespace(
            id="battery:BAT0", group="battery", label="BAT0", value=85.0,
            unit="%", status="ready", source="/sys/class/power_supply",
            sampled_at=sample.collected_at, reason="", detail="", high=None, critical=None
        ))
        page.set_snapshot(sample_with_bat)
        self.assertFalse(page._cards["battery"].isHidden())
        page.cleanup()

    def test_refresh_button_debounce(self):
        page = OverviewPage()
        controller = MagicMock()
        controller.latest_snapshot = None
        page.set_controller(controller)
        self.assertTrue(page.refresh_button.isEnabled())
        page._refresh()
        self.assertFalse(page.refresh_button.isEnabled())
        controller.refresh.assert_called_once()
        page.cleanup()


class _Service:
    def __init__(self):
        self.calls = []
        self.resets = 0
        self.thread = None
        self.entered = Event()
        self.release = Event()
        self.release.set()

    def reset_baselines(self):
        self.resets += 1

    def collect(self, fast=True, slow=True):
        self.thread = get_ident()
        self.calls.append((fast, slow))
        self.entered.set()
        self.release.wait(2)
        return snapshot(20.0, "ok")


class TestDashboardController(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def _drain(self, controller):
        for _ in range(100):
            self.app.processEvents()
            if controller._worker is None:
                return
            QTest.qWait(5)
        self.fail("Sampler did not finish")

    def test_idle_has_no_reads_and_work_runs_off_ui_thread(self):
        service = _Service()
        controller = DashboardController(service=service)
        results = []
        controller.snapshotReady.connect(results.append)
        controller.refresh()
        self.assertEqual(service.calls, [])
        controller.set_consumer_active("overview", True)
        self._drain(controller)
        self.assertNotEqual(service.thread, get_ident())
        self.assertEqual(len(results), 1)
        self.assertEqual(service.resets, 1)
        controller.set_consumer_active("overview", False)
        self.assertFalse(controller.fast_timer.isActive())
        self.assertFalse(controller.slow_timer.isActive())
        controller.cleanup()

    def test_hidden_read_is_discarded_and_resume_resets_baseline(self):
        service = _Service()
        service.release.clear()
        controller = DashboardController(service=service)
        results = []
        controller.snapshotReady.connect(results.append)
        controller.set_consumer_active("overview", True)
        self.assertTrue(service.entered.wait(1))
        controller.set_consumer_active("overview", False)
        service.release.set()
        self._drain(controller)
        self.assertEqual(results, [])
        controller.set_consumer_active("monitor", True)
        self._drain(controller)
        self.assertEqual(service.resets, 2)
        controller.cleanup()

    def test_multiple_consumers_share_sampler_and_suspend_stops_timers(self):
        service = _Service()
        controller = DashboardController(service=service)
        controller.set_consumer_active("overview", True)
        self._drain(controller)
        controller.set_consumer_active("monitor", True)
        controller.set_consumer_active("overview", False)
        self.assertTrue(controller.active)
        self.assertEqual(len(service.calls), 1)
        controller.set_suspended(True)
        self.assertFalse(controller.active)
        self.assertFalse(controller.fast_timer.isActive())
        controller.set_suspended(False)
        self._drain(controller)
        self.assertEqual(service.resets, 2)
        controller.cleanup()

    def test_requests_coalesce_and_cleanup_joins_live_worker(self):
        service = _Service()
        service.release.clear()
        controller = DashboardController(service=service)
        controller.set_consumer_active("overview", True)
        self.assertTrue(service.entered.wait(1))
        for _ in range(5):
            controller.refresh()
        self.assertEqual(len(service.calls), 1)
        service.release.set()
        self._drain(controller)
        self.assertEqual(len(service.calls), 2)
        controller.refresh()
        controller.cleanup()
        self.assertFalse(controller.active)
        self.app.processEvents()
        self.assertIsNone(controller._worker)

    def test_failure_is_reported_and_worker_is_released(self):
        service = _Service()
        service.collect = MagicMock(side_effect=OSError("Fixture failure"))
        controller = DashboardController(service=service)
        failures = []
        controller.failed.connect(failures.append)
        controller.set_consumer_active("overview", True)
        self._drain(controller)
        self.assertEqual(failures, ["Fixture failure"])
        self.assertIsNone(controller.latest_snapshot)
        controller.cleanup()

    def test_blocked_reader_stops_without_unbounded_wait_or_destruction(self):
        service = _Service()
        service.release.clear()
        controller = DashboardController(service=service)
        stopped, results = [], []
        controller.stopped.connect(lambda: stopped.append(get_ident()))
        controller.snapshotReady.connect(results.append)
        controller.set_consumer_active("overview", True)
        self.assertTrue(service.entered.wait(1))
        try:
            started = monotonic()
            controller.request_stop()
            self.assertLess(monotonic() - started, 0.1)
            self.assertFalse(controller.active)
            self.assertTrue(controller.busy)
            self.assertFalse(controller.fast_timer.isActive())
            started = monotonic()
            self.assertFalse(controller.wait_for_stop(20))
            self.assertLess(monotonic() - started, 0.2)
            self.assertFalse(controller.cleanup(timeout_ms=0))
            self.assertIsNotNone(controller._worker)
            self.assertEqual(stopped, [])
        finally:
            service.release.set()
            self._drain(controller)
        self.assertFalse(controller.busy)
        self.assertEqual(stopped, [get_ident()])
        self.assertEqual(results, [])
        self.assertTrue(controller.cleanup(timeout_ms=20))
        self.app.processEvents()
        self.assertEqual(len(stopped), 1)

    def test_minimized_window_suspends_collection(self):
        window = QWidget()
        service = _Service()
        controller = DashboardController(window, service=service)
        controller.set_consumer_active("overview", True)
        self._drain(controller)
        window.showMinimized()
        self.app.processEvents()
        self.assertFalse(controller.active)
        controller.cleanup()
        window.close()


class TestSharedMonitor(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_performance_reuses_snapshot_without_private_reads(self):
        from ui.monitor_tab import MonitorTab
        service = _Service()
        controller = DashboardController(service=service)
        monitor = MonitorTab()
        monitor.set_dashboard_controller(controller)
        monitor._performance_tab.collector = MagicMock()
        sample = snapshot(55, "ready")
        sample.metrics[0].id = "cpu.usage"
        sample.cpu_per_core = (10.0, 30.0)
        monitor._performance_tab._show_dashboard_snapshot(sample)
        self.assertIn("55%", monitor._performance_tab.lbl_cpu.text())
        self.assertEqual(len(monitor._performance_tab.cpu_core_bars), 2)
        monitor._performance_tab._on_tick()
        monitor._performance_tab.collector.collect_all.assert_not_called()
        self.assertFalse(monitor._performance_tab.refresh_timer.isActive())
        monitor.cleanup()
        controller.cleanup()

    def test_monitor_stop_preserves_blocked_sampler_until_finished(self):
        from unittest.mock import patch
        from ui.monitor_tab import MonitorTab
        entered, release = Event(), Event()

        def read():
            entered.set()
            release.wait(2)
            return []

        @patch("ui.monitor_tab.ProcessManager.get_all_processes", side_effect=read)
        def exercise(mock_read):
            monitor = MonitorTab()
            stopped = []
            monitor.stopped.connect(lambda: stopped.append(get_ident()))
            process = monitor._processes_tab
            process.set_active(True)
            self.assertTrue(entered.wait(1))
            try:
                started = monotonic()
                monitor.request_stop()
                self.assertLess(monotonic() - started, 0.1)
                self.assertTrue(monitor.sampling_busy)
                self.assertFalse(process.refresh_timer.isActive())
                started = monotonic()
                self.assertFalse(monitor.wait_for_stop(20))
                self.assertLess(monotonic() - started, 0.2)
                self.assertFalse(monitor.cleanup(timeout_ms=0))
                self.assertIsNotNone(process._process_worker)
                self.assertEqual(stopped, [])
            finally:
                release.set()
                for _ in range(100):
                    self.app.processEvents()
                    if not monitor.sampling_busy:
                        break
                    QTest.qWait(5)
            self.assertFalse(monitor.sampling_busy)
            self.assertEqual(stopped, [get_ident()])
            self.assertEqual(process.lbl_summary.text(), "Waiting for process measurements")
            self.assertTrue(monitor.cleanup(timeout_ms=20))
            self.app.processEvents()
            self.assertEqual(len(stopped), 1)

        exercise()

    def test_process_worker_reads_off_ui_thread_and_discards_hidden_result(self):
        from unittest.mock import patch
        from ui.monitor_tab import MonitorTab
        entered, release = Event(), Event()
        read_thread = []

        def read():
            read_thread.append(get_ident())
            entered.set()
            release.wait(2)
            return []

        # This test controls asynchronous synchronization rather than host reads.
        @patch("ui.monitor_tab.ProcessManager.get_all_processes", side_effect=read)
        def exercise(mock_read):
            monitor = MonitorTab()
            process = monitor._processes_tab
            process.set_active(True)
            self.assertTrue(entered.wait(1))
            for _ in range(5):
                process.refresh_processes()
            self.assertEqual(mock_read.call_count, 1)
            process.set_active(False)
            release.set()
            for _ in range(100):
                self.app.processEvents()
                if process._process_worker is None:
                    break
                QTest.qWait(5)
            self.assertNotEqual(read_thread[0], get_ident())
            self.assertEqual(process.lbl_summary.text(), "Waiting for process measurements")
            self.assertFalse(process.refresh_timer.isActive())
            monitor.cleanup()

        exercise()
