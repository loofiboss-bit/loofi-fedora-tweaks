"""Focused v29 shell contracts for the task-oriented utility presentation."""

from __future__ import annotations

import os
import sys
import unittest
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(
    0,
    os.path.join(os.path.dirname(__file__), "..", "loofi-fedora-tweaks"),
)

from PyQt6.QtWidgets import QApplication, QPushButton

from ui.activity_recovery_tab import ActivityRecoveryTab
from ui.main_window import MainWindow
from ui.navigation import UTILITY_DESTINATIONS
from ui.utility_landing_page import UtilityLandingPage, default_utility_tasks


class TestV29UtilityLandingPage(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def test_each_job_has_a_single_primary_cta_and_bounded_groups(self) -> None:
        for destination_id, tasks in default_utility_tasks().items():
            page = UtilityLandingPage(
                destination_id,
                destination_id.title(),
                "Description",
                tasks,
            )
            try:
                primary = [
                    button
                    for button in page.findChildren(QPushButton)
                    if button.property("buttonRole") == "primary"
                ]
                self.assertEqual(len(primary), 1, destination_id)
                self.assertLessEqual(len(tasks), 5, destination_id)
                self.assertEqual(page.property("presentationState"), None)
                self.assertEqual(page.state_notice.property("presentationState"), "ready")
            finally:
                page.close()


class TestV29MainWindowShell(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        self.window = None

    def tearDown(self) -> None:
        if self.window is not None:
            self.window.close()
            self.app.processEvents()

    def _build(self) -> MainWindow:
        with patch.object(MainWindow, "_check_first_run", lambda _self: None), patch.object(
            MainWindow,
            "_initialize_background_services",
            lambda _self: None,
        ):
            self.window = MainWindow()
        self.app.processEvents()
        return self.window

    def test_primary_navigation_is_five_user_jobs(self) -> None:
        window = self._build()
        window._set_sidebar_collapsed(False)

        self.assertEqual(
            window.sidebar.destination_ids(),
            tuple(destination.id for destination in UTILITY_DESTINATIONS),
        )
        self.assertEqual(
            [
                window.sidebar.topLevelItem(index).text(0)
                for index in range(window.sidebar.topLevelItemCount())
            ],
            ["Home", "Install", "Tune", "Fix", "Update"],
        )
        self.assertTrue(
            all(
                window.sidebar.topLevelItem(index).childCount() == 0
                for index in range(window.sidebar.topLevelItemCount())
            )
        )

    def test_landing_aliases_open_page_and_cta_emits_a_canonical_route(self) -> None:
        window = self._build()
        self.assertTrue(window.switch_to_route("install"))
        opened: list[str] = []
        window.switch_to_route = lambda route_id, **_kwargs: opened.append(route_id) or True
        page = window._sidebar_index["utility_install"].page_widget
        page.primary_button.click()

        self.assertEqual(opened, ["software:apps"])

    def test_legacy_change_routes_open_activity_and_secondary_routes_clear_primary(self) -> None:
        window = self._build()

        self.assertTrue(window.switch_to_route("changes"))
        self.assertEqual(window._active_route_id, "activity")
        self.assertEqual(window._active_destination_id, "")
        self.assertTrue(window.switch_to_route("settings"))
        self.assertEqual(window._active_destination_id, "")

    def test_saved_run_compatibility_link_uses_activity_surface(self) -> None:
        window = self._build()
        window._open_action_center_run("run-v29")

        self.assertEqual(window._active_route_id, "activity")
        activity = window._real_widget_for_entry(window._sidebar_index["activity"])
        self.assertEqual(activity._requested_run_id, "run-v29")


class TestV29ActivityTerminology(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def test_activity_surface_has_no_action_center_user_copy(self) -> None:
        tab = ActivityRecoveryTab(journal_service=object())
        try:
            visible_text = " ".join(
                widget.text()
                for widget in tab.findChildren(QPushButton)
                if widget.text()
            )
            self.assertNotIn("Action Center", visible_text)
        finally:
            tab.close()

    def test_activity_primary_views_are_needs_you_progress_and_history(self) -> None:
        tab = ActivityRecoveryTab(journal_service=object())
        try:
            labels = [
                tab.activity_view_filter.itemText(index)
                for index in range(tab.activity_view_filter.count())
            ]
            self.assertEqual(labels, ["Needs you", "In progress", "History"])
            self.assertEqual(
                tab._current_filters()["statuses"],
                ("failed", "verification_failed", "awaiting_reboot", "interrupted"),
            )
        finally:
            tab.close()


if __name__ == "__main__":
    unittest.main()
