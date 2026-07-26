"""Resolve Phase 3 Specialist Tools and Settings presentation contracts."""

from __future__ import annotations

import os
import sys
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(
    0,
    os.path.join(os.path.dirname(__file__), "..", "loofi-fedora-tweaks"),
)

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QApplication, QCheckBox

from core.navigation import (
    ADVANCED_DESTINATION,
    NavigationContext,
    NavigationDecision,
    NavigationMode,
    NavigationPolicy,
    sections_for_destination,
)
from ui.components.settings import SettingRow
from ui.navigation.destination_host import (
    DestinationHost,
    secondary_routes_for_destination,
)


class TestSpecialistToolsProjection(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        self.context = NavigationContext(mode=NavigationMode.ADVANCED)
        self.host = DestinationHost()
        self.host.set_destination(
            ADVANCED_DESTINATION,
            self.context,
            "development",
        )

    def tearDown(self) -> None:
        self.host.deleteLater()
        self.app.processEvents()

    def test_grouping_preserves_every_policy_visible_section(self) -> None:
        routes = secondary_routes_for_destination(
            ADVANCED_DESTINATION,
            self.context,
        )

        self.assertEqual(
            {route.section_id for route in routes},
            {
                section.id
                for section in sections_for_destination("advanced")
                if NavigationPolicy.evaluate(
                    section.default_route_id,
                    self.context,
                ).decision
                is NavigationDecision.VISIBLE
            },
        )
        self.assertEqual(
            self.host.navigator.section_ids(),
            tuple(route.section_id for route in routes),
        )
        self.assertEqual(
            self.host.navigator.available_groups(),
            (
                "Performance & gaming",
                "Development & local AI",
                "Profiles & extensions",
                "Devices & sharing",
                "Agents & automation",
                "Virtualization",
            ),
        )

    def test_local_filter_changes_only_the_projection(self) -> None:
        original_routes = self.host.route_ids()

        self.host.navigator.filter_input.setText("clipboard")
        self.app.processEvents()

        self.assertEqual(
            self.host.navigator.visible_section_ids(),
            ("loofi_link_clipboard",),
        )
        self.assertEqual(self.host.route_ids(), original_routes)
        self.assertEqual(self.host.navigator.filter_input.accessibleName(), "Filter specialist tools")

    def test_direct_link_clears_filters_and_selects_exact_section(self) -> None:
        self.host.navigator.filter_input.setText("clipboard")
        self.host.set_active_route("virtualization:gpu-passthrough")

        self.assertEqual(self.host.navigator.filter_text(), "")
        self.assertEqual(
            self.host.navigator.active_section_id(),
            "virtualization_gpu",
        )

    def test_rtl_keeps_filter_controls_and_route_labels_available(self) -> None:
        self.host.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
        self.host.show()
        self.app.processEvents()

        self.assertTrue(self.host.navigator.filter_panel.isVisible())
        self.assertGreater(self.host.navigator.selector.count(), 0)
        self.assertTrue(
            all(
                self.host.navigator.selector.itemText(index)
                for index in range(self.host.navigator.selector.count())
            )
        )


class TestSettingRows(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    @staticmethod
    def _manager(*, save_result: bool = True) -> MagicMock:
        manager = MagicMock()
        values = {
            "theme": "dark",
            "follow_system_theme": True,
            "start_minimized": False,
            "show_notifications": True,
            "confirm_dangerous_actions": True,
            "restore_last_tab": False,
            "log_level": "INFO",
            "check_updates_on_start": True,
        }
        manager.get.side_effect = lambda key, default=None: values.get(key, default)
        manager.save.return_value = save_result
        return manager

    def test_row_feedback_never_relies_on_color_alone(self) -> None:
        row = SettingRow("Notifications", "Desktop feedback", QCheckBox())

        row.set_feedback("The change is stored.", kind="saved")
        self.assertTrue(row.feedback_label.text().startswith("Saved —"))
        self.assertTrue(row.feedback_label.accessibleDescription())

        row.set_feedback("The file is read-only.", kind="error")
        self.assertTrue(row.feedback_label.text().startswith("Error —"))
        row.deleteLater()

    @patch("ui.settings_tab.SettingsManager.instance")
    def test_theme_dependency_is_visible_and_named(self, mock_instance) -> None:
        from ui.settings_tab import SettingsTab

        mock_instance.return_value = self._manager()
        tab = SettingsTab()
        row = tab._setting_rows["theme"]

        self.assertFalse(tab.theme_combo.isEnabled())
        self.assertTrue(row.feedback_label.text().startswith("Unavailable —"))
        self.assertTrue(row.accessibleName())
        tab.deleteLater()

    @patch("ui.settings_tab.SettingsManager.instance")
    def test_success_and_failure_are_reported_beside_the_setting(
        self,
        mock_instance,
    ) -> None:
        from ui.settings_tab import SettingsTab

        manager = self._manager()
        mock_instance.return_value = manager
        tab = SettingsTab()

        tab._toggle_setting("show_notifications", False)
        self.assertTrue(
            tab._setting_rows["show_notifications"].feedback_label.text().startswith("Saved —")
        )

        manager.save.return_value = False
        tab._toggle_setting("start_minimized", True)
        self.assertTrue(
            tab._setting_rows["start_minimized"].feedback_label.text().startswith("Error —")
        )
        tab.deleteLater()

    @patch("ui.settings_tab.SettingsManager.instance")
    def test_settings_context_keeps_specialist_dependency_feedback(
        self,
        mock_instance,
    ) -> None:
        from ui.settings_tab import SettingsTab

        mock_instance.return_value = self._manager()
        tab = SettingsTab()
        tab.set_context(
            {
                "main_window": SimpleNamespace(
                    _navigation_context=SimpleNamespace(
                        installed_components=frozenset({"core"})
                    )
                )
            }
        )

        self.assertIn("does not include specialist tools", tab._component_status.text())
        tab.deleteLater()

    @patch("ui.settings_tab.SettingsManager.instance")
    def test_reset_failure_is_reported_for_every_affected_row(
        self,
        mock_instance,
    ) -> None:
        from ui.settings_tab import SettingsTab

        manager = self._manager()
        manager.reset_group.return_value = False
        mock_instance.return_value = manager
        tab = SettingsTab()

        tab._reset_behavior()

        for key in (
            "start_minimized",
            "show_notifications",
            "confirm_dangerous_actions",
            "restore_last_tab",
        ):
            self.assertTrue(
                tab._setting_rows[key].feedback_label.text().startswith("Error —")
            )
        tab.deleteLater()


if __name__ == "__main__":
    unittest.main()
