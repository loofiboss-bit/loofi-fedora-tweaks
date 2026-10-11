"""Live refresh observation requires a complete busy cycle, not an enabled CTA."""
import importlib.util
from pathlib import Path
import sys
from threading import Event
from types import ModuleType
import unittest
from unittest.mock import Mock, patch


class TestRefreshObservation(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        by = ModuleType("selenium.webdriver.common.by")
        by.By = Mock()
        modules = {key: ModuleType(key) for key in ("selenium", "selenium.webdriver", "selenium.webdriver.common")}
        modules["selenium.webdriver.common.by"] = by
        path = Path(__file__).resolve().parents[1] / "e2e/tests/helpers.py"
        spec = importlib.util.spec_from_file_location("refresh_observation_helpers", path)
        cls.helpers = importlib.util.module_from_spec(spec)
        loader = patch.dict(sys.modules, modules)
        loader.start()
        try:
            spec.loader.exec_module(cls.helpers)
        finally:
            loader.stop()

    def setUp(self):
        self.started, self.completed, self.stop = Event(), Event(), Event()
        self.clock = 0.0

    def tick(self, seconds):
        self.clock += seconds

    def observe(self, read, timeout=0.1):
        monotonic = patch.object(self.helpers.time, "monotonic", side_effect=lambda: self.clock)
        sleep = patch.object(self.helpers.time, "sleep", side_effect=self.tick)
        monotonic.start()
        sleep.start()
        try:
            self.helpers.observe_refresh(read, self.started, self.completed, self.stop, timeout=timeout, poll_interval=0.01)
        finally:
            sleep.stop()
            monotonic.stop()

    def test_disconnected_always_enabled_refresh_never_reports_work(self):
        read = Mock(return_value=True)
        self.observe(read)
        self.assertGreater(read.call_count, 1)
        self.assertFalse(self.started.is_set())
        self.assertFalse(self.completed.is_set())
        self.assertTrue(self.stop.is_set())
        self.assertGreaterEqual(self.clock, 0.1)

    def test_enabled_disabled_enabled_reports_both_observed_transitions(self):
        read = Mock(side_effect=[True, False, False, True])
        self.observe(read)
        self.assertEqual(read.call_count, 4)
        self.assertTrue(self.started.is_set())
        self.assertTrue(self.completed.is_set())
        self.assertTrue(self.stop.is_set())

    def test_initially_disabled_then_enabled_is_not_a_started_refresh(self):
        read = Mock(side_effect=[False, True] + [True] * 20)
        self.observe(read)
        self.assertFalse(self.started.is_set())
        self.assertFalse(self.completed.is_set())

    def test_busy_without_return_to_enabled_is_incomplete(self):
        read = Mock(side_effect=[True] + [False] * 20)
        self.observe(read)
        self.assertTrue(self.started.is_set())
        self.assertFalse(self.completed.is_set())
        self.assertTrue(self.stop.is_set())

    def test_cancelled_before_observation_does_not_read_state(self):
        self.stop.set()
        read = Mock()
        self.observe(read)
        read.assert_not_called()
        self.assertFalse(self.started.is_set())
        self.assertFalse(self.completed.is_set())

    def test_cancellation_during_read_cannot_report_a_transition(self):
        def read():
            self.stop.set()
            return False
        self.observe(read)
        self.assertFalse(self.started.is_set())
        self.assertFalse(self.completed.is_set())

    def test_read_failure_propagates_and_finishes_observation(self):
        with self.assertRaisesRegex(RuntimeError, "disappeared"):
            self.observe(Mock(side_effect=RuntimeError("accessible disappeared")))
        self.assertTrue(self.stop.is_set())
        self.assertFalse(self.started.is_set())
        self.assertFalse(self.completed.is_set())

    def test_invalid_bounds_reject_without_reading(self):
        read = Mock()
        with self.assertRaises(ValueError):
            self.helpers.observe_refresh(read, self.started, self.completed, self.stop, timeout=0)
        read.assert_not_called()


if __name__ == "__main__":
    unittest.main()
