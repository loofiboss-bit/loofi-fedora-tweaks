"""Phase 7 real-shell validation and accessibility contracts."""

from __future__ import annotations

import importlib.util
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtCore import Qt
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QApplication, QDialog, QPushButton, QSizePolicy, QWidget

from ui.confirm_dialog import ConfirmActionDialog
from ui.components.layout import AdaptiveGrid, ContentColumn, PageScaffold
from ui.main_window import MainWindow


ROOT = Path(__file__).parents[1]
SCRIPT = ROOT / "scripts" / "validate_v16_phase7_ui.py"


def _load_validator():
    spec = importlib.util.spec_from_file_location("v16_phase7_validator", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class TestPhase7MatrixContract(unittest.TestCase):
    def test_matrix_is_the_complete_theme_mode_size_scale_locale_product(self) -> None:
        validator = _load_validator()
        matrix = validator.build_automated_matrix()

        self.assertEqual(len(matrix), 400)
        self.assertEqual({case.theme for case in matrix}, set(validator.THEMES))
        self.assertEqual({case.navigation_mode for case in matrix}, set(validator.NAVIGATION_MODES))
        self.assertEqual({case.viewport for case in matrix}, set(validator.VIEWPORTS))
        self.assertEqual({case.scale_percent for case in matrix}, set(validator.FONT_SCALES))
        self.assertEqual({case.locale_fixture for case in matrix}, set(validator.LOCALE_FIXTURES))

    def test_catalog_samples_every_axis_and_standard_destination(self) -> None:
        validator = _load_validator()
        catalog = validator.build_catalog_matrix()

        self.assertEqual(len(catalog), 24)
        self.assertEqual({case.theme for case in catalog}, set(validator.THEMES))
        self.assertEqual({case.navigation_mode for case in catalog}, set(validator.NAVIGATION_MODES))
        self.assertEqual({case.viewport for case in catalog}, set(validator.VIEWPORTS))
        self.assertEqual({case.scale_percent for case in catalog}, set(validator.FONT_SCALES))
        self.assertEqual({case.locale_fixture for case in catalog}, set(validator.LOCALE_FIXTURES))
        self.assertTrue(set(validator.STANDARD_ROUTES).issubset({case.route_id for case in catalog}))

    def test_static_release_contract_is_complete(self) -> None:
        validator = _load_validator()
        self.assertEqual(validator.validate_static_contract(), [])

    def test_product_and_stress_fixtures_are_english_only(self) -> None:
        validator = _load_validator()
        self.assertEqual(validator.LOCALE_FIXTURES, ("en", "en-long"))
        self.assertFalse(
            (ROOT / "loofi-fedora-tweaks" / "resources" / "translations" / "sv.ts").exists()
        )
        main_source = (ROOT / "loofi-fedora-tweaks" / "main.py").read_text(
            encoding="utf-8"
        )
        self.assertNotIn("QTranslator", main_source)


class TestPhase7AccessibleSurfaces(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    @patch("ui.main_window.MainWindow._check_first_run")
    @patch("ui.main_window.MainWindow._initialize_background_services")
    @patch("ui.main_window.MainWindow._schedule_post_render_services")
    def test_real_main_window_exposes_shell_and_result_state(
        self,
        _mock_post_render,
        _mock_background,
        _mock_first_run,
    ) -> None:
        window = MainWindow()
        window.show()
        self.app.processEvents()
        try:
            self.assertEqual(window.accessibleName(), "Loofi Fedora Tweaks")
            self.assertTrue(window.accessibleDescription())
            self.assertTrue(window.sidebar.accessibleName())
            self.assertTrue(window.destination_host.navigator.accessibleName())
            self.assertTrue(window._breadcrumb_frame.accessibleName())

            window.set_status("Validation completed")
            self.assertEqual(window._status_label.accessibleName(), "Activity status")
            self.assertEqual(
                window._status_label.accessibleDescription(),
                "Validation completed",
            )
        finally:
            window.close()
            window.deleteLater()
            self.app.processEvents()

    def test_confirmation_dialog_is_named_and_keyboard_dismissible(self) -> None:
        dialog = ConfirmActionDialog(
            action="Remove selected packages",
            description="Review the package list before continuing.",
            command_preview="dnf remove example",
            risk_level=ConfirmActionDialog.RISK_HIGH,
        )
        dialog.show()
        self.app.processEvents()
        try:
            self.assertIn("Remove selected packages", dialog.accessibleName())
            self.assertEqual(
                dialog.accessibleDescription(),
                "Review the package list before continuing.",
            )
            focusable = [
                button
                for button in dialog.findChildren(QPushButton)
                if button.focusPolicy() != Qt.FocusPolicy.NoFocus
            ]
            self.assertTrue(focusable)
            self.assertTrue(all(button.accessibleName() or button.text() for button in focusable))

            QTest.keyClick(dialog, Qt.Key.Key_Escape)
            self.app.processEvents()
            self.assertEqual(dialog.result(), QDialog.DialogCode.Rejected)
        finally:
            dialog.close()
            dialog.deleteLater()

    def test_application_page_wrapper_disables_horizontal_scrolling(self) -> None:
        scroll = MainWindow._wrap_page_widget(object(), QWidget())

        self.assertEqual(
            scroll.horizontalScrollBarPolicy(),
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff,
        )
        scroll.deleteLater()

    def test_shared_page_layout_can_shrink_before_grids_reflow(self) -> None:
        widgets = (ContentColumn(), PageScaffold(), AdaptiveGrid())

        for widget in widgets:
            with self.subTest(widget=widget.__class__.__name__):
                self.assertEqual(
                    widget.sizePolicy().horizontalPolicy(),
                    QSizePolicy.Policy.Ignored,
                )
                widget.deleteLater()


if __name__ == "__main__":
    unittest.main()
