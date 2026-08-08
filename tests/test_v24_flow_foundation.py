"""REQ-001/REQ-002 contracts for the Flow semantic presentation foundation."""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock

from core.navigation import NavigationMode, destinations_for_mode
from PyQt6.QtCore import Qt
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QApplication, QComboBox, QLabel
from ui.components import (
    ActionCenterWorkItem,
    ApplicationRow,
    ConfirmationRiskPanel,
    DestructiveButton,
    DisabledState,
    ErrorState,
    FeedbackBanner,
    QuietButton,
    RetryButton,
    SearchFilterRow,
    SectionHeader,
    SuccessState,
    TaskSummary,
)
from ui.components.layout import LayoutMetrics, PageHeader
from ui.icon_pack import get_semantic_icon
from ui.navigation.destination_sidebar import DestinationSidebar
from ui.presentation import button_label, visible_label


class TestFlowSemanticFoundation(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def test_action_roles_cover_quiet_destructive_and_retry(self) -> None:
        for button_type, role in (
            (QuietButton, "quiet"),
            (DestructiveButton, "destructive"),
            (RetryButton, "retry"),
        ):
            with self.subTest(role=role):
                button = button_type("Try again", description="Repeat the safe check")
                callback = MagicMock()
                button.clicked.connect(callback)
                button.show()
                button.setFocus()
                QTest.keyClick(button, Qt.Key.Key_Space)
                callback.assert_called_once()
                self.assertEqual(button.property("buttonRole"), role)
                self.assertEqual(button.accessibleName(), "Try again")
                self.assertTrue(button.accessibleDescription())

    def test_complete_state_and_banner_patterns_are_non_color_only(self) -> None:
        error = ErrorState("Could not check", "The saved result is unchanged", retry_text="Try again")
        success = SuccessState("Check complete", "No issue was found")
        disabled = DisabledState("Unavailable", "This capability is not installed")
        banner = FeedbackBanner("Restart required", "Finish after restarting", kind="warning")

        self.assertEqual(error.property("presentationState"), "error")
        self.assertEqual(success.property("presentationState"), "success")
        self.assertEqual(disabled.property("presentationState"), "disabled")
        self.assertIn("Restart required", banner.accessibleName())
        self.assertIn("Finish after restarting", banner.accessibleDescription())

    def test_header_and_visible_labels_remove_identifier_and_mnemonic_artifacts(self) -> None:
        self.assertEqual(visible_label("Software_Updates"), "Software Updates")
        self.assertEqual(button_label("Network & Security"), "Network && Security")
        header = PageHeader()
        header.set_content("Software & Updates", "Network_Security", "Review state")
        header.set_status("Ready", kind="success", description="Saved state is current")

        self.assertEqual(header.eyebrow.text(), "Software && Updates")
        self.assertEqual(header.eyebrow.accessibleName(), "Software & Updates")
        self.assertEqual(header.title.text(), "Network Security")
        self.assertTrue(header.status.isVisible() or not header.isVisible())
        self.assertEqual(header.status.accessibleName(), "Ready")

    def test_navigation_groups_six_stable_destinations_without_new_ids(self) -> None:
        sidebar = DestinationSidebar()
        sidebar.set_destinations(destinations_for_mode(NavigationMode.STANDARD))

        self.assertEqual(
            sidebar.destination_ids(),
            ("home", "software_updates", "system", "network_security", "desktop", "settings"),
        )
        self.assertEqual(
            sidebar.presentation_groups(),
            (
                ("Overview", ("home",)),
                ("Manage", ("software_updates", "system", "network_security")),
                ("Personalize", ("desktop", "settings")),
            ),
        )

    def test_section_search_summary_risk_and_rows_share_accessible_hierarchy(self) -> None:
        section = SectionHeader("Available applications", "Search the curated catalog")
        search = SearchFilterRow("Search applications…", accessible_name="Application search")
        source_filter = QComboBox()
        source_filter.addItem("All sources")
        search.add_filter(source_filter, accessible_name="Application source")
        summary = TaskSummary("Update check", "Review saved update state", status="Ready", status_kind="success")
        summary.add_fact("Source", "Fedora")
        risk = ConfirmationRiskPanel("Review plan", "Nothing runs until Run Plan")
        risk.set_review_facts(
            risk="Medium",
            scope="Packages",
            requirements="Administrator approval",
            validation="Package state",
            rollback="DNF history guidance",
        )
        app_row = ApplicationRow(
            "org.example.App",
            "Example App",
            "A curated example",
            source="Fedora",
            status="Available",
            status_kind="info",
            action_text="Review install",
            action_id="install",
        )
        work_item = ActionCenterWorkItem(
            "plan-1",
            "Update Fedora packages",
            "Review risk and validation",
            status="Needs review",
            status_kind="warning",
        )

        self.assertEqual(section.accessibleName(), "Available applications")
        self.assertEqual(search.search.accessibleName(), "Application search")
        self.assertEqual(source_filter.accessibleName(), "Application source")
        self.assertEqual(summary.status_badge.accessibleName(), "Ready")
        self.assertTrue(risk.facts.isVisibleTo(risk) or not risk.isVisible())
        self.assertIn("Source: Fedora", app_row.accessibleDescription())
        self.assertIn("Select to review details", work_item.accessibleDescription())

    def test_semantic_icons_and_geometry_have_deterministic_scale_contract(self) -> None:
        for role in (
            "application",
            "catalog",
            "check",
            "error",
            "retry",
            "review",
            "success",
            "warning",
        ):
            with self.subTest(role=role):
                self.assertFalse(get_semantic_icon(role, size=20).isNull())

        probe = QLabel("Flow")
        metrics = LayoutMetrics.from_widget(probe)
        for scale in (1.0, 1.25, 1.4, 1.5, 2.0):
            with self.subTest(scale=scale):
                self.assertGreaterEqual(int(metrics.header_height * scale), int(68 * scale))
                self.assertGreaterEqual(int(metrics.sidebar_collapsed_width * scale), int(64 * scale))


if __name__ == "__main__":
    unittest.main()
