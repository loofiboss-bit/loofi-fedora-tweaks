"""Everyday explicit update inspection and asynchronous page lifetime contracts."""

import time
import unittest
from threading import Event
from unittest.mock import Mock

from PyQt6 import sip
from PyQt6.QtCore import QCoreApplication, QEvent
from PyQt6.QtWidgets import QApplication

from services.software.update_overview import OverviewCancelled, UpdateOverviewSnapshot, UpdateSourceResult
from ui.update_overview import UpdateCheckWorker, UpdateOverviewWidget


class UpdateOverviewUiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.snapshot = UpdateOverviewSnapshot()
        self.service = Mock()
        self.service.load.return_value = self.snapshot
        self.service.check.return_value = self.snapshot
        self.widget = UpdateOverviewWidget(self.service)
        self.addCleanup(self.dispose_widget)

    def dispose_widget(self):
        if not sip.isdeleted(self.widget):
            self.widget.deleteLater()

    def pump_until(self, predicate):
        deadline = time.monotonic() + 3
        while not predicate() and time.monotonic() < deadline:
            self.app.processEvents()
            time.sleep(0.001)
        self.assertTrue(predicate())

    def test_construction_and_navigation_only_read_saved_state(self):
        self.widget.show()
        self.app.processEvents()
        self.widget.hide()
        self.widget.show()
        self.app.processEvents()
        self.service.check.assert_not_called()
        self.assertTrue(self.widget.check_button.isEnabled())
        self.assertEqual(self.widget.check_button.property("buttonRole"), "primary")

    def test_explicit_check_is_single_flight_and_runs_off_gui_thread(self):
        entered, release = Event(), Event()

        def check():
            entered.set()
            release.wait(2)
            return self.snapshot

        self.service.check.side_effect = check
        self.widget.check()
        self.pump_until(entered.is_set)
        self.widget.check()
        self.assertFalse(self.widget.check_button.isEnabled())
        self.assertEqual(self.service.check.call_count, 1)
        release.set()
        self.pump_until(lambda: self.widget._worker is None)
        self.assertTrue(self.widget.check_button.isEnabled())

    def test_hidden_page_ignores_late_result_and_reloads_on_return(self):
        self.widget.show()
        self.app.processEvents()
        self.widget.hide()
        result = UpdateOverviewSnapshot(sources=(UpdateSourceResult(source="system", status="error"),))
        self.widget._completed(result)
        self.assertEqual(self.widget.rows["system"][0].property("sourceStatus"), "unchecked")
        self.service.load.return_value = result
        self.widget.show()
        self.app.processEvents()
        self.assertEqual(self.widget.rows["system"][0].property("sourceStatus"), "error")

    def test_application_quit_cancels_and_joins_active_worker(self):
        entered, cancelled = Event(), Event()

        def check():
            entered.set()
            cancelled.wait(2)
            raise OverviewCancelled()

        self.service.check.side_effect = check
        self.service.cancel.side_effect = cancelled.set
        self.widget.check()
        self.pump_until(entered.is_set)
        worker = self.widget._worker
        self.app.aboutToQuit.emit()
        self.assertFalse(worker.isRunning())
        self.assertTrue(cancelled.is_set())
        self.pump_until(lambda: worker not in UpdateCheckWorker.active)

    def test_deleted_page_does_not_own_running_thread(self):
        entered, release = Event(), Event()

        def check():
            entered.set()
            release.wait(2)
            return self.snapshot

        self.service.check.side_effect = check
        self.widget.check()
        self.pump_until(entered.is_set)
        worker = self.widget._worker
        self.assertIsNot(worker.parent(), self.widget)
        self.widget.deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        release.set()
        self.pump_until(lambda: worker not in UpdateCheckWorker.active)

    def test_failure_is_not_empty_or_success_and_stale_success_is_warning(self):
        snapshot = UpdateOverviewSnapshot(sources=(
            UpdateSourceResult(source="system", status="error", error_code="timeout"),
            UpdateSourceResult(source="flatpak", status="up_to_date", checked_at="2026-01-01T00:00:00Z", stale=True),
        ))
        self.widget.set_snapshot(snapshot)
        self.assertIn("Unknown", self.widget.rows["system"][1].text())
        self.assertEqual(self.widget.rows["system"][0].property("resultKind"), "warning")
        self.assertEqual(self.widget.rows["flatpak"][0].property("resultKind"), "warning")
        self.assertIn("Out of date", self.widget.rows["flatpak"][0].message_label.text())

    def test_future_storage_warning_keeps_check_results_visible(self):
        self.widget.set_snapshot(UpdateOverviewSnapshot(storage_status="future_schema"))
        self.assertEqual(self.widget.feedback.property("resultKind"), "warning")
        self.assertIn("preserved", self.widget.feedback.message_label.text())
