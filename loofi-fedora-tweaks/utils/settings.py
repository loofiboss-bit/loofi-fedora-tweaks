"""
Settings Manager - Persistent application settings with JSON storage.
Part of v13.5 "UX Polish" update.

Provides a singleton SettingsManager that persists user preferences
to ~/.config/loofi-fedora-tweaks/settings.json. Includes typed
defaults via AppSettings dataclass, safe read/write with automatic
recovery from corrupt files, and idempotent migration from older UI
state keys.
"""

import json
import logging
import threading
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Optional

from core.navigation.migrations import (
    legacy_experience_for_mode,
    migrate_last_route,
    migrate_route_references,
    navigation_mode_from_value,
)

logger = logging.getLogger(__name__)

CONFIG_DIR = Path.home() / ".config" / "loofi-fedora-tweaks"
SETTINGS_FILE = CONFIG_DIR / "settings.json"


@dataclass
class AppSettings:
    """Default application settings with typed fields."""

    # Appearance
    theme: str = "dark"
    follow_system_theme: bool = False

    # Behavior
    start_minimized: bool = False
    show_notifications: bool = True
    confirm_dangerous_actions: bool = True
    restore_last_tab: bool = False
    last_tab_index: int = 0

    # Advanced
    log_level: str = "INFO"
    check_updates_on_start: bool = True
    plugin_analytics_enabled: bool = False
    plugin_analytics_anonymous_id: str = ""
    plugin_analytics_endpoint: str = "https://api.loofi.software/marketplace/v1/analytics/events"

    # UX
    experience_level: str = "beginner"
    navigation_mode: str = "standard"
    suppressed_confirmations: list = field(default_factory=list)
    locale: str = "en"
    favorite_routes: list = field(default_factory=list)
    hidden_routes: list = field(default_factory=list)
    last_route_id: str = "atlas_dashboard"
    window_geometry: dict = field(default_factory=dict)

    # Version tracking
    last_seen_version: str = "0.0.0"
    state_schema_version: int = 2


# Canonical set of known setting keys (derived from the dataclass).
_DEFAULTS = AppSettings()
KNOWN_KEYS = set(asdict(_DEFAULTS).keys())
STATE_SCHEMA_VERSION = 2


def _first(raw: dict, *keys: str) -> Any:
    """Return the first present value from dotted or top-level keys."""
    for key in keys:
        current: Any = raw
        found = True
        for part in key.split("."):
            if isinstance(current, dict) and part in current:
                current = current[part]
            else:
                found = False
                break
        if found:
            return current
    return None


def _string_list(value: Any) -> list:
    """Normalize list-like setting values to a de-duplicated string list."""
    if not isinstance(value, list):
        return []
    normalized = []
    for item in value:
        text = str(item).strip()
        if text and text not in normalized:
            normalized.append(text)
    return normalized


def _window_geometry(value: Any) -> dict:
    """Normalize legacy window geometry into a JSON-safe geometry dict."""
    if isinstance(value, dict):
        allowed = ("x", "y", "width", "height", "state")
        return {key: value[key] for key in allowed if key in value}
    if isinstance(value, list) and len(value) >= 4:
        return {
            "x": value[0],
            "y": value[1],
            "width": value[2],
            "height": value[3],
        }
    return {}


def migrate_settings(raw: dict) -> tuple[dict, bool]:
    """Return canonical settings plus whether legacy state was migrated."""
    defaults = asdict(AppSettings())
    migrated = False

    for key in defaults:
        if key in raw:
            defaults[key] = raw[key]

    legacy_theme = _first(raw, "appearance.theme", "ui.theme")
    if "theme" not in raw and legacy_theme in {"dark", "light", "highcontrast"}:
        defaults["theme"] = legacy_theme
        migrated = True

    legacy_experience = _first(raw, "experience", "experienceLevel", "ui.experience_level")
    if "experience_level" not in raw and legacy_experience is not None:
        value = str(legacy_experience).lower()
        if value in {"beginner", "intermediate", "advanced"}:
            defaults["experience_level"] = value
            migrated = True

    mode_value = _first(raw, "navigation_mode", "ui_mode", "navigation.mode")
    mode = navigation_mode_from_value(
        mode_value if mode_value is not None else defaults["experience_level"]
    )
    if raw.get("navigation_mode") != mode.value:
        migrated = True
    defaults["navigation_mode"] = mode.value

    compatible_experience = legacy_experience_for_mode(mode)
    if defaults["experience_level"] != compatible_experience:
        defaults["experience_level"] = compatible_experience
        migrated = True

    favorite_routes = _first(raw, "navigation.favorite_routes", "navigation.favorites", "favorite_tabs", "favorites")
    if "favorite_routes" not in raw and favorite_routes is not None:
        defaults["favorite_routes"] = _string_list(favorite_routes)
        migrated = True

    last_route = _first(
        raw,
        "last_route_id",
        "navigation.last_route_id",
        "navigation.last_route",
        "last_active_route",
        "last_route",
    )
    migrated_last_route = migrate_last_route(
        last_route if last_route is not None else defaults["last_route_id"]
    )
    if raw.get("last_route_id") != migrated_last_route:
        migrated = True
    defaults["last_route_id"] = migrated_last_route

    hidden_routes = _first(raw, "navigation.hidden_routes", "hiddenRoutes", "hidden_routes")
    if "hidden_routes" not in raw and hidden_routes is not None:
        defaults["hidden_routes"] = _string_list(hidden_routes)
        migrated = True

    window_geometry = _first(raw, "window.geometry", "main_window_geometry", "geometry")
    if "window_geometry" not in raw and window_geometry is not None:
        defaults["window_geometry"] = _window_geometry(window_geometry)
        migrated = True

    favorite_values = _string_list(defaults.get("favorite_routes"))
    defaults["favorite_routes"] = migrate_route_references(favorite_values)
    if defaults["favorite_routes"] != favorite_values:
        migrated = True
    hidden_values = _string_list(defaults.get("hidden_routes"))
    defaults["hidden_routes"] = migrate_route_references(hidden_values)
    if defaults["hidden_routes"] != hidden_values:
        migrated = True
    defaults["window_geometry"] = _window_geometry(defaults.get("window_geometry"))
    defaults["state_schema_version"] = STATE_SCHEMA_VERSION

    if raw.get("state_schema_version") != STATE_SCHEMA_VERSION:
        migrated = True

    return defaults, migrated


class SettingsManager:
    """
    Singleton settings manager with JSON persistence.

    Usage::

        from utils.settings import SettingsManager

        mgr = SettingsManager.instance()
        theme = mgr.get("theme")       # -> "dark"
        mgr.set("theme", "light")
        mgr.save()
    """

    _instance: Optional["SettingsManager"] = None
    _lock = threading.Lock()

    def __init__(self, settings_path: Optional[Path] = None):
        """
        Initialise with an optional custom path (useful for testing).
        Prefer ``SettingsManager.instance()`` for production use.
        """
        self._path = settings_path or SETTINGS_FILE
        self._settings: dict = asdict(AppSettings())
        self._load()

    # ---- Singleton accessor ------------------------------------------------

    @classmethod
    def instance(cls) -> "SettingsManager":
        """Return the global singleton, creating it on first call."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    @classmethod
    def _reset_instance(cls):
        """Reset singleton (for testing only)."""
        with cls._lock:
            cls._instance = None

    # ---- Public API --------------------------------------------------------

    def get(self, key: str, default: Any = None) -> Any:
        """
        Return the value for *key*.

        If *key* is unknown **and** no explicit *default* is given,
        ``KeyError`` is raised so callers notice typos early.
        """
        if key in self._settings:
            return self._settings[key]
        if default is not None:
            return default
        if key not in KNOWN_KEYS:
            raise KeyError(f"Unknown setting: {key!r}")
        return asdict(AppSettings()).get(key)

    def set(self, key: str, value: Any) -> None:
        """
        Set *key* to *value*.

        Only keys present in ``KNOWN_KEYS`` are accepted; unknown keys
        raise ``KeyError``.  The change is held in memory until
        :meth:`save` is called.
        """
        if key not in KNOWN_KEYS:
            raise KeyError(f"Unknown setting: {key!r}")
        self._settings[key] = value

    def reset(self) -> None:
        """Restore every setting to its default value and persist."""
        self._settings = asdict(AppSettings())
        self.save()

    def reset_group(self, keys: list) -> None:
        """Reset a specific group of setting keys to their defaults and persist."""
        defaults = asdict(AppSettings())
        for key in keys:
            if key in defaults:
                self._settings[key] = defaults[key]
        self.save()

    def all(self) -> dict:
        """Return a shallow copy of the current settings dict."""
        return dict(self._settings)

    # ---- Persistence -------------------------------------------------------

    def save(self) -> None:
        """Write current settings to disk as pretty-printed JSON."""
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            tmp_path = self._path.with_suffix(".tmp")
            tmp_path.write_text(json.dumps(self._settings, indent=2) + "\n")
            tmp_path.replace(self._path)
            logger.debug("Settings saved to %s", self._path)
        except OSError as exc:
            logger.warning("Failed to save settings: %s", exc)

    def _load(self) -> None:
        """Load settings from disk, falling back to defaults on error."""
        if not self._path.exists():
            logger.debug("No settings file found; using defaults.")
            return

        try:
            raw = json.loads(self._path.read_text())
            if not isinstance(raw, dict):
                raise ValueError("Settings file root is not a JSON object")
            self._settings, migrated = migrate_settings(raw)
            if migrated:
                self.save()
            logger.debug("Settings loaded from %s", self._path)
        except (json.JSONDecodeError, ValueError, OSError) as exc:
            logger.warning(
                "Corrupt settings file (%s); reverting to defaults.", exc
            )
            self._settings = asdict(AppSettings())
