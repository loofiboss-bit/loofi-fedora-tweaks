"""UI contract tests for the canonical, navigation-only Home."""

from __future__ import annotations

import unittest
from datetime import datetime, timezone
from unittest.mock import MagicMock

from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import QApplication, QFrame, QPushButton

from core.home import AttentionItem, HomeSummary, HomeTask, RecentChange, Recommendation
from ui.atlas_dashboard_tab import AtlasDashboardTab


class _SummaryService:
    def __init__(self, summary: HomeSummary):
        self.value = summary

    def summary(self) -> HomeSummary:
        return self.value


def _summary() -> HomeSummary:
    return HomeSummary(
        overall_state="critical",
        data_state="fresh",
        summary="A saved maintenance run needs review.",
        generated_at=datetime.now(timezone.utc),
        primary_recommendation=Recommendation(
            "run", "action_run_review", "Review maintenance", "An interrupted run needs review.",
            "maintenance:action-center", "critical",
        ),
        attention_items=(
            AttentionItem("updates", "Updates", "Updates are available.", "maintenance:updates"),
            AttentionItem("backup", "Backup", "Recovery protection is stale.", "backup"),
            AttentionItem("health", "Health", "A health issue is recurring.", "maintenance:health-timeline"),
        ),
        common_tasks=tuple(
            HomeTask(str(index), f"Task {index}", "Open a maintained route.", route, "home")
            for index, route in enumerate(("maintenance:updates", "software:apps", "monitor", "backup"))
        ),
        recent_change=RecentChange("change", "Changed a setting", None, True),
    )


class TestCanonicalHomeUi(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_content_limits_and_no_home_timer(self):
        tab = AtlasDashboardTab(home_service=_SummaryService(_summary()))

        self.assertEqual(len(tab.findChildren(QFrame, "homePrimaryRecommendation")), 1)
        self.assertEqual(len(tab.findChildren(QFrame, "homeAttentionItem")), 3)
        self.assertEqual(len(tab.findChildren(QFrame, "homeTask")), 4)
        self.assertEqual(len(tab.findChildren(QFrame, "homeRecentChange")), 1)
        self.assertEqual(tab.findChildren(QTimer), [])

    def test_action_center_control_only_navigates(self):
        main_window = MagicMock()
        tab = AtlasDashboardTab(main_window=main_window, home_service=_SummaryService(_summary()))
        action_link = tab.findChild(QPushButton, "homeActionCenterLink")

        self.assertIsNotNone(action_link)
        action_link.click()

        main_window.switch_to_route.assert_called_once_with("maintenance:action-center")

    def test_home_has_no_plan_run_or_verify_controls(self):
        tab = AtlasDashboardTab(home_service=_SummaryService(_summary()))
        button_text = {button.text().lower() for button in tab.findChildren(QPushButton)}

        self.assertNotIn("plan", button_text)
        self.assertNotIn("run", button_text)
        self.assertNotIn("verify", button_text)


if __name__ == "__main__":
    unittest.main()
