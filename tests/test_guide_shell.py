"""The compact shell guide menu resumes the selected guide without execution."""

from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from PyQt6.QtGui import QAction
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QApplication, QFrame, QHBoxLayout, QMenu, QPushButton, QToolButton

from core.tasks.guides import GUIDES_BY_ID, GuideProgressSnapshot, GuideStepProgress
from ui.main_window_guides import GuideNavigationMixin


class TestGuideShell(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def _owner(self):
        button = QToolButton()
        menu = QMenu(button)
        next_action = QAction(menu)
        return_action = QAction(menu)
        return SimpleNamespace(
            tr=lambda value: value,
            _resume_guide_button=button,
            _resume_guide_menu=menu,
            _continue_guide_action=next_action,
            _return_to_guide_action=return_action,
        )

    def test_resume_control_accepts_keyboard_and_accessibility_focus(self):
        frame = QFrame()
        frame.actions_layout = QHBoxLayout(frame)
        previous = QPushButton("Previous control", frame)
        frame.actions_layout.addWidget(previous)
        owner = SimpleNamespace(
            tr=lambda value: value, _breadcrumb_frame=frame,
            _continue_guide_from_shell=Mock(), _resume_active_guide=Mock(),
        )
        GuideNavigationMixin._setup_guide_controls(owner)
        try:
            owner._resume_guide_button.show()
            frame.show()
            previous.setFocus()
            self.app.processEvents()
            QTest.keyClick(previous, Qt.Key.Key_Tab)
            self.assertIs(frame.focusWidget(), owner._resume_guide_button)
            self.assertEqual(owner._resume_guide_button.focusPolicy(), Qt.FocusPolicy.StrongFocus)
            self.assertEqual(owner._resume_guide_button.popupMode(), QToolButton.ToolButtonPopupMode.MenuButtonPopup)
            shown = []
            owner._resume_guide_menu.aboutToShow.connect(lambda: shown.append(True))
            QTimer.singleShot(50, owner._resume_guide_menu.close)
            QTest.keyClick(owner._resume_guide_button, Qt.Key.Key_Space)
            self.assertEqual(shown, [True])
            self.assertIs(frame.focusWidget(), owner._resume_guide_button)
        finally:
            frame.close()

    def test_menu_names_the_next_unfinished_step_and_return_target(self):
        guide = GUIDES_BY_ID["make-fedora-yours"]
        owner = self._owner()
        snapshot = GuideProgressSnapshot(
            guide.id,
            guide.steps[0].id,
            {guide.steps[0].id: GuideStepProgress("reviewed", 10.0)},
            1,
        )
        with patch("core.tasks.guides.GuideProgressStore") as store:
            store.return_value.read.return_value = snapshot
            GuideNavigationMixin._set_active_guide(owner, guide.id)

        self.assertEqual(owner._active_guide_id, guide.id)
        self.assertEqual(owner._continue_guide_action.data(), guide.steps[1].id)
        self.assertEqual(owner._continue_guide_action.text(), "Open next step: Review a desktop change")
        self.assertEqual(owner._return_to_guide_action.text(), "Return to Make Fedora yours")
        self.assertFalse(owner._resume_guide_button.isHidden())

    def test_all_reviewed_guide_disables_next_step_but_keeps_return(self):
        guide = GUIDES_BY_ID["make-fedora-yours"]
        owner = self._owner()
        completed = {step.id: GuideStepProgress("reviewed", 20.0) for step in guide.steps}
        snapshot = GuideProgressSnapshot(guide.id, guide.steps[-1].id, completed, 4)
        with patch("core.tasks.guides.GuideProgressStore") as store:
            store.return_value.read.return_value = snapshot
            GuideNavigationMixin._set_active_guide(owner, guide.id)

        self.assertFalse(owner._continue_guide_action.isEnabled())
        self.assertEqual(owner._continue_guide_action.text(), "All guide steps have been reviewed")
        self.assertTrue(owner._return_to_guide_action.isEnabled())

    def test_next_step_action_returns_to_overview_and_opens_that_step(self):
        guide = GUIDES_BY_ID["choose-and-manage-apps"]
        owner = self._owner()
        owner._active_guide_id = guide.id
        owner._continue_guide_action.setData(guide.steps[1].id)
        owner.switch_to_route = Mock(return_value=True)
        owner._sidebar_index = {"overview": object()}
        overview = SimpleNamespace(guide_panel=SimpleNamespace(open_step=Mock(return_value=True)))
        owner._real_widget_for_entry = Mock(return_value=overview)

        GuideNavigationMixin._continue_guide_from_shell(owner)

        owner.switch_to_route.assert_called_once_with("overview")
        overview.guide_panel.open_step.assert_called_once_with(guide.id, guide.steps[1].id)


if __name__ == "__main__":
    unittest.main()
