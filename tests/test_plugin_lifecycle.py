"""Tests for Phase 2 route, timer, and startup-service lifecycle contracts."""

import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from ui.agents_tab import AgentsTab
from ui.hardware_tab import HardwareTab
from ui.main_window import MainWindow
from ui.monitor_tab import MonitorTab
from ui.network_tab import NetworkTab
from ui.performance_tab import PerformanceTab
from ui.software_tab import SoftwareTab


class TestTimerLifecycle(unittest.TestCase):
    @patch("ui.hardware_tab.QTimer.singleShot")
    def test_hardware_timer_tracks_route_visibility(self, single_shot):
        tab = SimpleNamespace(refresh_timer=MagicMock(), refresh_status=MagicMock())
        tab.refresh_timer.isActive.side_effect = [False, True]
        HardwareTab.on_activate(tab)
        HardwareTab.on_deactivate(tab)
        tab.refresh_timer.start.assert_called_once_with(5000)
        single_shot.assert_called_once_with(0, tab.refresh_status)
        tab.refresh_timer.stop.assert_called_once_with()

    @patch("ui.performance_tab.QTimer.singleShot")
    def test_performance_timer_tracks_route_visibility(self, single_shot):
        tab = SimpleNamespace(_timer=MagicMock(), _detect_workload=MagicMock())
        tab._timer.isActive.side_effect = [False, True]
        PerformanceTab.on_activate(tab)
        PerformanceTab.on_deactivate(tab)
        tab._timer.start.assert_called_once_with(30_000)
        single_shot.assert_called_once_with(0, tab._detect_workload)
        tab._timer.stop.assert_called_once_with()

    @patch("ui.agents_tab.QTimer.singleShot")
    def test_agents_timer_tracks_route_visibility(self, single_shot):
        tab = SimpleNamespace(_refresh_timer=MagicMock(), _refresh_all=MagicMock())
        tab._refresh_timer.isActive.side_effect = [False, True]
        AgentsTab.on_activate(tab)
        AgentsTab.on_deactivate(tab)
        tab._refresh_timer.start.assert_called_once()
        single_shot.assert_called_once_with(0, tab._refresh_all)
        tab._refresh_timer.stop.assert_called_once_with()

    def test_monitor_runs_only_the_visible_subtab_timer(self):
        tab = SimpleNamespace(
            _route_active=True,
            _performance_tab=MagicMock(),
            _processes_tab=MagicMock(),
        )
        MonitorTab._sync_timer_lifecycle(tab, 1)
        tab._performance_tab.set_active.assert_called_once_with(False)
        tab._processes_tab.set_active.assert_called_once_with(True)

    def test_network_monitor_stops_on_deactivation(self):
        tab = SimpleNamespace(_route_active=True, _monitor_timer=MagicMock())
        NetworkTab.on_deactivate(tab)
        self.assertFalse(tab._route_active)
        tab._monitor_timer.stop.assert_called_once_with()

    def test_software_catalog_waits_for_applications_subtab(self):
        tab = SimpleNamespace(
            _route_active=True,
            tabs=MagicMock(),
            _applications_tab=MagicMock(),
        )
        tab.tabs.currentIndex.return_value = 1

        SoftwareTab._activate_current_subtab(tab)
        tab._applications_tab.on_activate.assert_not_called()

        tab.tabs.currentIndex.return_value = 0
        SoftwareTab._activate_current_subtab(tab)
        tab._applications_tab.on_activate.assert_called_once_with()


class TestShellLifecycle(unittest.TestCase):
    @patch("ui.main_window.PluginRegistry.instance")
    def test_route_change_deactivates_previous_and_activates_next_once(self, instance):
        previous = MagicMock()
        current = MagicMock()
        registry = MagicMock()
        registry.get.side_effect = lambda plugin_id: {
            "previous": previous,
            "current": current,
        }.get(plugin_id)
        instance.return_value = registry
        window = SimpleNamespace(_active_plugin_id="previous", _sidebar_index={})
        MainWindow._set_active_plugin(window, "current")
        MainWindow._set_active_plugin(window, "current")
        previous.on_deactivate.assert_called_once_with()
        current.on_activate.assert_called_once_with()
        self.assertEqual(window._active_plugin_id, "current")

    def test_background_services_are_disabled_by_default(self):
        window = SimpleNamespace(
            _background_services_enabled=MagicMock(return_value=False),
            setup_tray=MagicMock(),
            _start_pulse_listener=MagicMock(),
        )
        MainWindow._initialize_background_services(window)
        window.setup_tray.assert_not_called()
        window._start_pulse_listener.assert_not_called()

    def test_background_setting_enables_tray_and_pulse(self):
        window = SimpleNamespace(
            _background_services_enabled=MagicMock(return_value=True),
            setup_tray=MagicMock(),
            _start_pulse_listener=MagicMock(),
        )
        MainWindow._initialize_background_services(window)
        window.setup_tray.assert_called_once_with()
        window._start_pulse_listener.assert_called_once_with()

    @patch("ui.main_window.QTimer.singleShot")
    def test_post_render_services_are_scheduled_once(self, single_shot):
        window = SimpleNamespace(
            _post_render_services_scheduled=False,
            _initialize_post_render_services=MagicMock(),
        )
        MainWindow._schedule_post_render_services(window)
        MainWindow._schedule_post_render_services(window)
        single_shot.assert_called_once_with(250, window._initialize_post_render_services)


if __name__ == "__main__":
    unittest.main()
