"""Control-center integration without host probes or user-state writes."""
from dataclasses import asdict
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from PyQt6.QtCore import Qt
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QApplication

from core.platform.profile import DeploymentBackend, DesktopEnvironment, PlatformProfile, SessionType
from core.plugins.registry import PluginRegistry
from ui.main_window import MainWindow
from ui.overview_page import OverviewPage
from utils.settings import AppSettings


PROFILE = PlatformProfile(
    os_id="fedora", fedora_version=44, variant_id="kde", variant_name="Fedora KDE",
    architecture="x86_64", desktop=DesktopEnvironment.KDE, session_type=SessionType.WAYLAND,
    deployment_backend=DeploymentBackend.DNF5, is_atomic=False, reboot_pending=False,
    package_manager_command="dnf5",
)


class TestControlCenterShell(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def build_window(self, **values):
        PluginRegistry.reset()
        prefs = {**asdict(AppSettings()), **values}
        manager = Mock()
        manager.get.side_effect = lambda key, default=None: prefs.get(key, default)
        manager.set.side_effect = lambda key, value: prefs.__setitem__(key, value)
        manager.save.return_value = True
        controller = Mock(latest_snapshot=None, busy=False)
        # One lifetime for each patch: lazy visits use the same mocks, and LIFO
        # cleanup restores the real methods rather than an outer decorator mock.
        patchers = (
            patch("utils.settings.SettingsManager.instance", return_value=manager),
            patch("ui.dashboard_controller.DashboardController", return_value=controller),
            patch("ui.main_window.SystemManager.get_platform_profile", return_value=PROFILE),
            patch("ui.main_window.MainWindow._initialize_background_services"),
            patch("ui.main_window.MainWindow._check_first_run"),
        )
        for patcher in patchers:
            patcher.start()
            self.addCleanup(patcher.stop)
        window = MainWindow()
        self.addCleanup(PluginRegistry.reset)
        self.addCleanup(window.close)
        self.addCleanup(window.cleanup)
        return window, prefs, manager, controller

    def test_overview_is_default_but_tweak_workflow_remains_lazy(self):
        window, prefs, _, _ = self.build_window()
        self.assertEqual(window._active_route_id, "overview")
        self.assertEqual(window.sidebar.destination_ids(), ("overview", "tune", "install", "update", "fix", "activity"))
        self.assertIsInstance(window._real_widget_for_entry(window._sidebar_index["overview"]), OverviewPage)
        self.assertIsNone(window._sidebar_index["utility_tune"].page_widget.get_real_widget())
        self.assertEqual(prefs["last_route_id"], "overview")

    def test_saved_route_restoration_and_invalid_route_fallback(self):
        window, _, _, _ = self.build_window(restore_last_tab=True, last_route_id="settings:behavior")
        self.assertEqual(window._active_route_id, "settings:behavior")
        window.cleanup()
        window.close()
        window, _, _, _ = self.build_window(restore_last_tab=True, last_route_id="missing")
        self.assertEqual(window._active_route_id, "overview")

    def test_documented_home_alias_still_opens_tweaks(self):
        window, _, _, _ = self.build_window()
        self.assertTrue(window.switch_to_route("home"))
        self.assertEqual(window._active_route_id, "utility:tune")

    def test_saved_atlas_links_use_live_tweak_workflow(self):
        window, _, _, _ = self.build_window(restore_last_tab=True, last_route_id="atlas_dashboard")
        self.assertEqual(window._active_route_id, "utility:tune")
        self.assertEqual(window._active_plugin_id, "utility_tune")

    def test_action_search_opens_visible_review_without_execution(self):
        window, _, _, _ = self.build_window()
        result = SimpleNamespace(route_id="maintenance:action-center", action_id="dnf-clean-all", task_id=None)
        with patch.object(window, "_preselect_action_center", return_value=True) as preselect:
            self.assertTrue(window._activate_global_search_result(result))
        self.assertEqual(window._active_route_id, "maintenance:action-center")
        self.assertEqual(window._active_plugin_id, "changes")
        preselect.assert_called_once_with("dnf-clean-all")
        self.assertIsNone(window._utility_operation_adapter)

    def test_read_only_results_do_not_claim_recorded_changes(self):
        window, _, _, _ = self.build_window()
        window._record_global_operation_result((), phase="inspection")
        self.assertIn("No change was started", window._status_label.text())
        window._record_global_operation_result(SimpleNamespace(plan=object()), phase="review")
        self.assertIn("Review ready", window._status_label.text())
        self.assertNotIn("Activity", window._status_label.text())

    def test_tools_keyboard_disclosure_persists_and_failed_save_restores(self):
        window, prefs, manager, _ = self.build_window()
        item = window.sidebar._tools_item
        window.sidebar.setCurrentItem(item)
        QTest.keyClick(window.sidebar, Qt.Key.Key_Space)
        self.assertTrue(item.isExpanded())
        self.assertTrue(prefs["show_advanced_tools"])
        manager.save.return_value = False
        QTest.keyClick(window.sidebar, Qt.Key.Key_Space)
        self.assertTrue(window.sidebar._tools_item.isExpanded())
        self.assertTrue(prefs["show_advanced_tools"])
        self.assertIn("Could not save", window._status_label.text())

    def test_system_subnavigation_is_limited_to_its_tool_routes(self):
        window, _, _, _ = self.build_window()
        self.assertTrue(window.switch_to_route("system_info"))
        self.assertEqual(window._active_destination_id, "system")
        self.assertTrue(window.sidebar._tools_item.isExpanded())
        routes = window.destination_host.route_ids()
        self.assertIn("monitor", routes)
        self.assertIn("system-monitor:processes", routes)
        self.assertNotIn("snapshots", routes)
        self.assertNotIn("health", routes)

    def test_global_result_is_not_relabelled_verified_after_page_change(self):
        window, _, _, _ = self.build_window()
        adapter = window._new_utility_operation_adapter()
        self.assertTrue(window.switch_to_route("settings"))
        adapter.finished.emit(SimpleNamespace(success=False, message="Readback mismatch"))
        self.assertEqual(window._status_label.text(), "Readback mismatch")
        self.assertNotIn("Verified", window._status_label.text())
        window._utility_operation_adapter_stopped(adapter)

    def test_failed_last_route_save_keeps_previous_preference(self):
        window, prefs, manager, _ = self.build_window()
        manager.save.return_value = False
        self.assertTrue(window.switch_to_route("settings"))
        self.assertEqual(prefs["last_route_id"], "overview")
        self.assertIn("Could not save", window._status_label.text())
