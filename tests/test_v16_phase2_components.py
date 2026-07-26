"""Canonical API and structural contracts for v16 Phase 2."""

from __future__ import annotations

import os
import sys
import unittest
from unittest.mock import MagicMock

from PyQt6.QtCore import Qt
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QApplication, QLabel, QPushButton, QWidget

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "loofi-fedora-tweaks"))

import ui.components as components
from ui import layout_primitives, shared_states
from ui.components import (
    ActionBar,
    ClickableCard,
    DangerButton,
    DefinitionList,
    GhostButton,
    LocalViewItem,
    LocalViewSwitcher,
    PageHeader,
    PageScaffold,
    PrimaryButton,
    SecondaryButton,
    SectionItem,
    SectionNavigator,
)
from ui.components.layout import AdaptiveGrid


class TestCanonicalComponentApi(unittest.TestCase):
    def test_public_api_contains_only_phase2_components(self) -> None:
        self.assertEqual(
            set(components.__all__),
            {
                "ActionBar",
                "ActionProgress",
                "Card",
                "ClickableCard",
                "ContentColumn",
                "DangerButton",
                "DefinitionList",
                "DefinitionRow",
                "DetailsDisclosure",
                "EmptyState",
                "GhostButton",
                "InlineNotice",
                "LoadingState",
                "LocalViewItem",
                "LocalViewSwitcher",
                "PageHeader",
                "PageScaffold",
                "PrimaryButton",
                "SecondaryButton",
                "SectionItem",
                "SectionNavigator",
                "StatusBadge",
                "UnavailableState",
            },
        )
        for legacy_name in (
            "ActionRow",
            "AdaptiveGrid",
            "LayoutMetrics",
            "ResultBanner",
            "RoleButton",
            "RouteCard",
            "Section",
            "make_page_title",
        ):
            self.assertNotIn(legacy_name, components.__all__)

    def test_legacy_imports_are_identity_shims(self) -> None:
        self.assertIs(layout_primitives.ActionRow, components.ActionBar)
        self.assertIs(layout_primitives.Section, components.Card)
        self.assertIs(layout_primitives.RouteCard, components.ClickableCard)
        self.assertIs(shared_states.ResultBanner, components.InlineNotice)
        self.assertIs(shared_states.LoadingState, components.LoadingState)


class TestInteractiveComponents(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def test_button_roles_are_accessible_and_keyboard_operable(self) -> None:
        for button_type, role in (
            (PrimaryButton, "primary"),
            (SecondaryButton, "secondary"),
            (GhostButton, "ghost"),
            (DangerButton, "danger"),
        ):
            with self.subTest(role=role):
                button = button_type("Continue", description="Continue safely")
                callback = MagicMock()
                button.clicked.connect(callback)
                button.show()
                button.setFocus()
                QTest.keyClick(button, Qt.Key.Key_Space)

                callback.assert_called_once()
                self.assertEqual(button.property("buttonRole"), role)
                self.assertGreaterEqual(button.minimumWidth(), 36)
                self.assertGreaterEqual(button.minimumHeight(), 36)
                self.assertEqual(button.accessibleName(), "Continue")
                self.assertEqual(button.accessibleDescription(), "Continue safely")

    def test_button_presentation_states_keep_text_and_accessibility(self) -> None:
        button = PrimaryButton("Apply", description="Apply reviewed changes")

        button.set_loading(True, "Applying")
        self.assertEqual(button.property("interactionState"), "loading")
        self.assertFalse(button.isEnabled())
        self.assertIn("Applying", button.accessibleDescription())
        button.set_error("Try again")
        self.assertEqual(button.property("interactionState"), "error")
        self.assertTrue(button.isEnabled())
        button.set_success("Applied")
        self.assertEqual(button.property("interactionState"), "success")
        button.reset_state()
        self.assertEqual(button.text(), "Apply")

    def test_clickable_card_activates_without_nested_action(self) -> None:
        card = ClickableCard("Updates", "Review available updates", "updates")
        callback = MagicMock()
        card.activated.connect(callback)
        card.resize(320, 120)
        card.show()
        card.setFocus()

        QTest.keyClick(card, Qt.Key.Key_Return)
        QTest.keyClick(card, Qt.Key.Key_Enter)
        QTest.keyClick(card, Qt.Key.Key_Space)
        QTest.mouseClick(card, Qt.MouseButton.LeftButton, pos=card.rect().center())
        self.assertEqual(callback.call_count, 4)
        callback.assert_called_with("updates")

        with self.assertRaises(ValueError):
            card.add_widget(QPushButton("Nested"))
        card.add_widget(QLabel("Read-only detail"))
        card.setEnabled(False)
        card.activate()
        self.assertEqual(callback.call_count, 4)

    def test_navigator_uses_explicit_modes_and_stable_ids(self) -> None:
        navigator = SectionNavigator()
        navigator.set_sections(
            [
                SectionItem("overview", "Översikt och aktuell systemstatus", "Saved state", "Ready"),
                SectionItem("details", "Technical details and history", "Read-only details"),
            ]
        )
        callback = MagicMock()
        navigator.sectionActivated.connect(callback)

        self.assertFalse(navigator.is_compact())
        self.assertEqual(navigator.section_ids(), ("overview", "details"))
        self.assertIn("Ready", navigator.rail.item(0).text())
        navigator.set_active_section("details")
        callback.assert_not_called()
        navigator.rail.setCurrentRow(0)
        callback.assert_called_once_with("overview")

        callback.reset_mock()
        navigator.set_compact(True)
        self.assertTrue(navigator.is_compact())
        navigator.selector.setCurrentIndex(1)
        callback.assert_called_once_with("details")
        self.assertEqual(
            navigator.selector.itemData(1, Qt.ItemDataRole.AccessibleTextRole),
            "Technical details and history",
        )

    def test_local_view_switcher_has_no_route_semantics(self) -> None:
        switcher = LocalViewSwitcher()
        switcher.set_views(
            [
                LocalViewItem("overview", "Overview", "Current summary"),
                LocalViewItem("history", "History", "Saved checks"),
            ]
        )
        callback = MagicMock()
        switcher.viewActivated.connect(callback)

        self.assertEqual(switcher.view_ids(), ("overview", "history"))
        switcher.button_group.button(1).click()
        callback.assert_called_once_with("history")
        self.assertEqual(switcher.active_view_id(), "history")
        self.assertFalse(hasattr(switcher, "routeRequested"))

        switcher.set_compact(True)
        self.assertTrue(switcher.is_compact())
        self.assertFalse(switcher.button_row.isVisible())

        with self.assertRaises(ValueError):
            switcher.set_views([LocalViewItem("only", "Only")])


class TestContentComponents(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def test_scaffold_has_no_duplicate_shell_header(self) -> None:
        scaffold = PageScaffold("System content", "Caller-owned content")
        self.assertEqual(scaffold.findChildren(PageHeader), [])
        self.assertEqual(scaffold.accessibleName(), "System content")
        self.assertEqual(scaffold.content.maximumWidth(), 1120)

    def test_header_hides_redundant_eyebrow_and_hosts_actions(self) -> None:
        header = PageHeader()
        header.set_content("System", "System", "Current system details")
        action = SecondaryButton("Export", description="Export existing report")
        header.add_action(action, primary=True)

        self.assertFalse(header.eyebrow.isVisible())
        self.assertEqual(header.title.text(), "System")
        self.assertTrue(header.description.wordWrap())
        self.assertEqual(action.accessibleName(), "Export")

        header.set_content("Software & Updates", "Updates", "Review available updates")
        self.assertFalse(header.eyebrow.isHidden())

    def test_action_bar_clear_restores_caller_ownership_and_allows_reuse(self) -> None:
        owner = QWidget()
        action = SecondaryButton("Export", parent=owner)
        bar = ActionBar()

        bar.add_action(action, primary=True)
        self.assertIs(action.parentWidget(), bar)
        bar.clear_actions()
        self.assertIs(action.parentWidget(), owner)
        self.assertFalse(action.isVisible())
        bar.add_action(action, primary=True)
        self.assertIs(action.parentWidget(), bar)

    def test_adaptive_grid_supports_explicit_responsive_breakpoints(self) -> None:
        grid = AdaptiveGrid(column_breakpoints=((0, 1), (360, 2), (760, 4)))
        for index in range(4):
            grid.add_card(QLabel(str(index)))

        grid._reflow(320)
        self.assertEqual(grid._columns, 1)
        grid._reflow(600)
        self.assertEqual(grid._columns, 2)
        grid._reflow(900)
        self.assertEqual(grid._columns, 4)

    def test_definition_rows_keep_labels_near_selectable_values(self) -> None:
        definitions = DefinitionList("System properties")
        row = definitions.add_row("Operating system", "Fedora Linux", copyable=True)
        copied = MagicMock()
        row.copyRequested.connect(copied)

        self.assertTrue(row.value.textInteractionFlags() & Qt.TextInteractionFlag.TextSelectableByKeyboard)
        row.copy_button.click()
        copied.assert_called_once_with("Fedora Linux")
        row.set_value("Fedora Linux 44")
        self.assertEqual(row.value.text(), "Fedora Linux 44")
        self.assertEqual(row.accessibleDescription(), "Fedora Linux 44")


if __name__ == "__main__":
    unittest.main()
