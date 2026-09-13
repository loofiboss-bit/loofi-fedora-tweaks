"""Saved-run follow-up navigation and explicit verification regressions."""

import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock

from core.actions.orchestrator import ActionRunNotFoundError
from ui.maintenance_action_center import _ActionCenterSubTab
from ui.main_window import MainWindow


class TestEverydayFollowup(unittest.TestCase):
    def test_saved_run_selection_never_executes_or_verifies(self):
        run = SimpleNamespace(run_id="saved-run", state="awaiting_reboot")
        tab = MagicMock()
        tab._orchestrator_instance.return_value.get_run.return_value = run
        tab._visible_records = [("run", run)]

        self.assertTrue(_ActionCenterSubTab.preselect_run(tab, "saved-run"))

        self.assertIs(tab._current_run, run)
        tab._show_run.assert_called_once_with(run)
        orchestrator = tab._orchestrator_instance.return_value
        orchestrator.verify.assert_not_called()
        orchestrator.plan.assert_not_called()
        orchestrator.prepare_run.assert_not_called()
        tab.runner.run_command.assert_not_called()

    def test_missing_saved_run_is_reported_without_creating_replacement(self):
        tab = MagicMock()
        tab._orchestrator_instance.return_value.get_run.side_effect = ActionRunNotFoundError("missing")
        self.assertFalse(_ActionCenterSubTab.preselect_run(tab, "missing"))
        tab.presentation_banner.set_result.assert_called_once()
        tab._orchestrator_instance.return_value.plan.assert_not_called()

    def test_navigation_passes_exact_run_id_to_existing_route(self):
        window = MagicMock()
        window.switch_to_route.return_value = True
        MainWindow._open_action_center_run(window, "saved-run")
        window.switch_to_route.assert_called_once_with("maintenance:action-center")
        window._real_widget_for_entry.return_value.preselect_run.assert_called_once_with("saved-run")

    def test_duplicate_verification_click_does_not_dispatch(self):
        tab = MagicMock()
        tab._operation_thread = object()
        _ActionCenterSubTab._verify_current_run(tab)
        tab._start_operation.assert_not_called()

    def test_check_result_dispatches_existing_run_once(self):
        tab = MagicMock()
        tab._operation_thread = None
        tab._current_run = SimpleNamespace(run_id="saved-run")
        _ActionCenterSubTab._verify_current_run(tab)
        operation = tab._start_operation.call_args.args[0]
        operation()
        tab._orchestrator_instance.return_value.verify.assert_called_once_with("saved-run")
        tab._orchestrator_instance.return_value.prepare_run.assert_not_called()

    def test_late_catalog_result_preserves_selected_saved_run(self):
        tab = MagicMock()
        tab._current_run = SimpleNamespace(run_id="saved-run")
        _ActionCenterSubTab._accept_loaded_items(tab, [])
        tab.preselect_run.assert_called_once_with("saved-run")
        tab._select_requested_action.assert_not_called()

    def test_failed_check_restores_saved_run_next_step(self):
        tab = MagicMock()
        tab._current_run = SimpleNamespace(run_id="saved-run", state="awaiting_reboot")
        _ActionCenterSubTab._operation_failed(tab, "Check unavailable")
        tab._show_run.assert_called_once_with(tab._current_run)
        self.assertEqual(tab.presentation_banner.set_result.call_args.args[0], "warning")
        tab._orchestrator_instance.assert_not_called()
