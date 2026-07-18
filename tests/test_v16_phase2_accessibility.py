"""Accessibility, theme, and font-scale matrix for v16 Phase 2."""

from __future__ import annotations

import os
import sys
import unittest
from unittest.mock import MagicMock

from PyQt6.QtCore import Qt, QThread, QTimer
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QApplication, QWidget

TEST_ROOT = os.path.dirname(__file__)
sys.path.insert(0, TEST_ROOT)
sys.path.insert(0, os.path.join(TEST_ROOT, "..", "loofi-fedora-tweaks"))

from support.v16_component_gallery import ComponentGallery
from ui.components import (
    ActionProgress,
    DetailsDisclosure,
    EmptyState,
    InlineNotice,
    StatusBadge,
)
from ui.design import DesignTokens, ThemeManager


class TestFeedbackAccessibility(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def test_badges_and_notices_use_text_icon_and_semantic_property(self) -> None:
        for kind in ("info", "success", "warning", "error", "neutral", "unknown"):
            with self.subTest(kind=kind):
                badge = StatusBadge("Saved state", kind=kind, description="Current result")
                expected = kind if kind != "unknown" else "info"
                self.assertEqual(badge.property("statusKind"), expected)
                self.assertEqual(badge.text_label.text(), "Saved state")
                self.assertFalse(badge.icon_label.pixmap().isNull())
                self.assertEqual(badge.accessibleName(), "Saved state")
                self.assertEqual(badge.accessibleDescription(), "Current result")

                notice = InlineNotice("Result", "Plain-language detail", kind=kind)
                self.assertEqual(notice.property("noticeKind"), expected)
                self.assertFalse(notice.icon_label.pixmap().isNull())
                notice.set_notice("success", "Completed", "No changes were needed")
                self.assertEqual(notice.accessibleName(), "Completed")
                self.assertEqual(notice.accessibleDescription(), "No changes were needed")

    def test_empty_action_and_disclosure_are_keyboard_operable(self) -> None:
        empty = EmptyState(
            "No results",
            "Change the filter to continue",
            action_text="Clear filter",
        )
        action = MagicMock()
        empty.actionRequested.connect(action)
        empty.show()
        empty.action_button.setFocus()
        QTest.keyClick(empty.action_button, Qt.Key.Key_Space)
        action.assert_called_once()

        disclosure = DetailsDisclosure("technical output", summary="Show operation details")
        disclosure.show()
        disclosure.toggle_button.setFocus()
        QTest.keyClick(disclosure.toggle_button, Qt.Key.Key_Space)
        self.assertTrue(disclosure.details.isVisible())
        self.assertEqual(disclosure.toggle_button.text(), "Hide details")
        self.assertEqual(
            disclosure.toggle_button.accessibleDescription(),
            "Hide technical details",
        )

    def test_progress_is_bounded_and_textually_announced(self) -> None:
        progress = ActionProgress("Starting")
        progress.set_progress(140, "Finished")
        self.assertEqual(progress.progress_bar.value(), 100)
        self.assertEqual(progress.status_label.text(), "Finished")
        self.assertIn("100", progress.accessibleDescription())
        self.assertIn("Finished", progress.accessibleDescription())

    def test_disclosure_can_own_caller_content_without_changing_behavior(self) -> None:
        disclosure = DetailsDisclosure(summary="Show command output")
        output = QWidget()
        disclosure.add_widget(output)
        disclosure.show()
        self.app.processEvents()

        self.assertFalse(output.isVisible())
        disclosure.toggle_button.click()
        self.app.processEvents()
        self.assertTrue(output.isVisible())
        self.assertFalse(disclosure.details.isVisible())


class TestComponentGalleryMatrix(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def test_all_themes_and_supported_font_scales_render_gallery(self) -> None:
        manager = ThemeManager()
        signatures = []
        for theme in manager.SUPPORTED_THEMES:
            self.assertTrue(manager.apply(self.app, theme))
            signatures.append(manager.tokens.geometry_signature())
            for scale in (1.0, 1.25, 1.4, 1.5, 2.0):
                with self.subTest(theme=theme, scale=scale):
                    gallery = ComponentGallery()
                    font = gallery.font()
                    base_size = font.pointSizeF() if font.pointSizeF() > 0 else 10.0
                    font.setPointSizeF(base_size * scale)
                    gallery.setFont(font)
                    gallery.resize(1280, 1800)
                    gallery.show()
                    self.app.processEvents()

                    self.assertEqual(gallery.navigator.rail.horizontalScrollBarPolicy(), Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
                    self.assertGreaterEqual(gallery.navigator.rail.sizeHintForRow(0), 44)
                    self.assertEqual(gallery.scaffold.content.maximumWidth(), 1120)
                    self.assertEqual(gallery.findChildren(QTimer), [])
                    self.assertEqual(gallery.findChildren(QThread), [])
                    self.assertTrue(gallery.header.title.text())
                    self.assertTrue(gallery.clickable_card.accessibleName())
                    self.assertTrue(gallery.primary_button.accessibleDescription())
                    gallery.close()

        self.assertTrue(all(signature == signatures[0] for signature in signatures))

    def test_gallery_supports_explicit_minimum_width_selector_mode(self) -> None:
        gallery = ComponentGallery()
        gallery.resize(860, 1400)
        gallery.navigator.set_compact(True)
        gallery.show()
        self.app.processEvents()

        self.assertTrue(gallery.navigator.selector.isVisible())
        for index in range(gallery.navigator.selector.count()):
            self.assertTrue(gallery.navigator.selector.itemText(index))
            self.assertTrue(
                gallery.navigator.selector.itemData(
                    index,
                    Qt.ItemDataRole.AccessibleTextRole,
                )
            )

    def test_component_geometry_matches_phase_tokens(self) -> None:
        gallery = ComponentGallery()
        tokens = DesignTokens()
        for button in (
            gallery.primary_button,
            gallery.secondary_button,
            gallery.ghost_button,
            gallery.danger_button,
        ):
            self.assertGreaterEqual(button.minimumWidth(), tokens.control_min_height)
            self.assertGreaterEqual(button.minimumHeight(), tokens.control_min_height)
        self.assertEqual(gallery.scaffold.content.maximumWidth(), tokens.content_max_width)


if __name__ == "__main__":
    unittest.main()
