"""End-to-end Home contracts for explicit asynchronous System Check."""

from __future__ import annotations

import threading
import time
import unittest
from datetime import datetime, timezone

from PyQt6.QtCore import QObject, Qt, pyqtSignal
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QApplication, QLabel, QPushButton

from core.home import HomeSummary
from core.system_check.models import CheckProgress, CheckSourceError, SystemCheckResult
from core.workers.system_check_worker import SystemCheckWorker
from ui.atlas_dashboard_tab import AtlasDashboardTab


def _summary(*, state="empty", text="No saved status exists.") -> HomeSummary:
    return HomeSummary(
        overall_state="unknown" if state != "error" else "attention",
        data_state=state,
        summary=text,
        generated_at=datetime.now(timezone.utc),
        primary_recommendation=None,
        attention_items=(),
        common_tasks=(),
        recent_change=None,
        freshness_state="stale" if state == "stale" else "unavailable",
    )


class _MutableSummaryService:
    def __init__(self, *values):
        self.values = list(values)
        self.calls = 0

    def summary(self):
        value = self.values[min(self.calls, len(self.values) - 1)]
        self.calls += 1
        return value


class _FakeWorker(QObject):
    check_progress = pyqtSignal(object)
    finished = pyqtSignal(object)
    error = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.running = False
        self.started = False
        self.cancelled = False
        self.waited = False

    def start(self):
        self.started = True
        self.running = True

    def isRunning(self):
        return self.running

    def wait(self, _milliseconds):
        self.waited = True
        return not self.running

    def cancel(self):
        self.cancelled = True
        self.running = False
        self.error.emit("Operation cancelled by user")

    def complete(self, result):
        self.running = False
        self.finished.emit(result)


class TestSystemCheckHomeFlow(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def _tab(self, service=None):
        workers = []

        def factory(parent):
            worker = _FakeWorker(parent)
            workers.append(worker)
            return worker

        tab = AtlasDashboardTab(
            home_service=service or _MutableSummaryService(_summary()),
            check_worker_factory=factory,
        )
        return tab, workers

    def test_no_check_starts_before_explicit_button_activation(self):
        tab, workers = self._tab()

        self.assertEqual(workers, [])

        tab.findChild(QPushButton, "homeCheckNow").click()

        self.assertEqual(len(workers), 1)
        self.assertTrue(workers[0].started)
        self.assertTrue(workers[0].isRunning())

    def test_progress_shows_source_percentage_and_elapsed_time(self):
        tab, workers = self._tab()
        tab.start_system_check()
        workers[0].check_progress.emit(CheckProgress(
            "maintenance",
            "running",
            2,
            5,
            1.25,
        ))

        self.assertIn("Updates, services, and disk", tab.check_source_label.text())
        self.assertIn("1.2", tab.check_elapsed_label.text())
        self.assertEqual(tab.check_progress.progress_bar.value(), 40)
        self.assertFalse(tab.cancel_check_button.isHidden())

    def test_completed_check_refreshes_home_from_persisted_result(self):
        service = _MutableSummaryService(
            _summary(),
            _summary(state="stale", text="Refreshed from persisted System Check."),
        )
        tab, workers = self._tab(service)
        tab.start_system_check()
        workers[0].complete(SystemCheckResult(
            "check-1",
            "system-check-quick-v1",
            "completed",
            False,
            10.0,
            11.0,
        ))

        self.assertEqual(service.calls, 2)
        self.assertEqual(tab.state_label.text(), "Refreshed from persisted System Check.")
        self.assertIn("Check complete", tab.check_notice.title_label.text())

    def test_partial_result_names_unavailable_source_and_never_reports_good(self):
        service = _MutableSummaryService(
            _summary(),
            _summary(state="error", text="Some checks were unavailable."),
        )
        tab, workers = self._tab(service)
        tab.start_system_check()
        workers[0].complete(SystemCheckResult(
            "check-2",
            "system-check-quick-v1",
            "partial",
            False,
            10.0,
            11.0,
            source_errors=(
                CheckSourceError("maintenance", "collector-timeout", "Timed out", 1000.0, True),
            ),
            completed_sources=("state-integrity",),
        ))

        self.assertEqual(tab.state_card.property("overallState"), "attention")
        self.assertIn("Updates, services, and disk", tab.check_notice.message_label.text())
        self.assertNotIn("good", tab.check_notice.title_label.text().lower())

    def test_cancellation_is_visible_and_keeps_previous_summary(self):
        service = _MutableSummaryService(_summary(text="Previous saved status."))
        tab, workers = self._tab(service)
        tab.start_system_check()

        tab.cancel_system_check()

        self.assertTrue(workers[0].cancelled)
        self.assertEqual(service.calls, 1)
        self.assertEqual(tab.state_label.text(), "Previous saved status.")
        self.assertIn("cancelled", tab.check_notice.title_label.text().lower())

    def test_keyboard_starts_and_cancels_check(self):
        tab, workers = self._tab()
        tab.show()
        self.app.processEvents()

        check_button = tab.findChild(QPushButton, "homeCheckNow")
        check_button.setFocus()
        QTest.keyClick(check_button, Qt.Key.Key_Space)
        self.assertTrue(workers[0].started)

        tab.cancel_check_button.setFocus()
        QTest.keyClick(tab.cancel_check_button, Qt.Key.Key_Space)
        self.assertTrue(workers[0].cancelled)
        self.assertIn("cancelled", tab.check_notice.title_label.text().lower())

    def test_cleanup_cancels_running_worker(self):
        tab, workers = self._tab()
        tab.start_system_check()

        tab.cleanup()

        self.assertTrue(workers[0].cancelled)
        self.assertTrue(workers[0].waited)

    def test_real_worker_runs_service_off_ui_thread_and_cancels_cooperatively(self):
        entered = threading.Event()

        class Service:
            @staticmethod
            def run(*, cancel_event, progress_callback):
                entered.set()
                progress_callback(CheckProgress("maintenance", "running", 0, 5, 0.0))
                cancel_event.wait(2.0)
                return SystemCheckResult(
                    "check-worker",
                    "system-check-fixture-v1",
                    "cancelled",
                    False,
                    10.0,
                    11.0,
                    cancelled_sources=("maintenance",),
                )

        worker = SystemCheckWorker(service_factory=Service)
        started_at = time.monotonic()
        worker.start()

        self.assertLess(time.monotonic() - started_at, 0.1)
        self.assertTrue(entered.wait(1.0))
        self.assertTrue(worker.isRunning())

        worker.cancel()
        self.assertTrue(worker.wait(1000))
        self.assertFalse(worker.isRunning())


if __name__ == "__main__":
    unittest.main()
