"""Precise contextual links remain navigation rather than operation authority."""
import unittest
from unittest.mock import Mock, MagicMock

from ui.main_window import MainWindow
from core.tasks.next_steps import NextStep, NextStepContext


class RoutineNavigationTests(unittest.TestCase):
    def test_failed_flatpak_opens_exact_diagnosis_without_switch_fallback(self):
        owner = MagicMock()
        MainWindow._open_route_request(owner, "health", {"update_source": "flatpak", "run_id": "chosen"})
        owner._open_update_diagnosis.assert_called_once_with("flatpak", "chosen")
        owner.switch_to_route.assert_not_called()

    def test_generic_failure_opens_exact_activity(self):
        owner = MagicMock()
        MainWindow._open_route_request(owner, "changes", {"run_id": "chosen"})
        owner._open_action_center_run.assert_called_once_with("chosen")
        owner.switch_to_route.assert_not_called()

    def test_storage_link_selects_symptom_without_starting(self):
        owner = MagicMock()
        MainWindow._open_route_request(owner, "health", {"symptom": "storage_full"})
        page = owner._real_widget_for_entry.return_value
        page.focus_task.assert_called_once_with("storage_full")
        page.start_session.assert_not_called()

    def test_pending_link_selects_exact_update_source(self):
        owner = MagicMock()
        MainWindow._open_route_request(owner, "maintenance:updates", {"update_source": "system", "run_id": "chosen"})
        owner._open_update_source_context.assert_called_once_with("system", "chosen")

    def test_invalid_context_never_becomes_action(self):
        owner = MagicMock()
        MainWindow._open_route_request(owner, "health", {"run_id": 42})
        owner.switch_to_route.assert_not_called()
        owner._open_action_center_request.assert_not_called()


class RoutineContextPresentationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from PyQt6.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication([])

    def test_context_changes_replace_button_target(self):
        from ui.overview_page import OverviewPage
        page = OverviewPage()
        self.addCleanup(page.close)
        callback = Mock()
        page.contextRouteRequested.connect(callback)
        for run in ("first", "second"):
            page._show_next_steps((NextStep("failed", "Failed", "Reason", "changes", "Open", context=NextStepContext(run_id=run)),))
        page._next_step_rows[0].layout().itemAt(2).widget().click()
        callback.assert_called_once_with("changes", {"run_id": "second"})

    def test_preselected_update_offers_exact_record_without_check(self):
        from ui.update_workflow import UpdateWorkflowPage
        page = UpdateWorkflowPage(service=Mock())
        self.addCleanup(page.cleanup)
        self.addCleanup(page.close)
        callback = Mock()
        check = Mock()
        page.recordRequested.connect(callback)
        page.sourceActionRequested.connect(check)
        self.assertTrue(page.preselect_source("flatpak", "saved-run"))
        check.assert_not_called()
        page.record_button.click()
        callback.assert_called_once_with("saved-run")
