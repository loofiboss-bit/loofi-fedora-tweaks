"""REQ-003 deterministic Home next-action and onboarding contracts."""

from __future__ import annotations

import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from unittest.mock import MagicMock

from PyQt6.QtCore import Qt
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QApplication

from core.home import ONBOARDING_STEPS, OnboardingState, OnboardingStore
from core.home.recommendations import select_primary_recommendation
from core.home.models import Recommendation
from ui.atlas_dashboard_tab import AtlasDashboardTab


class _OnboardingMemoryStore:
    def __init__(self, state: OnboardingState = OnboardingState()) -> None:
        self.state = state
        self.load_calls = 0
        self.advance_calls = 0
        self.dismiss_calls = 0

    def load(self) -> OnboardingState:
        self.load_calls += 1
        return self.state

    def advance(self, state: OnboardingState) -> OnboardingState:
        self.advance_calls += 1
        next_step = state.step + 1
        self.state = replace(
            state,
            step=min(next_step, len(ONBOARDING_STEPS) - 1),
            completed=next_step >= len(ONBOARDING_STEPS),
        )
        return self.state

    def dismiss(self, state: OnboardingState) -> OnboardingState:
        self.dismiss_calls += 1
        self.state = replace(state, dismissed=True)
        return self.state


class TestFlowHomeOnboarding(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def test_store_resumes_step_and_preserves_legacy_completion(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            store = OnboardingStore(root / "onboarding.json", root / "first_run_complete")
            state = store.load()
            self.assertEqual(state.step, 0)
            state = store.advance(state)
            self.assertEqual(store.load().step, 1)
            state = store.advance(state)
            state = store.advance(state)
            self.assertTrue(state.completed)
            self.assertTrue((root / "first_run_complete").exists())

            (root / "onboarding.json").unlink()
            self.assertTrue(store.load().completed)

    def test_onboarding_is_non_blocking_navigation_only_and_dismissible(self) -> None:
        main_window = MagicMock()
        store = _OnboardingMemoryStore(OnboardingState(step=1))
        tab = AtlasDashboardTab(main_window=main_window, onboarding_store=store)
        self.addCleanup(tab.deleteLater)

        self.assertEqual(store.load_calls, 1)
        self.assertTrue(tab.onboarding_card.isVisibleTo(tab) or not tab.isVisible())
        self.assertEqual(tab.onboarding_card.advance_button.property("routeId"), "health")
        tab.show()
        self.app.processEvents()
        tab.onboarding_card.advance_button.setFocus()
        QTest.keyClick(tab.onboarding_card.advance_button, Qt.Key.Key_Space)

        self.assertEqual(store.advance_calls, 1)
        main_window.switch_to_route.assert_called_once_with("health")

        QTest.mouseClick(tab.onboarding_card.dismiss_button, Qt.MouseButton.LeftButton)
        self.assertEqual(store.dismiss_calls, 1)
        self.assertTrue(tab.onboarding_card.isHidden())

    def test_next_action_selection_is_order_independent_and_deterministic(self) -> None:
        recommendations = (
            Recommendation("updates", "updates", "Updates", "Updates available", "maintenance:updates", "attention"),
            Recommendation("state", "state_integrity", "Repair state", "State needs review", "settings:repair", "critical"),
            Recommendation("run", "action_run_review", "Review run", "Interrupted run", "maintenance:action-center", "critical"),
        )
        expected = select_primary_recommendation(recommendations)
        self.assertEqual(expected.kind, "state_integrity")
        self.assertEqual(select_primary_recommendation(tuple(reversed(recommendations))), expected)


if __name__ == "__main__":
    unittest.main()
