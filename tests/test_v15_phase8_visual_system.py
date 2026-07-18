"""Phase 8 visual-system, shared-state, and accessibility contracts."""

from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock

from PyQt6.QtCore import Qt
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QApplication, QWidget

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "loofi-fedora-tweaks"))

from core.home.service import _COMMON_TASKS
from ui.layout_primitives import AdaptiveGrid, LayoutMetrics, RouteCard
from ui.icon_pack import resolve_icon_path
from ui.shared_states import (
    ActionProgress,
    DetailsDisclosure,
    EmptyState,
    LoadingState,
    ResultBanner,
    UnavailableState,
)


class TestSharedStates(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_message_states_expose_textual_accessibility(self):
        loading = LoadingState("Reading saved status")
        empty = EmptyState("Nothing to review", "Run a refresh later")
        unavailable = UnavailableState("Not available", "Install the required tool")

        self.assertEqual(loading.property("presentationState"), "loading")
        self.assertEqual(empty.accessibleName(), "Nothing to review")
        self.assertEqual(empty.accessibleDescription(), "Run a refresh later")
        self.assertEqual(unavailable.property("presentationState"), "unavailable")

    def test_result_and_progress_encode_state_without_color_only(self):
        banner = ResultBanner("Completed", "No changes were needed", kind="success")
        progress = ActionProgress("Working")

        self.assertEqual(banner.property("resultKind"), "success")
        self.assertEqual(banner.title_label.text(), "Completed")
        self.assertEqual(progress.progress_bar.maximum(), 0)
        progress.set_progress(120, "Finished")
        self.assertEqual(progress.progress_bar.value(), 100)
        self.assertEqual(progress.status_label.text(), "Finished")

    def test_details_disclosure_is_keyboard_operable(self):
        disclosure = DetailsDisclosure("command output")
        disclosure.show()
        disclosure.toggle_button.setFocus()

        QTest.keyClick(disclosure.toggle_button, Qt.Key.Key_Space)

        self.assertTrue(disclosure.details.isVisible())
        self.assertEqual(disclosure.details.toPlainText(), "command output")


class TestAccessibleRouteCard(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_enter_space_and_mouse_emit_route_signal(self):
        card = RouteCard("Updates", "Review available updates", "maintenance:updates")
        callback = MagicMock()
        card.activated.connect(callback)
        card.resize(320, 120)
        card.show()
        card.setFocus()

        QTest.keyClick(card, Qt.Key.Key_Return)
        QTest.keyClick(card, Qt.Key.Key_Space)
        QTest.mouseClick(card, Qt.MouseButton.LeftButton, pos=card.rect().center())

        self.assertEqual(callback.call_count, 3)
        callback.assert_called_with("maintenance:updates")
        self.assertEqual(card.focusPolicy(), Qt.FocusPolicy.StrongFocus)
        self.assertEqual(card.accessibleName(), "Updates")

    def test_optional_qt_events_are_ignored_safely(self):
        card = RouteCard("Updates", "Review available updates", "maintenance:updates")
        callback = MagicMock()
        card.activated.connect(callback)

        card.keyPressEvent(None)
        card.mouseReleaseEvent(None)

        callback.assert_not_called()


class TestResponsiveMatrix(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_supported_sizes_and_font_scales_keep_adaptive_layout(self):
        matrix = (
            (860, 720, 1.0),
            (1280, 720, 1.0),
            (1366, 768, 1.0),
            (1920, 1080, 1.0),
            (1920, 1080, 1.25),
            (2560, 1440, 1.25),
            (2560, 1440, 1.5),
            (2560, 1440, 2.0),
        )

        for width, height, scale in matrix:
            with self.subTest(width=width, height=height, scale=scale):
                grid = AdaptiveGrid(min_column_width=260)
                font = grid.font()
                font.setPointSizeF(max(8.0, font.pointSizeF() * scale))
                grid.setFont(font)
                for index in range(4):
                    grid.add_card(RouteCard(f"Task {index}", "Open a maintained route", str(index)))
                grid.resize(max(1, width - 240), height)
                grid._reflow(grid.width())
                metrics = LayoutMetrics.from_widget(grid)

                self.assertEqual(grid.count(), 4)
                self.assertGreaterEqual(grid._columns, 2)
                self.assertLess(metrics.page_margin * 2, width)
                self.assertLess(metrics.header_height, height)


class TestQssContracts(unittest.TestCase):
    def test_common_home_tasks_use_packaged_semantic_icons(self):
        for task in _COMMON_TASKS:
            with self.subTest(task=task.id):
                self.assertIsNotNone(resolve_icon_path(task.icon_id))

    def test_structural_theme_uses_system_font_and_real_sidebar_type(self):
        root = Path(__file__).parents[1] / "loofi-fedora-tweaks" / "assets"
        text = (root / "base.qss").read_text()
        global_widget_rule = text.split("QWidget {", 1)[1].split("}", 1)[0]
        self.assertNotIn("font-family:", global_widget_rule)
        self.assertNotIn("font-size:", global_widget_rule)
        self.assertNotIn("QListWidget#destinationSidebar", text)
        self.assertIn("QTreeWidget#destinationSidebar", text)
        self.assertIn('QFrame[routeCard="true"]:focus', text)
        self.assertIn("QFrame#resultBanner", text)

    def test_ui_labels_do_not_embed_ordinary_emoji(self):
        ui_root = Path(__file__).parents[1] / "loofi-fedora-tweaks" / "ui"
        sources = "\n".join(
            path.read_text()
            for path in ui_root.glob("*.py")
            if path.name != "icon_pack.py"
        )

        ordinary_emoji = [
            character
            for character in sources
            if character == "\u2139"
            or "\u2600" <= character <= "\u27ff"
            or "\U0001F300" <= character <= "\U0001FAFF"
        ]
        self.assertEqual(ordinary_emoji, [])


if __name__ == "__main__":
    unittest.main()
