"""Integration coverage for the Phase 3 MainWindow destination shell."""

import os
import sys
import unittest
from unittest.mock import MagicMock, patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(
    0,
    os.path.join(os.path.dirname(__file__), "..", "loofi-fedora-tweaks"),
)

from PyQt6.QtWidgets import QApplication, QWidget

from core.navigation import (
    DirectLinkBehavior,
    NavigationDecision,
    NavigationMode,
    NavigationPolicy,
    all_routes,
)
from core.plugins.registry import PluginRegistry
from ui.main_window import MainWindow


class _RouteWidget(QWidget):
    """Mutation-free route target used to observe shell activation only."""

    def __init__(self, plugin_id: str) -> None:
        super().__init__()
        self.plugin_id = plugin_id
        self.activated_routes: list[str] = []

    def activate_route(self, route) -> bool:
        self.activated_routes.append(route.id)
        return True


class TestPhase3MainWindowShell(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def tearDown(self):
        window = getattr(self, "window", None)
        if window is not None:
            window.deleteLater()
        PluginRegistry.reset()

    @patch("ui.main_window.MainWindow._check_first_run")
    @patch("ui.main_window.MainWindow._initialize_background_services")
    @patch("ui.main_window.SystemManager.is_atomic", return_value=False)
    @patch("ui.main_window.FavoritesManager.get_favorites", return_value=[])
    @patch("utils.navigation_mode.NavigationModeManager.get_mode")
    def _build_window(
        self,
        mock_mode,
        mock_favorites,
        mock_atomic,
        mock_background,
        mock_first_run,
        *,
        mode=NavigationMode.STANDARD,
    ) -> MainWindow:
        del mock_favorites, mock_atomic, mock_background, mock_first_run
        PluginRegistry.reset()
        mock_mode.return_value = mode
        window = MainWindow()
        route_widgets: dict[str, _RouteWidget] = {}

        def load_widget(plugin_id: str, context=None):
            del context
            return route_widgets.setdefault(plugin_id, _RouteWidget(plugin_id))

        window._plugin_loader.load_builtin_widget = MagicMock(
            side_effect=load_widget
        )
        window._phase3_route_widgets = route_widgets
        window.show()
        self.app.processEvents()
        self.window = window
        return window

    def test_standard_shell_is_flat_and_has_no_duplicate_chrome(self):
        window = self._build_window()

        self.assertEqual(window.sidebar.topLevelItemCount(), 6)
        self.assertEqual(
            window.sidebar.destination_ids(),
            (
                "home",
                "software_updates",
                "system",
                "network_security",
                "desktop",
                "settings",
            ),
        )
        self.assertTrue(
            all(
                window.sidebar.topLevelItem(index).childCount() == 0
                for index in range(window.sidebar.topLevelItemCount())
            )
        )
        self.assertFalse(hasattr(window, "sidebar_footer"))
        object_names = {
            widget.objectName() for widget in window.findChildren(QWidget)
        }
        self.assertNotIn("statusHints", object_names)
        self.assertNotIn("statusVersion", object_names)
        self.assertFalse(window._status_frame.isVisible())

    def test_advanced_mode_adds_exactly_one_destination(self):
        window = self._build_window(mode=NavigationMode.ADVANCED)

        self.assertEqual(window.sidebar.topLevelItemCount(), 7)
        self.assertEqual(window.sidebar.destination_ids()[-1], "advanced")

    def test_mode_refresh_preserves_lazy_pages_and_toggles_six_to_seven(self):
        window = self._build_window(mode=NavigationMode.STANDARD)
        pages_before = {
            plugin_id: entry.page_widget
            for plugin_id, entry in window._sidebar_index.items()
        }
        load_calls_before = window._plugin_loader.load_builtin_widget.call_count

        window._rebuild_sidebar_for_navigation_mode(NavigationMode.ADVANCED)
        self.assertEqual(window.sidebar.topLevelItemCount(), 7)
        self.assertEqual(
            pages_before,
            {plugin_id: entry.page_widget for plugin_id, entry in window._sidebar_index.items()},
        )
        self.assertEqual(window._plugin_loader.load_builtin_widget.call_count, load_calls_before)

        window._rebuild_sidebar_for_navigation_mode(NavigationMode.STANDARD)
        self.assertEqual(window.sidebar.topLevelItemCount(), 6)
        self.assertTrue(
            all(
                window.sidebar.topLevelItem(index).childCount() == 0
                for index in range(window.sidebar.topLevelItemCount())
            )
        )

    def test_action_center_navigation_only_activates_its_stable_route(self):
        window = self._build_window()

        opened = window.switch_to_route("maintenance:action-center")

        self.assertTrue(opened)
        self.assertEqual(window._active_route_id, "maintenance:action-center")
        self.assertEqual(window._active_destination_id, "software_updates")
        maintenance = window._phase3_route_widgets["maintenance"]
        self.assertEqual(
            maintenance.activated_routes,
            ["maintenance:action-center"],
        )
        self.assertFalse(hasattr(maintenance, "plan"))
        self.assertFalse(hasattr(maintenance, "apply"))
        self.assertFalse(hasattr(maintenance, "verify"))

    def test_standard_deep_link_to_advanced_route_shows_gate_without_loading(self):
        window = self._build_window()

        opened = window.switch_to_route("development")

        self.assertFalse(opened)
        self.assertNotIn("development", window._phase3_route_widgets)
        self.assertTrue(window.destination_host.explanation.isVisible())
        self.assertIn("Advanced", window.destination_host.explanation.text())

    def test_route_history_preserves_destination_and_secondary_selection(self):
        window = self._build_window()
        self.assertTrue(window.switch_to_route("system_info"))
        self.assertTrue(window.switch_to_route("network:dns"))

        self.assertTrue(window.navigate_back())

        self.assertEqual(window._active_route_id, "system_info")
        self.assertEqual(window.sidebar.current_destination_id(), "system")

    def test_collapse_preserves_destination_selection_and_tooltips(self):
        window = self._build_window()
        window.switch_to_route("network")

        window._set_sidebar_collapsed(True)

        self.assertEqual(
            window.sidebar.current_destination_id(),
            "network_security",
        )
        for index in range(window.sidebar.topLevelItemCount()):
            item = window.sidebar.topLevelItem(index)
            self.assertEqual(item.text(0), "")
            self.assertTrue(item.toolTip(0))

    def test_narrow_and_normal_width_apply_responsive_sidebar_state(self):
        window = self._build_window()
        window.resize(860, 600)
        self.app.processEvents()
        self.assertTrue(window._sidebar_collapsed)

        window.resize(1280, 720)
        self.app.processEvents()
        self.assertFalse(window._sidebar_collapsed)

    def test_activity_chrome_is_conditional(self):
        window = self._build_window()
        self.assertFalse(window._status_frame.isVisible())

        window.set_status("Running system check…")
        self.assertTrue(window._status_frame.isVisible())

        window.set_status("")
        self.assertFalse(window._status_frame.isVisible())

        window.show_undo_button("Setting changed")
        self.assertTrue(window._status_frame.isVisible())

    def test_all_v14_routes_open_or_show_the_policy_gate(self):
        window = self._build_window()

        opened = 0
        gated = 0
        for route in all_routes():
            result = NavigationPolicy.evaluate(route.id, window._navigation_context)
            did_open = window.switch_to_route(route.id)
            if result.decision is NavigationDecision.VISIBLE:
                self.assertTrue(did_open, route.id)
                opened += 1
            elif (
                result.direct_link_behavior is DirectLinkBehavior.REDIRECT
                and result.redirect_route_id
            ):
                self.assertTrue(did_open, route.id)
                opened += 1
            else:
                self.assertFalse(did_open, route.id)
                self.assertTrue(window.destination_host.explanation.isVisible())
                gated += 1

        self.assertEqual(opened + gated, 80)
        self.assertGreater(opened, 0)
        self.assertGreater(gated, 0)


if __name__ == "__main__":
    unittest.main()
