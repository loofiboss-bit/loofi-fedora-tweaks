"""Regression for the system setting approval discovered by real VM tests."""

import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from PyQt6.QtWidgets import QApplication, QDialog, QWidget
from ui.main_window_utility import MainWindowUtilityMixin


class TestSystemTweakConfirmation(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.parent = QWidget()
        self.controller = Mock()
        self.parent._utility_operation_controller = self.controller
        self.parent._utility_operation_adapter = None
        signals = ("finished", "failed", "cancelled", "stopped")
        self.adapter = SimpleNamespace(**{name: SimpleNamespace(connect=Mock()) for name in signals})
        self.adapter.start = Mock(side_effect=lambda operation: operation())
        self.parent._new_utility_operation_adapter = Mock(return_value=self.adapter)
        self.parent._start_tweak_inspection = Mock()
        control = Mock()
        control.property.return_value = "3"
        self.page = SimpleNamespace(_rows={"dnf-parallel-downloads": (Mock(), control)},
                                    set_error=Mock(), set_busy=Mock(), set_pending=Mock(),
                                    restore_selection=Mock(), set_outcome=Mock(), set_activation=Mock(),
                                    set_restore_error=Mock())

    def tearDown(self):
        self.parent.close()

    @patch("core.actions.tweak_operations.activate_verified_tweak")
    @patch("core.actions.tweak_operations.cursor_notification_parameters", return_value=None)
    @patch("ui.tweak_review.ReviewedActionDialog")
    def test_change_discloses_scope_and_recovery_and_forwards_explicit_acceptance(self, dialog_class, _cursor, _activation):
        dialog_class.return_value.exec.return_value = QDialog.DialogCode.Accepted
        dialog_class.return_value.accepts_no_rollback = True
        MainWindowUtilityMixin._start_tweak_change(self.parent, self.page, "dnf-parallel-downloads", "5")
        self.assertIn("this computer, all users", dialog_class.call_args.args[2])
        self.assertIn("Automatic rollback is unavailable", dialog_class.call_args.args[3])
        self.assertTrue(dialog_class.call_args.kwargs["require_no_rollback_acceptance"])
        self.controller.execute.assert_called_once_with("set-dnf-parallel-downloads", {"value": "5"},
                                                        confirmed=True, accept_no_rollback=True)

    @patch("ui.tweak_review.ReviewedActionDialog")
    def test_cancel_does_not_execute_a_system_change(self, dialog_class):
        dialog_class.return_value.exec.return_value = QDialog.DialogCode.Rejected
        self.assertFalse(MainWindowUtilityMixin._start_tweak_change(self.parent, self.page, "dnf-parallel-downloads", "5"))
        self.controller.execute.assert_not_called()
        self.adapter.start.assert_not_called()

    @patch("core.actions.tweak_operations.activate_verified_tweak")
    def test_source_bound_restoration_forwards_prior_system_confirmation(self, _activation):
        ticket = SimpleNamespace(plan=SimpleNamespace(policy_decision=SimpleNamespace(facts={"requested": "3"})))
        self.controller.confirm.return_value = SimpleNamespace(status="blocked")
        MainWindowUtilityMixin._run_tweak_restore(self.parent, self.page, "dnf-parallel-downloads", ticket, accept_no_rollback=True)
        self.controller.confirm.assert_called_once_with(ticket, confirmed=True, accept_no_rollback=True)
