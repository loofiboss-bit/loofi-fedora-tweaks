"""UI contract tests for the canonical, navigation-only Home."""

from __future__ import annotations

import unittest
from dataclasses import replace
from datetime import datetime, timezone
from unittest.mock import MagicMock

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QFont
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QApplication, QAbstractButton, QFrame, QLabel, QPushButton, QScrollArea

from core.home import AttentionItem, HomeStatus, HomeSummary, HomeTask, RecentChange, Recommendation
from ui.components import ClickableCard, DetailsDisclosure, PageScaffold, StatusBadge
from ui.atlas_dashboard_tab import AtlasDashboardTab
from ui.design.theme_manager import ThemeManager


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
        status_items=(
            HomeStatus("health", "System health", "critical", "Health needs review.", "maintenance:health-timeline"),
            HomeStatus("updates", "Updates", "attention", "Updates are available.", "maintenance:updates"),
            HomeStatus("storage", "Storage", "good", "Storage is healthy.", "storage"),
            HomeStatus("recovery", "Recovery protection", "unknown", "No saved protection status.", "backup"),
        ),
        last_checked_at=datetime(2026, 7, 24, 10, 30, tzinfo=timezone.utc),
        freshness_state="fresh",
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
        self.assertEqual(len(tab.findChildren(PageScaffold)), 1)
        self.assertEqual(tab.findChildren(QScrollArea), [])

    def test_status_tasks_and_activity_use_phase_four_components(self):
        tab = AtlasDashboardTab(home_service=_SummaryService(_summary()))

        statuses = tab.findChildren(StatusBadge, "statusBadge")
        status_categories = {
            str(badge.property("statusCategory"))
            for badge in statuses
            if badge.property("statusCategory")
        }
        self.assertEqual(status_categories, {"health", "updates", "storage", "recovery"})

        task_cards = tab.findChildren(ClickableCard, "homeTask")
        self.assertEqual(len(task_cards), 4)
        for card in task_cards:
            self.assertEqual(card.findChildren(QAbstractButton), [])
            icon = card.findChild(QLabel, "homeTaskIcon")
            self.assertIsNotNone(icon)
            self.assertFalse(icon.pixmap().isNull())

        disclosure = tab.findChild(DetailsDisclosure, "detailsDisclosure")
        self.assertIsNotNone(disclosure)
        self.assertFalse(disclosure.details.isVisible())

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

    def test_check_now_is_directly_visible_for_empty_stale_and_error_states(self):
        for data_state, freshness in (
            ("empty", "unavailable"),
            ("stale", "stale"),
            ("error", "unavailable"),
        ):
            with self.subTest(data_state=data_state):
                summary = replace(
                    _summary(),
                    data_state=data_state,
                    freshness_state=freshness,
                    last_checked_at=None if data_state == "empty" else _summary().last_checked_at,
                )
                factory = MagicMock()
                tab = AtlasDashboardTab(
                    home_service=_SummaryService(summary),
                    check_worker_factory=factory,
                )

                button = tab.findChild(QPushButton, "homeCheckNow")
                self.assertIsNotNone(button)
                self.assertFalse(button.isHidden())
                factory.assert_not_called()

    def test_status_card_shows_last_checked_and_freshness(self):
        tab = AtlasDashboardTab(home_service=_SummaryService(_summary()))

        label = tab.findChild(QLabel, "homeLastChecked")

        self.assertIsNotNone(label)
        self.assertIn("2026-07-24", label.text())
        self.assertIn("Fresh", label.text())

    def test_phase_two_size_scale_and_theme_matrix_keeps_check_action_available(self):
        original_font = self.app.font()
        theme_manager = ThemeManager()
        try:
            for theme in ThemeManager.SUPPORTED_THEMES:
                self.assertTrue(theme_manager.apply(self.app, theme))
                for width in (860, 1180, 1400):
                    for scale in (100, 140, 200):
                        with self.subTest(theme=theme, width=width, scale=scale):
                            font = QFont(original_font)
                            font.setPointSizeF(original_font.pointSizeF() * scale / 100)
                            self.app.setFont(font)
                            tab = AtlasDashboardTab(
                                home_service=_SummaryService(_summary())
                            )
                            tab.resize(width, 900)
                            tab.show()
                            self.app.processEvents()

                            button = tab.findChild(QPushButton, "homeCheckNow")
                            self.assertIsNotNone(button)
                            self.assertTrue(button.isVisible())
                            self.assertGreater(button.width(), 0)
                            self.assertLessEqual(button.mapTo(tab, button.rect().topRight()).x(), tab.width())

                            tab.close()
                            tab.deleteLater()
                            self.app.processEvents()
        finally:
            self.app.setFont(original_font)
            theme_manager.apply(self.app, "system")

    def test_keyboard_activates_check_and_action_center_route(self):
        factory = MagicMock()
        worker = MagicMock()
        worker.isRunning.return_value = False
        factory.return_value = worker
        main_window = MagicMock()
        tab = AtlasDashboardTab(
            main_window=main_window,
            home_service=_SummaryService(_summary()),
            check_worker_factory=factory,
        )
        tab.show()
        self.app.processEvents()

        check_button = tab.findChild(QPushButton, "homeCheckNow")
        check_button.setFocus()
        QTest.keyClick(check_button, Qt.Key.Key_Space)
        factory.assert_called_once_with(tab)
        worker.start.assert_called_once_with()

        action_link = tab.findChild(QPushButton, "homeActionCenterLink")
        action_link.setFocus()
        QTest.keyClick(action_link, Qt.Key.Key_Space)
        main_window.switch_to_route.assert_called_once_with("maintenance:action-center")


if __name__ == "__main__":
    unittest.main()
