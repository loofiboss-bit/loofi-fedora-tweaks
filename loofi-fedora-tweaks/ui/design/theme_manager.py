"""Semantic palettes and structural QSS rendering for the PyQt application."""

from __future__ import annotations

import logging
from dataclasses import asdict, dataclass
from pathlib import Path
from string import Template
from typing import Any

from ui.design.tokens import DesignTokens

logger = logging.getLogger(__name__)


def _rgb(value: str) -> tuple[int, int, int]:
    text = value.lstrip("#")
    if len(text) != 6:
        raise ValueError(f"Expected #RRGGBB colour, got {value!r}")
    return tuple(int(text[index:index + 2], 16) for index in (0, 2, 4))  # type: ignore[return-value]


def _relative_luminance(value: str) -> float:
    channels = []
    for channel in _rgb(value):
        normalized = channel / 255.0
        channels.append(
            normalized / 12.92
            if normalized <= 0.04045
            else ((normalized + 0.055) / 1.055) ** 2.4
        )
    return (0.2126 * channels[0]) + (0.7152 * channels[1]) + (0.0722 * channels[2])


def contrast_ratio(foreground: str, background: str) -> float:
    """Return the WCAG contrast ratio for two ``#RRGGBB`` colours."""
    lighter, darker = sorted(
        (_relative_luminance(foreground), _relative_luminance(background)),
        reverse=True,
    )
    return (lighter + 0.05) / (darker + 0.05)


@dataclass(frozen=True)
class SemanticPalette:
    """Complete semantic colour contract consumed by ``base.qss``."""

    window: str
    surface: str
    surface_raised: str
    text: str
    text_muted: str
    border: str
    hover: str
    selected: str
    accent: str
    accent_text: str
    focus: str
    disabled_surface: str
    disabled_text: str
    success: str
    success_surface: str
    success_text: str
    warning: str
    warning_surface: str
    warning_text: str
    error: str
    error_surface: str
    error_text: str

    def qss_values(self) -> dict[str, str]:
        return {f"color_{key}": value for key, value in asdict(self).items()}

    def contrast_failures(self) -> dict[str, float]:
        """Return semantic pairs below the v16 accessibility targets."""
        pairs = {
            "text": (self.text, self.window, 4.5),
            "muted_text": (self.text_muted, self.window, 4.5),
            "accent_text": (self.accent_text, self.accent, 4.5),
            "focus": (self.focus, self.window, 3.0),
            "selected": (self.accent, self.selected, 3.0),
            "success": (self.success, self.success_surface, 3.0),
            "success_text": (self.success_text, self.success_surface, 4.5),
            "warning": (self.warning, self.warning_surface, 3.0),
            "warning_text": (self.warning_text, self.warning_surface, 4.5),
            "error": (self.error, self.error_surface, 3.0),
            "error_text": (self.error_text, self.error_surface, 4.5),
        }
        return {
            name: contrast_ratio(foreground, background)
            for name, (foreground, background, minimum) in pairs.items()
            if contrast_ratio(foreground, background) < minimum
        }


_DARK = SemanticPalette(
    window="#141823",
    surface="#1d2331",
    surface_raised="#283145",
    text="#f2f5fc",
    text_muted="#b0bdd2",
    border="#62728d",
    hover="#283145",
    selected="#30304f",
    accent="#a59aff",
    accent_text="#141823",
    focus="#83b9ff",
    disabled_surface="#242a33",
    disabled_text="#8995a5",
    success="#63d99b",
    success_surface="#143b2a",
    success_text="#c9f7dc",
    warning="#f2c14e",
    warning_surface="#49370e",
    warning_text="#ffecb5",
    error="#ff8a92",
    error_surface="#4b1f25",
    error_text="#ffd9dc",
)

_LIGHT = SemanticPalette(
    window="#f4f6fb",
    surface="#ffffff",
    surface_raised="#e9edf7",
    text="#182034",
    text_muted="#556178",
    border="#7b89a0",
    hover="#e9edf7",
    selected="#e6e2ff",
    accent="#5b4fd6",
    accent_text="#ffffff",
    focus="#3f6ae0",
    disabled_surface="#e5e9ee",
    disabled_text="#657386",
    success="#197541",
    success_surface="#d9f4e4",
    success_text="#124c2d",
    warning="#815d00",
    warning_surface="#fff0bf",
    warning_text="#543d00",
    error="#b4232f",
    error_surface="#ffe0e3",
    error_text="#721822",
)

_HIGH_CONTRAST = SemanticPalette(
    window="#000000",
    surface="#000000",
    surface_raised="#101010",
    text="#ffffff",
    text_muted="#ffffff",
    border="#ffffff",
    hover="#262626",
    selected="#001a80",
    accent="#ffff00",
    accent_text="#000000",
    focus="#ffff00",
    disabled_surface="#1f1f1f",
    disabled_text="#b8b8b8",
    success="#00ff80",
    success_surface="#002b16",
    success_text="#ffffff",
    warning="#ffff00",
    warning_surface="#332b00",
    warning_text="#ffffff",
    error="#ff7070",
    error_surface="#3d0000",
    error_text="#ffffff",
)


def current_palette() -> SemanticPalette:
    """Return the palette applied to the running app, or a safe dark fixture."""
    try:
        from PyQt6.QtWidgets import QApplication

        application = QApplication.instance()
        if application is not None:
            palette = application.property("loofiSemanticPalette")
            if isinstance(palette, SemanticPalette):
                return palette
    except (ImportError, AttributeError, RuntimeError, TypeError):
        pass
    return _DARK


def semantic_color(role: str) -> str:
    """Resolve a semantic role to its current ``#RRGGBB`` value."""
    palette = current_palette()
    if role not in palette.__dataclass_fields__:
        raise KeyError(f"Unknown semantic colour role: {role!r}")
    return str(getattr(palette, role))


def semantic_qcolor(role: str, alpha: int | None = None) -> Any:
    """Resolve a semantic role to QColor, optionally overriding alpha."""
    from PyQt6.QtGui import QColor

    color = QColor(semantic_color(role))
    if alpha is not None:
        color.setAlpha(max(0, min(255, alpha)))
    return color


class ThemeManager:
    """Render one structural stylesheet with a selected semantic palette."""

    SUPPORTED_THEMES = ("system", "dark", "light", "highcontrast")

    def __init__(
        self,
        base_qss_path: Path | None = None,
        tokens: DesignTokens | None = None,
    ) -> None:
        self.base_qss_path = base_qss_path or (
            Path(__file__).resolve().parents[2] / "assets" / "base.qss"
        )
        self.tokens = tokens or DesignTokens()

    @staticmethod
    def explicit_palette(name: str) -> SemanticPalette:
        """Return a validated explicit theme fixture."""
        return {
            "dark": _DARK,
            "light": _LIGHT,
            "highcontrast": _HIGH_CONTRAST,
        }.get(name, _DARK)

    @staticmethod
    def _qt_colour(qt_palette: Any, role: Any, fallback: str) -> str:
        try:
            colour = qt_palette.color(role)
            if hasattr(colour, "name"):
                value = str(colour.name())
                if len(value) == 7 and value.startswith("#"):
                    return value.lower()
        except (AttributeError, RuntimeError, TypeError, ValueError):
            pass
        return fallback

    @classmethod
    def system_palette(cls, qt_palette: Any) -> SemanticPalette:
        """Select the Loofi palette from the desktop's light or dark mode.

        Desktop palette colours determine brightness only. Keeping the complete
        Loofi palette makes all application surfaces and states consistent even
        when the desktop uses custom accent or low-contrast colours.
        """
        if qt_palette is None:
            return _DARK
        try:
            from PyQt6.QtGui import QPalette

            window = cls._qt_colour(qt_palette, QPalette.ColorRole.Window, _DARK.window)
        except (ImportError, AttributeError):
            return _DARK
        return _DARK if _relative_luminance(window) < 0.35 else _LIGHT

    def palette_for(self, name: str, qt_palette: Any = None) -> SemanticPalette:
        normalized = name if name in self.SUPPORTED_THEMES else "dark"
        if normalized == "system":
            return self.system_palette(qt_palette)
        return self.explicit_palette(normalized)

    def stylesheet(self, name: str, qt_palette: Any = None) -> str:
        """Render the invariant structural stylesheet for one palette."""
        template = Template(self.base_qss_path.read_text(encoding="utf-8"))
        values = self.tokens.qss_values()
        values.update(self.palette_for(name, qt_palette).qss_values())
        return template.substitute(values)

    def apply(self, application: Any, name: str) -> bool:
        """Apply a theme to a QApplication-like object without changing its font."""
        qt_palette = application.palette() if name == "system" and hasattr(application, "palette") else None
        if hasattr(application, "property") and hasattr(application, "setProperty"):
            native_palette = application.property("loofiDesktopPalette")
            if native_palette is None and hasattr(application, "palette"):
                native_palette = application.palette()
                application.setProperty("loofiDesktopPalette", native_palette)
            if name == "system" and native_palette is not None:
                qt_palette = native_palette
        try:
            palette = self.palette_for(name, qt_palette)
            if name == "system" and hasattr(application, "styleHints"):
                from PyQt6.QtCore import Qt
                hints = application.styleHints()
                scheme = hints.colorScheme() if hints is not None else Qt.ColorScheme.Unknown
                if scheme == Qt.ColorScheme.Dark:
                    palette = _DARK
                elif scheme == Qt.ColorScheme.Light:
                    palette = _LIGHT
            template = Template(self.base_qss_path.read_text(encoding="utf-8"))
            values = self.tokens.qss_values()
            values.update(palette.qss_values())
            stylesheet = template.substitute(values)
        except (OSError, KeyError, ValueError):
            logger.debug("Failed to render structural theme stylesheet", exc_info=True)
            return False
        application.setStyleSheet(stylesheet)
        if hasattr(application, "setProperty"):
            application.setProperty("loofiTheme", name if name in self.SUPPORTED_THEMES else "dark")
            application.setProperty("loofiSemanticPalette", palette)
        return True
