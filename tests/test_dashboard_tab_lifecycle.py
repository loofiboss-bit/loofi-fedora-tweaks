"""Tests for dashboard timer lifecycle behavior."""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'loofi-fedora-tweaks'))

from ui.dashboard_tab import DashboardTab  # pyright: ignore[reportMissingImports]


class _DummyTimer:
    def __init__(self, active: bool):
        self._active = active
        self.started_with = None
        self.stop_calls = 0

    def isActive(self):
        return self._active

    def start(self, interval):
        self._active = True
        self.started_with = interval

    def stop(self):
        self._active = False
        self.stop_calls += 1


class TestDashboardTimerLifecycle(unittest.TestCase):
    """Ensure dashboard timers pause/resume with visibility changes."""

    def test_disable_live_updates_stops_active_timers(self):
        tab = DashboardTab.__new__(DashboardTab)
        tab._fast_timer = _DummyTimer(active=True)
        tab._slow_timer = _DummyTimer(active=True)
        tab._fast_interval_ms = 2000
        tab._slow_interval_ms = 10000

        tab._set_live_updates_enabled(False)

        self.assertFalse(tab._fast_timer.isActive())
        self.assertFalse(tab._slow_timer.isActive())
        self.assertEqual(tab._fast_timer.stop_calls, 1)
        self.assertEqual(tab._slow_timer.stop_calls, 1)

    def test_enable_live_updates_starts_inactive_timers(self):
        tab = DashboardTab.__new__(DashboardTab)
        tab._fast_timer = _DummyTimer(active=False)
        tab._slow_timer = _DummyTimer(active=False)
        tab._fast_interval_ms = 2000
        tab._slow_interval_ms = 10000

        tab._set_live_updates_enabled(True)

        self.assertTrue(tab._fast_timer.isActive())
        self.assertTrue(tab._slow_timer.isActive())
        self.assertEqual(tab._fast_timer.started_with, 2000)
        self.assertEqual(tab._slow_timer.started_with, 10000)

    def test_enable_live_updates_does_not_restart_active_timers(self):
        tab = DashboardTab.__new__(DashboardTab)
        tab._fast_timer = _DummyTimer(active=True)
        tab._slow_timer = _DummyTimer(active=True)
        tab._fast_interval_ms = 2000
        tab._slow_interval_ms = 10000

        tab._set_live_updates_enabled(True)

        self.assertIsNone(tab._fast_timer.started_with)
        self.assertIsNone(tab._slow_timer.started_with)


if __name__ == '__main__':
    unittest.main()
