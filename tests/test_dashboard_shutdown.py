"""Main-window reader shutdown deferral, budgets, and wrapper ownership."""
from __future__ import annotations

import gc
from threading import Event
from types import SimpleNamespace
import unittest
from unittest.mock import MagicMock, patch
import weakref

from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QApplication, QWidget

from ui.dashboard_controller import DashboardController
from ui.main_window_interactions import MainWindowInteractionMixin, _PENDING_SHUTDOWN_WINDOWS


class _Signal:
    def __init__(self):
        self.callbacks = []

    def connect(self, callback):
        self.callbacks.append(callback)

    def emit(self):
        for callback in tuple(self.callbacks):
            callback()


def reader(kind="busy"):
    resource = SimpleNamespace(stopped=_Signal(), request_stop=MagicMock(), wait_for_stop=MagicMock(return_value=True))
    setattr(resource, kind, True)
    return resource


class _Harness(MainWindowInteractionMixin):
    def __init__(self, dashboard=None, monitor=None):
        self._dashboard_controller = dashboard
        self._sidebar_index = {"monitor": SimpleNamespace(page_widget=monitor)} if monitor is not None else {}
        self._utility_operation_adapter = None
        self._pending_runtime_shutdown = None
        self._status_frame = None
        self._status_label = None
        self._runtime = SimpleNamespace(shutdown=MagicMock())
        self._request_runtime_stop = MagicMock()
        self.close = MagicMock(side_effect=lambda: self._request_runtime_shutdown(action="close"))
        self.tr = lambda text: text
        self.pulse_thread = None


class TestReaderShutdownDeferral(unittest.TestCase):
    def tearDown(self):
        _PENDING_SHUTDOWN_WINDOWS.clear()

    def test_close_waits_for_both_readers_and_connects_before_request(self):
        dashboard, monitor = reader(), reader("sampling_busy")
        window = _Harness(dashboard, monitor)
        dashboard.request_stop.side_effect = lambda: self.assertEqual(len(dashboard.stopped.callbacks), 1)
        monitor.request_stop.side_effect = lambda: self.assertEqual(len(monitor.stopped.callbacks), 1)
        self.assertFalse(window._request_runtime_shutdown(action="close"))
        self.assertEqual(window._pending_runtime_shutdown, "close")
        window._runtime.shutdown.assert_not_called()
        dashboard.busy = False
        dashboard.stopped.emit()
        window.close.assert_not_called()
        self.assertEqual(window._pending_runtime_shutdown, "close")
        monitor.sampling_busy = False
        monitor.stopped.emit()
        window.close.assert_called_once()
        window._runtime.shutdown.assert_called_once()
        self.assertNotIn(window, _PENDING_SHUTDOWN_WINDOWS)

    def test_installed_app_workers_defer_window_destruction(self):
        apps = reader()
        apps.refresh_installed_applications = MagicMock()
        lazy = SimpleNamespace(get_real_widget=lambda: apps)
        window = _Harness()
        window._sidebar_index["install"] = SimpleNamespace(page_widget=lazy)
        self.assertFalse(window._request_runtime_shutdown(action="close"))
        apps.request_stop.assert_called_once()
        window._runtime.shutdown.assert_not_called()
        apps.busy = False
        apps.stopped.emit()
        window.close.assert_called_once()
        window._runtime.shutdown.assert_called_once()

    @patch.object(QApplication, "quit")
    def test_quit_takes_precedence_and_finished_signal_is_connected_once(self, quit_app):
        dashboard = reader()
        window = _Harness(dashboard)
        self.assertFalse(window._request_runtime_shutdown(action="close"))
        self.assertFalse(window._request_runtime_shutdown(action="quit"))
        self.assertFalse(window._request_runtime_shutdown(action="close"))
        self.assertEqual(len(dashboard.stopped.callbacks), 1)
        self.assertEqual(window._pending_runtime_shutdown, "quit")
        dashboard.busy = False
        dashboard.stopped.emit()
        quit_app.assert_called_once()
        window.close.assert_not_called()

    @patch("ui.main_window_interactions.PluginRegistry.instance")
    def test_runtime_stop_requests_samplers_without_blocking_cleanup(self, registry):
        dashboard, monitor = reader(), reader("sampling_busy")
        dashboard.cleanup = MagicMock()
        monitor.cleanup = MagicMock()
        window = _Harness(dashboard, monitor)
        window._set_active_plugin = MagicMock()
        window._status_timer = None
        window.tray_icon = None
        MainWindowInteractionMixin._request_runtime_stop(window)
        dashboard.request_stop.assert_called()
        monitor.request_stop.assert_called()
        dashboard.cleanup.assert_not_called()
        monitor.cleanup.assert_not_called()
        dashboard.wait_for_stop.assert_not_called()
        monitor.wait_for_stop.assert_not_called()
        registry.assert_not_called()

    def test_unvisited_monitor_is_not_instantiated(self):
        lazy = SimpleNamespace(get_real_widget=MagicMock(return_value=None), ensure_loaded=MagicMock())
        window = _Harness(monitor=lazy)
        self.assertEqual(window._runtime_samplers(), ())
        self.assertTrue(window._request_runtime_shutdown())
        lazy.ensure_loaded.assert_not_called()

    @patch("ui.main_window_interactions.monotonic", side_effect=[10.0, 10.001, 10.021, 10.028])
    def test_all_readers_share_one_wait_budget_including_pulse(self, clock):
        dashboard, monitor = reader(), reader("sampling_busy")
        window = _Harness(dashboard, monitor)
        window.pulse_thread = SimpleNamespace(wait=MagicMock(return_value=True))
        dashboard.wait_for_stop.return_value = False
        self.assertFalse(window._wait_for_runtime_stop(0.030))
        budgets = [dashboard.wait_for_stop.call_args.args[0], monitor.wait_for_stop.call_args.args[0],
                   window.pulse_thread.wait.call_args.args[0]]
        self.assertTrue(all(0 <= budget <= 30 for budget in budgets))
        self.assertGreater(budgets[0], budgets[1])
        self.assertGreater(budgets[1], budgets[2])

    def test_realized_companion_pages_are_retained_without_duplicate_aliases(self):
        monitor, health, updates = reader(), reader(), reader()
        window = _Harness(monitor=monitor)
        window._sidebar_index.update({
            "monitor-alias": SimpleNamespace(page_widget=monitor),
            "utility_fix": SimpleNamespace(page_widget=health),
            "utility_update": SimpleNamespace(page_widget=updates),
        })
        self.assertEqual(window._runtime_samplers(), (monitor, health, updates))
        self.assertFalse(window._request_runtime_shutdown())
        for resource in (monitor, health, updates):
            resource.request_stop.assert_called_once()


class _Window(MainWindowInteractionMixin, QWidget):
    def __init__(self, service):
        QWidget.__init__(self)
        self._dashboard_controller = DashboardController(self, service)
        self._sidebar_index = {}
        self._utility_operation_adapter = None
        self._pending_runtime_shutdown = None
        self._runtime = SimpleNamespace(shutdown=MagicMock())
        self._status_frame = None
        self._status_label = None
        self._set_active_plugin = MagicMock()
        self.tray_icon = None
        self.pulse_thread = None


class TestClosingWindowOwnership(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_ignored_close_retains_window_until_reader_finishes(self):
        entered, release = Event(), Event()

        def collect(**kwargs):
            entered.set()
            release.wait(2)
            return SimpleNamespace()

        service = SimpleNamespace(reset_baselines=lambda: None, collect=collect)
        window = _Window(service)
        window.show()
        window._dashboard_controller.set_consumer_active("overview", True)
        self.assertTrue(entered.wait(1))
        reference = weakref.ref(window)
        try:
            self.assertFalse(window.close())
            self.assertIn(window, _PENDING_SHUTDOWN_WINDOWS)
            del window
            gc.collect()
            self.assertIsNotNone(reference())
        finally:
            release.set()
            for _ in range(100):
                self.app.processEvents()
                if not _PENDING_SHUTDOWN_WINDOWS:
                    break
                QTest.qWait(5)
        self.assertEqual(_PENDING_SHUTDOWN_WINDOWS, set())
        if reference() is not None:
            self.assertFalse(reference()._dashboard_controller.busy)
            reference().deleteLater()
        self.app.processEvents()
