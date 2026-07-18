"""Focused real-Qt integration tests for Phase 6 presentation adapters."""

import os
import unittest
from unittest.mock import MagicMock, patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication

from core.actions.model import ActionCenterItem
from core.navigation import resolve


class TestPhase6UiAdapters(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

        # Legacy UI suites temporarily import these modules with lightweight
        # Qt stubs during collection. Resolve production classes only after
        # those suites have restored the import cache.
        from ui.diagnostics_tab import _WatchtowerSubTab
        from ui.maintenance_tab import MaintenanceTab, _ActionCenterSubTab, _CleanupSubTab
        from ui.storage_tab import StorageTab

        cls.MaintenanceTab = MaintenanceTab
        cls.ActionCenterSubTab = _ActionCenterSubTab
        cls.CleanupSubTab = _CleanupSubTab
        cls.StorageTab = StorageTab
        cls.WatchtowerSubTab = _WatchtowerSubTab

    @patch("ui.maintenance_tab.SystemManager.get_package_manager", return_value="dnf")
    @patch("ui.maintenance_tab.SystemManager.is_atomic", return_value=False)
    def test_updates_owns_advanced_options_and_action_center_is_dedicated(self, _atomic, _manager):
        tab = self.MaintenanceTab()

        labels = [label for label, _factory in tab._sub_tab_factories]
        self.assertEqual(labels[:3], ["Updates", "Action Center", "Cleanup"])
        self.assertNotIn("Smart Updates", labels)
        updates = tab._loaded_tabs[0]
        self.assertFalse(updates.advanced_group.isChecked())

        self.assertTrue(tab.activate_route(resolve("maintenance:smart-updates")))
        self.assertTrue(updates.advanced_group.isChecked())

        tab.deleteLater()

    def test_cleanup_cache_and_trim_only_request_action_center(self):
        tab = self.CleanupSubTab()
        requested = []
        tab.actionCenterRequested.connect(
            lambda action_id, parameters: requested.append((action_id, parameters))
        )
        tab.runner.run_command = MagicMock()

        tab.findChild(type(tab.reclaim_button), "maintReviewDnfClean").click()
        tab.findChild(type(tab.reclaim_button), "maintReviewFstrim").click()

        self.assertEqual(requested, [("dnf-clean-all", {}), ("fstrim-all", {})])
        tab.runner.run_command.assert_not_called()
        tab.deleteLater()

    def test_action_center_loading_manual_state_and_parameter_preselection_are_ui_only(self):
        with patch.object(self.ActionCenterSubTab, "_load_target"):
            tab = self.ActionCenterSubTab()
        tab._set_loading(True)
        self.assertFalse(tab.review_button.isEnabled())
        self.assertFalse(tab.history_button.isEnabled())
        tab._set_loading(False)

        item = ActionCenterItem(
            id="restart-failed-service",
            title="Restart failed service",
            source="catalog:v14",
            description="Review one exact failed unit.",
            risk_level="medium",
            privilege="pkexec",
            state="planned",
        )
        tab._items = [item]
        tab.action_list.addItem(item.title)
        orchestrator = MagicMock()
        tab._orchestrator = orchestrator
        tab._start_operation = MagicMock()

        self.assertTrue(
            tab.preselect_action(
                "restart-failed-service",
                {"service": "broken.service"},
            )
        )
        orchestrator.plan.assert_not_called()

        tab._plan_selected()
        orchestrator.plan.assert_not_called()
        operation = tab._start_operation.call_args.args[0]
        operation()
        orchestrator.plan.assert_called_once_with(
            "restart-failed-service",
            {"service": "broken.service"},
            target="44",
        )

        item.manual_only = True
        tab._show_item(item)
        self.assertIn("Manual-only", tab.presentation_status.text())
        self.assertFalse(tab.review_button.isEnabled())
        tab.deleteLater()

    def test_storage_trim_only_requests_action_center(self):
        with patch("ui.storage_tab.QTimer.singleShot"):
            tab = self.StorageTab()
            requested = []
            tab.actionCenterRequested.connect(
                lambda action_id, parameters: requested.append((action_id, parameters))
            )

            tab._trim_ssd()

            self.assertEqual(requested, [("fstrim-all", {})])
            tab.deleteLater()

    def test_failed_system_service_navigation_carries_exact_parameter(self):
        main = MagicMock()
        main.switch_to_route.return_value = True
        with patch.object(self.WatchtowerSubTab, "init_ui"):
            watchtower = self.WatchtowerSubTab()
        with patch.object(self.WatchtowerSubTab, "window", return_value=main):
            watchtower._review_failed_service("broken.service")

        main.switch_to_route.assert_called_once_with("maintenance:action-center")
        main._preselect_action_center.assert_called_once_with(
            "restart-failed-service",
            {"service": "broken.service"},
        )
        watchtower.deleteLater()


if __name__ == "__main__":
    unittest.main()
