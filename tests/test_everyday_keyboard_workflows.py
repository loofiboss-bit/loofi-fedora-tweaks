"""Primary everyday input flows using Qt keyboard events, with inert services.

Offscreen focus/input regressions complement real desktop accessibility tests.
They do not qualify physical screen readers or every supported environment.
"""
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from PyQt6.QtCore import QTimer, Qt
from PyQt6.QtTest import QSignalSpy, QTest
from PyQt6.QtWidgets import QApplication, QPushButton, QVBoxLayout, QWidget

from core.catalog_models import FedoraVariant
from core.tasks.applications import ApplicationContext
from core.tasks.guides import GuideProgressSnapshot
from ui.confirm_dialog import ReviewedActionDialog
from ui.install_workflow import InstallWorkflowPage
from ui.overview_page import OverviewPage
from ui.tweaks_page import TweaksPage


class EverydayKeyboardWorkflows(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def show(self, widget):
        widget.resize(1000, 1000)
        widget.show()
        widget.activateWindow()
        self.app.processEvents()
        self.addCleanup(self.dispose, widget)
        return widget

    def dispose(self, widget):
        cleanup = getattr(widget, "cleanup", None)
        if callable(cleanup):
            cleanup()
        widget.close()
        widget.deleteLater()
        self.app.processEvents()

    def focus(self, widget):
        widget.setFocus(Qt.FocusReason.TabFocusReason)
        self.app.processEvents()
        self.assertIs(self.app.focusWidget(), widget)

    def apps_page(self):
        return self.show(InstallWorkflowPage(context=ApplicationContext(
            FedoraVariant.TRADITIONAL, frozenset({"fedora", "dnf5"}), online=True)))

    def test_apps_typing_filters_rows_without_losing_search_focus(self):
        page = self.apps_page()
        firefox_item = page._rows["firefox"][2]
        self.focus(page.search_input)
        QTest.keyClicks(page.search_input, "firefox")
        self.app.processEvents()
        self.assertIs(self.app.focusWidget(), page.search_input)
        self.assertFalse(firefox_item.isHidden())
        self.assertTrue(any(item.isHidden() for _record, _eligibility, item in page._rows.values()))
        QTest.keyClick(page.search_input, Qt.Key.Key_A, Qt.KeyboardModifier.ControlModifier)
        QTest.keyClick(page.search_input, Qt.Key.Key_Backspace)
        self.app.processEvents()
        self.assertEqual(page.search_input.text(), "")
        self.assertIs(page._rows["firefox"][2], firefox_item)
        self.assertIs(self.app.focusWidget(), page.search_input)

    def test_apps_view_can_be_selected_and_reversed_with_keyboard(self):
        page = self.apps_page()
        self.focus(page.view_filter)
        QTest.keyClick(page.view_filter, Qt.Key.Key_Down)
        self.app.processEvents()
        self.assertEqual(page.view_filter.currentData(), "installed")
        self.assertTrue(page.installed_card.isVisible())
        self.assertIs(self.app.focusWidget(), page.view_filter)
        QTest.keyClick(page.view_filter, Qt.Key.Key_Up)
        self.app.processEvents()
        self.assertEqual(page.view_filter.currentData(), "catalog")
        self.assertTrue(page.application_list.isVisible())

    def test_apps_space_selection_and_review_request_do_not_execute_install(self):
        page = self.apps_page()
        requested = QSignalSpy(page.bundleReviewRequested)
        checkbox = page._row_checks["firefox"]
        self.assertTrue(checkbox.isEnabled())
        self.focus(checkbox)
        QTest.keyClick(checkbox, Qt.Key.Key_Space)
        self.app.processEvents()
        self.assertTrue(checkbox.isChecked())
        self.assertTrue(page.review_button.isEnabled())
        self.assertEqual(len(requested), 0)
        self.focus(page.review_button)
        QTest.keyClick(page.review_button, Qt.Key.Key_Space)
        self.app.processEvents()
        self.assertEqual(len(requested), 1)
        self.assertEqual(requested[0][0].count, 1)
        self.assertIn("Review ready", page.state_notice.title_label.text())

    @patch("ui.guide_panel.GuideProgressStore")
    @patch("utils.settings.SettingsManager.instance")
    def test_intro_dismiss_and_reopen_are_keyboard_operable(self, settings, store):
        store.return_value.read.return_value = GuideProgressSnapshot("", "", {}, 0)
        settings.return_value.get.return_value = False
        settings.return_value.save.return_value = True
        page = self.show(OverviewPage())
        page._load_intro_preference()
        controller = Mock()
        controller.latest_snapshot = None
        page.set_controller(controller)
        navigated = QSignalSpy(page.taskRequested)
        self.assertTrue(page.intro_card.isVisible())
        self.focus(page.dismiss_intro_button)
        QTest.keyClick(page.dismiss_intro_button, Qt.Key.Key_Space)
        self.app.processEvents()
        self.assertFalse(page.intro_card.isVisible())
        self.assertTrue(page.show_intro_button.isVisible())
        settings.return_value.set.assert_called_with("overview_intro_dismissed", True)
        self.assertTrue(page.show_intro_button.accessibleName())
        self.focus(page.show_intro_button)
        QTest.keyClick(page.show_intro_button, Qt.Key.Key_Space)
        self.app.processEvents()
        self.assertTrue(page.intro_card.isVisible())
        settings.return_value.set.assert_called_with("overview_intro_dismissed", False)
        self.assertEqual(len(navigated), 0)
        controller.refresh.assert_not_called()

    @patch("ui.tweaks_page.SettingsManager.instance")
    def test_tweaks_search_tab_refresh_and_profile_menu_keyboard_route(self, settings):
        settings.return_value.get.return_value = []
        profile = SimpleNamespace(is_fedora=True, desktop=SimpleNamespace(value="kde"),
                                  deployment_backend=SimpleNamespace(value="dnf5"))
        page = self.show(TweaksPage(profile))
        refreshed = QSignalSpy(page.refreshRequested)
        library = QSignalSpy(page.choosePresetRequested)
        self.focus(page.search_input)
        QTest.keyClicks(page.search_input, "touchpad")
        self.assertIs(self.app.focusWidget(), page.search_input)
        QTest.keyClick(page.search_input, Qt.Key.Key_Tab)
        self.assertIs(self.app.focusWidget(), page.refresh_button)
        QTest.keyClick(page.refresh_button, Qt.Key.Key_Space)
        self.assertEqual(len(refreshed), 1)
        self.focus(page.profile_menu_button)
        menu = page.profile_menu_button.menu()
        observed = []

        def select_library_action():
            observed.append(menu.isVisible())
            for _ in range(3):
                QTest.keyClick(menu, Qt.Key.Key_Down)
            QTest.keyClick(menu, Qt.Key.Key_Return)

        QTimer.singleShot(100, select_library_action)
        watchdog = QTimer(menu)
        watchdog.setSingleShot(True)
        watchdog.timeout.connect(menu.close)
        watchdog.start(1500)
        QTest.keyClick(page.profile_menu_button, Qt.Key.Key_Space)
        watchdog.stop()
        self.assertEqual(observed, [True])
        self.app.processEvents()
        self.assertEqual(len(library), 1)

    def test_review_keyboard_acceptance_requires_acknowledgment_then_explicit_space(self):
        dialog = self.show(ReviewedActionDialog(
            "Fixture", "Review", "Exact scope", "No automatic rollback", require_no_rollback_acceptance=True))
        accepted = QSignalSpy(dialog.accepted)
        self.assertFalse(dialog.accept_button.isEnabled())
        self.focus(dialog.scope_view)
        QTest.keyClick(dialog.scope_view, Qt.Key.Key_Return)
        self.app.processEvents()
        self.assertEqual(len(accepted), 0)
        if not dialog.isVisible():
            dialog.show()
            dialog.activateWindow()
            self.app.processEvents()
        self.focus(dialog.no_rollback_checkbox)
        QTest.keyClick(dialog.no_rollback_checkbox, Qt.Key.Key_Space)
        self.assertTrue(dialog.accepts_no_rollback)
        self.focus(dialog.accept_button)
        QTest.keyClick(dialog.accept_button, Qt.Key.Key_Space)
        self.assertEqual(len(accepted), 1)

    def test_review_return_in_content_cannot_apply_after_acknowledgment(self):
        dialog = self.show(ReviewedActionDialog(
            "Fixture", "Review", "Scope", "No rollback", require_no_rollback_acceptance=True))
        accepted = QSignalSpy(dialog.accepted)
        self.focus(dialog.no_rollback_checkbox)
        QTest.keyClick(dialog.no_rollback_checkbox, Qt.Key.Key_Space)
        self.assertTrue(dialog.accept_button.isEnabled())
        self.focus(dialog.scope_view)
        QTest.keyClick(dialog.scope_view, Qt.Key.Key_Return)
        self.app.processEvents()
        self.assertEqual(len(accepted), 0)

    def test_review_cancel_and_escape_never_accept(self):
        for key in (Qt.Key.Key_Space, Qt.Key.Key_Escape):
            with self.subTest(key=key):
                dialog = self.show(ReviewedActionDialog("Fixture", "Review", "Scope", "Recorded prior value"))
                accepted = QSignalSpy(dialog.accepted)
                rejected = QSignalSpy(dialog.rejected)
                self.focus(dialog.cancel_button)
                QTest.keyClick(dialog.cancel_button, key)
                self.app.processEvents()
                self.assertEqual(len(accepted), 0)
                self.assertEqual(len(rejected), 1)

    def test_review_escape_returns_focus_to_trigger(self):
        parent = QWidget()
        layout = QVBoxLayout(parent)
        trigger = QPushButton("Review selected applications", parent)
        layout.addWidget(trigger)
        self.show(parent)
        self.focus(trigger)
        dialog = ReviewedActionDialog("Fixture", "Review", "Scope", "Recorded prior value", parent=parent)
        self.addCleanup(self.dispose, dialog)
        dialog.open()
        self.app.processEvents()
        self.focus(dialog.cancel_button)
        QTest.keyClick(dialog.cancel_button, Qt.Key.Key_Escape)
        self.app.processEvents()
        self.assertIs(parent.focusWidget(), trigger)
        # The offscreen plugin does not reactivate the parent like KWin does.
        # Reactivate its window without choosing a widget, then require Qt to
        # restore the remembered initiating focus rather than another control.
        parent.activateWindow()
        self.app.processEvents()
        self.assertIs(self.app.focusWidget(), trigger)
