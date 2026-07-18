"""Focused contracts for the v16 semantic theme engine."""

from __future__ import annotations

import os
import re
import sys
import tempfile
import unittest
from pathlib import Path

from PyQt6.QtGui import QColor, QPalette

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "loofi-fedora-tweaks"))

from ui.design import DesignTokens, ThemeManager, contrast_ratio


class _ApplicationFixture:
    def __init__(self, palette: QPalette) -> None:
        self._palette = palette
        self.stylesheet = ""
        self.properties: dict[str, str] = {}

    def palette(self) -> QPalette:
        return self._palette

    def setStyleSheet(self, stylesheet: str) -> None:
        self.stylesheet = stylesheet

    def setProperty(self, name: str, value: str) -> None:
        self.properties[name] = value


class TestDesignTokens(unittest.TestCase):
    def test_baseline_geometry_matches_phase_contract(self) -> None:
        tokens = DesignTokens()

        self.assertEqual(
            (tokens.space_1, tokens.space_2, tokens.space_3, tokens.space_4, tokens.space_6, tokens.space_8),
            (4, 8, 12, 16, 24, 32),
        )
        self.assertEqual(tokens.navigation_row_min_height, 44)
        self.assertEqual(tokens.control_min_height, 36)
        self.assertEqual(tokens.radius_card, 10)
        self.assertEqual(tokens.content_max_width, 1120)
        self.assertGreaterEqual(tokens.readable_line_length, 65)
        self.assertLessEqual(tokens.readable_line_length, 90)

    def test_typography_roles_do_not_override_system_font(self) -> None:
        values = DesignTokens().qss_values()

        self.assertNotIn("font_family", values)
        self.assertEqual(values["code_family"], "monospace")


class TestSemanticPalettes(unittest.TestCase):
    def test_explicit_theme_fixtures_satisfy_contrast_contracts(self) -> None:
        for name in ("dark", "light", "highcontrast"):
            with self.subTest(theme=name):
                palette = ThemeManager.explicit_palette(name)
                self.assertEqual(palette.contrast_failures(), {})

    def test_state_and_interaction_tokens_are_present(self) -> None:
        palette = ThemeManager.explicit_palette("dark")

        for token in (
            "focus",
            "disabled_surface",
            "disabled_text",
            "hover",
            "selected",
            "warning",
            "warning_surface",
            "warning_text",
            "success",
            "success_surface",
            "success_text",
            "error",
            "error_surface",
            "error_text",
        ):
            self.assertTrue(getattr(palette, token))

    def test_contrast_helper_uses_wcag_ratio(self) -> None:
        self.assertEqual(contrast_ratio("#000000", "#ffffff"), 21.0)
        self.assertAlmostEqual(contrast_ratio("#ffffff", "#ffffff"), 1.0)

    def test_system_palette_uses_qpalette_roles(self) -> None:
        qt_palette = QPalette()
        qt_palette.setColor(QPalette.ColorRole.Window, QColor("#f7f8fa"))
        qt_palette.setColor(QPalette.ColorRole.Base, QColor("#ffffff"))
        qt_palette.setColor(QPalette.ColorRole.AlternateBase, QColor("#eef1f5"))
        qt_palette.setColor(QPalette.ColorRole.WindowText, QColor("#17212d"))
        qt_palette.setColor(QPalette.ColorRole.PlaceholderText, QColor("#4b5a6c"))
        qt_palette.setColor(QPalette.ColorRole.Mid, QColor("#78879a"))
        qt_palette.setColor(QPalette.ColorRole.Button, QColor("#e5eaf0"))
        qt_palette.setColor(QPalette.ColorRole.Highlight, QColor("#d0e7ff"))
        qt_palette.setColor(QPalette.ColorRole.Link, QColor("#005ea8"))
        qt_palette.setColor(QPalette.ColorRole.HighlightedText, QColor("#ffffff"))

        palette = ThemeManager.system_palette(qt_palette)

        self.assertEqual(palette.window, "#f7f8fa")
        self.assertEqual(palette.surface, "#ffffff")
        self.assertEqual(palette.surface_raised, "#eef1f5")
        self.assertEqual(palette.accent, "#005ea8")
        self.assertEqual(palette.contrast_failures(), {})


class TestThemeManager(unittest.TestCase):
    def test_all_themes_render_the_same_structural_contract(self) -> None:
        manager = ThemeManager()
        signatures = []
        structural_stylesheets = []

        for name in manager.SUPPORTED_THEMES:
            stylesheet = manager.stylesheet(name)
            signatures.append(manager.tokens.geometry_signature())
            structural_stylesheets.append(
                re.sub(r"#[0-9a-fA-F]{6}", "#semantic", stylesheet)
            )
            self.assertNotIn("$color_", stylesheet)
            self.assertIn('QFrame[routeCard="true"]:focus', stylesheet)
            self.assertIn("QTreeWidget#destinationSidebar::item:selected", stylesheet)
            self.assertNotIn("QListWidget#destinationSidebar", stylesheet)
            self.assertIn('QFrame#resultBanner[resultKind="warning"]', stylesheet)

        self.assertTrue(all(signature == signatures[0] for signature in signatures))
        self.assertTrue(
            all(stylesheet == structural_stylesheets[0] for stylesheet in structural_stylesheets)
        )

    def test_structural_qss_keeps_global_system_font(self) -> None:
        stylesheet = ThemeManager().stylesheet("light")
        global_widget_rule = stylesheet.split("QWidget {", 1)[1].split("}", 1)[0]

        self.assertNotIn("font-family", global_widget_rule)
        self.assertNotIn("font-size", global_widget_rule)

    def test_apply_retains_structure_in_system_mode(self) -> None:
        app = _ApplicationFixture(QPalette())

        applied = ThemeManager().apply(app, "system")

        self.assertTrue(applied)
        self.assertIn("QFrame#contentSection", app.stylesheet)
        self.assertIn("QFrame#resultBanner", app.stylesheet)
        self.assertIn("QTreeWidget#destinationSidebar", app.stylesheet)
        self.assertEqual(app.properties["loofiTheme"], "system")

    def test_unknown_theme_falls_back_to_dark(self) -> None:
        manager = ThemeManager()

        self.assertEqual(manager.palette_for("unknown"), manager.explicit_palette("dark"))

    def test_missing_base_stylesheet_fails_without_clearing_current_style(self) -> None:
        app = _ApplicationFixture(QPalette())
        app.stylesheet = "existing"
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = ThemeManager(base_qss_path=Path(tmpdir) / "missing.qss")

            self.assertFalse(manager.apply(app, "dark"))
            self.assertEqual(app.stylesheet, "existing")

    def test_runtime_ui_has_no_direct_product_colours_outside_palette_source(self) -> None:
        ui_root = Path(__file__).parents[1] / "loofi-fedora-tweaks" / "ui"
        direct_colour = re.compile(
            r"#[0-9a-fA-F]{3,8}|QColor\(\s*\d+\s*,\s*\d+\s*,\s*\d+"
        )
        violations = []
        for path in ui_root.rglob("*.py"):
            if path.parent.name == "design":
                continue
            for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
                if direct_colour.search(line):
                    violations.append(f"{path.relative_to(ui_root)}:{line_number}")

        self.assertEqual(violations, [])

    def test_runtime_theme_path_does_not_load_legacy_qss_files(self) -> None:
        source_root = Path(__file__).parents[1] / "loofi-fedora-tweaks"
        runtime_source = "\n".join(
            (source_root / relative).read_text(encoding="utf-8")
            for relative in ("main.py", "ui/main_window.py", "ui/design/theme_manager.py")
        )
        for legacy_name in ("modern.qss", "light.qss", "highcontrast.qss"):
            self.assertNotIn(legacy_name, runtime_source)


if __name__ == "__main__":
    unittest.main()
