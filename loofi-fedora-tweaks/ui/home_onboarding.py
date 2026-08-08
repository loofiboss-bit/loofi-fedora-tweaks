"""Compact non-blocking onboarding embedded in canonical Home."""

from __future__ import annotations

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import QLabel, QWidget

from core.home.onboarding import ONBOARDING_STEPS, OnboardingState
from ui.components import ActionBar, Card, InlineNotice, PrimaryButton, QuietButton, StatusBadge


class HomeOnboardingCard(Card):
    """Present one inert onboarding step with explicit advance and dismiss."""

    advanceRequested = pyqtSignal()
    dismissRequested = pyqtSignal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent=parent)
        self.setObjectName("homeOnboarding")
        self.setProperty("onboarding", True)
        self.progress_badge = StatusBadge("")
        self.progress_badge.setObjectName("homeOnboardingProgress")
        self.add_widget(self.progress_badge)
        self.safety_label = QLabel(
            self.tr("Guidance only — opening, continuing, or dismissing this card changes no system setting.")
        )
        self.safety_label.setObjectName("homeOnboardingSafety")
        self.safety_label.setWordWrap(True)
        self.add_widget(self.safety_label)
        self.feedback = InlineNotice("", "", kind="error")
        self.feedback.setObjectName("homeOnboardingFeedback")
        self.feedback.hide()
        self.add_widget(self.feedback)
        actions = ActionBar()
        self.dismiss_button = QuietButton(
            self.tr("Dismiss"),
            description=self.tr("Hide getting-started guidance without changing the system."),
        )
        self.dismiss_button.setObjectName("homeOnboardingDismiss")
        self.dismiss_button.clicked.connect(self.dismissRequested)
        actions.add_action(self.dismiss_button)
        self.advance_button = PrimaryButton()
        self.advance_button.setObjectName("homeOnboardingAdvance")
        self.advance_button.clicked.connect(self.advanceRequested)
        actions.add_action(self.advance_button, primary=True)
        self.add_widget(actions)

    def set_state(self, state: OnboardingState) -> None:
        step = state.current_step
        self.set_heading(self.tr(step.title), self.tr(step.description))
        self.progress_badge.set_status(
            self.tr("Getting started %1 of %2")
            .replace("%1", str(state.step + 1))
            .replace("%2", str(len(ONBOARDING_STEPS))),
            kind="info",
            description=self.tr("Onboarding progress"),
        )
        self.advance_button.setText(self.tr(step.action_label))
        self.advance_button.setAccessibleDescription(self.tr(step.description))
        self.advance_button.setProperty("routeId", step.route_id)
        self.feedback.hide()
        self.setVisible(state.visible)

    def show_error(self, message: str) -> None:
        self.feedback.set_notice(
            "error",
            self.tr("Could not save onboarding progress"),
            message,
        )
        self.feedback.show()
