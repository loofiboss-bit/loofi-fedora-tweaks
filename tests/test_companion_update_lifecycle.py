"""Updates shutdown waits for both local inspection workers."""
import time
import unittest
from threading import Event
from unittest.mock import Mock

from PyQt6.QtWidgets import QApplication
from services.software.update_overview import UpdateOverviewSnapshot
from ui.update_workflow import UpdateWorkflowPage


class TestCompanionUpdateLifecycle(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def pump_until(self, predicate):
        deadline = time.monotonic() + 3
        while not predicate() and time.monotonic() < deadline:
            self.app.processEvents()
        self.assertTrue(predicate())

    def test_simultaneous_checks_emit_stopped_only_when_both_idle(self):
        source_started, source_release = Event(), Event()
        preparation_started, preparation_release = Event(), Event()
        source = Mock()

        def source_check():
            source_started.set()
            source_release.wait(3)
            return UpdateOverviewSnapshot()

        source.check.side_effect = source_check
        source.cancel.side_effect = source_release.set
        preparation = Mock()

        def prepare(_target):
            preparation_started.set()
            preparation_release.wait(3)
            return None

        preparation.prepare.side_effect = prepare
        page = UpdateWorkflowPage(service=source)
        page.preparation.service = preparation
        stopped = Mock()
        page.stopped.connect(stopped)
        try:
            self.assertTrue(page.start_check("system"))
            page.preparation.check()
            self.assertTrue(source_started.wait(1))
            self.assertTrue(preparation_started.wait(1))
            self.assertTrue(page.busy)
            page.request_stop()
            source.cancel.assert_called_once()
            preparation.cancel.assert_called_once()
            self.pump_until(lambda: page._check_worker is None)
            self.assertTrue(page.busy)
            stopped.assert_not_called()
            preparation_release.set()
            self.pump_until(lambda: not page.busy)
            stopped.assert_called_once()
        finally:
            source_release.set()
            preparation_release.set()
            page.cleanup(3000)
            self.app.processEvents()

    def test_failed_wait_retains_owned_worker(self):
        page = UpdateWorkflowPage(service=Mock())
        worker = Mock()
        worker.isRunning.return_value = True
        worker.wait.return_value = False
        page._check_worker = worker
        self.assertFalse(page.cleanup(1))
        self.assertIs(page._check_worker, worker)
        self.assertTrue(page.busy)
        page.service.cancel.assert_called_once()
        worker.wait.return_value = True
        self.assertTrue(page.cleanup(100))
        self.assertIsNone(page._check_worker)
        self.assertFalse(page.busy)
