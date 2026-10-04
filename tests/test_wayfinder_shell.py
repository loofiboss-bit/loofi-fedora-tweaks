"""Wayfinder system confirmation and GUI activation contracts."""
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from PyQt6.QtWidgets import QApplication, QMessageBox, QWidget

from ui.main_window_utility import MainWindowUtilityMixin


class TestWayfinderShell(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.parent = QWidget()
        self.addCleanup(self.parent.close)
        self.parent._utility_operation_adapter = None
        self.parent._utility_operation_controller = Mock()
        self.adapter = SimpleNamespace(finished=Mock(), failed=Mock(), cancelled=Mock(), stopped=Mock(), start=Mock(return_value=True))
        self.parent._new_utility_operation_adapter = Mock(return_value=self.adapter)
        self.parent._start_tweak_snapshot = Mock()
        self.page = Mock()
        self.page._rows = {"dnf-parallel": (Mock(), Mock())}
        self.page._rows["dnf-parallel"][1].property.return_value = "3"

    @patch("PyQt6.QtWidgets.QMessageBox.question", return_value=QMessageBox.StandardButton.Cancel)
    def test_system_confirmation_names_dnf_values_and_scope_then_restores_selection(self, question):
        from core.tasks.tweaks import TWEAKS
        tweak = next(t for t in TWEAKS if t.id.startswith("dnf"))
        self.page._rows = {tweak.id: (Mock(), Mock())}
        current, target = tweak.choices[:2]
        self.page._rows[tweak.id][1].property.return_value = current[0]
        self.assertFalse(MainWindowUtilityMixin._start_tweak_change(self.parent, self.page, tweak.id, target[0]))
        text = question.call_args.args[2]
        self.assertIn(tweak.title, text)
        self.assertIn(current[1], text)
        self.assertIn(target[1], text)
        self.assertIn("all users", text)
        self.assertNotIn("power profile", text.casefold())
        self.page.restore_selection.assert_called_once_with(tweak.id)
        self.adapter.start.assert_not_called()

    @patch("core.actions.tweak_operations.activate_verified_tweak")
    def test_gui_keeps_saved_outcome_and_separate_session_warning(self, activate):
        source = SimpleNamespace(success=True, message="Saved")
        activation = SimpleNamespace(saved_verified=True, session_verified=False, message="Saved; session unverified")
        activate.return_value = activation
        self.parent._utility_operation_controller.execute.return_value = source
        self.assertTrue(MainWindowUtilityMixin._start_tweak_change(self.parent, self.page, "kde-edge-tiling", "false"))
        operation = self.adapter.start.call_args.args[0]
        result = operation()
        activate.assert_called_once_with(self.parent._utility_operation_controller, source)
        self.adapter.finished.connect.call_args.args[0](result)
        self.page.set_outcome.assert_called_once_with("kde-edge-tiling", "false", source)
        self.page.set_activation.assert_called_once_with("kde-edge-tiling", activation.message)
        self.page.set_pending.assert_called_once_with("kde-edge-tiling", "false")

    @patch("ui.icon_pack.resolve_icon_path", return_value="/fixture/history.svg")
    @patch("ui.icon_pack.QIcon.fromTheme")
    @patch("ui.icon_pack._tinted_icon")
    def test_explicit_semantic_tint_is_respected_for_header_contrast(self, tinted, themed, _path):
        from ui.icon_pack import get_qicon
        result = get_qicon("history", size=20, tint="#ffff00")
        self.assertIs(result, tinted.return_value)
        themed.assert_not_called()
        tinted.assert_called_once_with("/fixture/history.svg", 20, "#ffff00")

    @patch("ui.tweaks_page.SettingsManager.instance")
    def test_failed_read_clears_pending_choice_and_retains_verified_value(self, settings):
        from core.tasks.tweaks import BY_ID, TweakState
        from ui.tweaks_page import TweaksPage
        settings.return_value.get.return_value = []
        profile = SimpleNamespace(is_fedora=True, desktop=SimpleNamespace(value="gnome"), deployment_backend=SimpleNamespace(value="dnf5"))
        page = TweaksPage(profile)
        self.addCleanup(page.close)
        tweak = BY_ID["gnome-battery"]
        page.set_states((TweakState(tweak, "ready", value="false", choices=tweak.choices),))
        control = page._rows[tweak.id][1]
        control.setCurrentIndex(control.findData("true"))
        page.set_pending(tweak.id, "true")
        page.set_error("Read failed")
        self.assertEqual(control.currentData(), "false")
        self.assertFalse(page._pending)
        self.assertNotIn("Pending", page._rows[tweak.id][0].value_label.text())
