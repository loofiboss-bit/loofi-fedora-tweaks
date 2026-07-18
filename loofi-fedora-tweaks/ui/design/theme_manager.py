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


def _mix(start: str, end: str, amount: float) -> str:
    start_rgb = _rgb(start)
    end_rgb = _rgb(end)
    channels = [round(a + ((b - a) * amount)) for a, b in zip(start_rgb, end_rgb)]
    return "#" + "".join(f"{channel:02x}" for channel in channels)


def _ensure_contrast(foreground: str, background: str, minimum: float) -> str:
    if contrast_ratio(foreground, background) >= minimum:
        return foreground.lower()
    black_ratio = contrast_ratio("#000000", background)
    white_ratio = contrast_ratio("#ffffff", background)
    target = "#000000" if black_ratio >= white_ratio else "#ffffff"
    for step in range(1, 21):
        candidate = _mix(foreground, target, step / 20.0)
        if contrast_ratio(candidate, background) >= minimum:
            return candidate
    return target


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
    window="#12161d",
    surface="#181d26",
    surface_raised="#202734",
    text="#f0f3f7",
    text_muted="#b7c0cc",
    border="#526073",
    hover="#252d39",
    selected="#183f61",
    accent="#79c1ff",
    accent_text="#07131f",
    focus="#8dcbff",
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
    window="#f5f7fa",
    surface="#ffffff",
    surface_raised="#eef2f7",
    text="#17212d",
    text_muted="#4b5a6c",
    border="#8a98a9",
    hover="#e2e9f1",
    selected="#d8eafb",
    accent="#075f9d",
    accent_text="#ffffff",
    focus="#075f9d",
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
        """Build system semantics from Qt palette roles with contrast guards."""
        if qt_palette is None:
            return _DARK
        try:
            from PyQt6.QtGui import QPalette

            role = QPalette.ColorRole
            window = cls._qt_colour(qt_palette, role.Window, _DARK.window)
            surface = cls._qt_colour(qt_palette, role.Base, window)
            surface_raised = cls._qt_colour(qt_palette, role.AlternateBase, surface)
            text = cls._qt_colour(qt_palette, role.WindowText, _DARK.text)
            text_muted = cls._qt_colour(qt_palette, role.PlaceholderText, text)
            border = cls._qt_colour(qt_palette, role.Mid, _DARK.border)
            hover = cls._qt_colour(qt_palette, role.Button, surface_raised)
            selected = cls._qt_colour(qt_palette, role.Highlight, _DARK.selected)
            accent = cls._qt_colour(qt_palette, role.Link, selected)
            accent_text = cls._qt_colour(qt_palette, role.HighlightedText, text)
            disabled_text = cls._qt_colour(qt_palette, role.PlaceholderText, text_muted)
        except (ImportError, AttributeError):
            return _DARK

        dark = _relative_luminance(window) < 0.35
        statuses = _DARK if dark else _LIGHT
        text = _ensure_contrast(text, window, 4.5)
        text_muted = _ensure_contrast(text_muted, window, 4.5)
        accent = _ensure_contrast(accent, selected, 3.0)
        focus = _ensure_contrast(accent, window, 3.0)
        accent_text = _ensure_contrast(accent_text, accent, 4.5)
        border = _ensure_contrast(border, window, 3.0)
        disabled_surface = _mix(surface, window, 0.45)

        return SemanticPalette(
            window=window,
            surface=surface,
            surface_raised=surface_raised,
            text=text,
            text_muted=text_muted,
            border=border,
            hover=hover,
            selected=selected,
            accent=accent,
            accent_text=accent_text,
            focus=focus,
            disabled_surface=disabled_surface,
            disabled_text=_ensure_contrast(disabled_text, disabled_surface, 3.0),
            success=statuses.success,
            success_surface=statuses.success_surface,
            success_text=statuses.success_text,
            warning=statuses.warning,
            warning_surface=statuses.warning_surface,
            warning_text=statuses.warning_text,
            error=statuses.error,
            error_surface=statuses.error_surface,
            error_text=statuses.error_text,
        )

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
        try:
            palette = self.palette_for(name, qt_palette)
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
