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
import os
import threading
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Optional

from core.navigation.migrations import (
    migrate_last_route,
    migrate_route_references,
    navigation_mode_from_value,
)
from core.state.atomic_io import advisory_lock, atomic_write_bytes
from core.state.paths import StatePaths
from core.state.version_constants import SETTINGS_SCHEMA_VERSION

logger = logging.getLogger(__name__)

CONFIG_DIR = StatePaths.from_environment().config
SETTINGS_FILE = CONFIG_DIR / "settings.json"


@dataclass
class AppSettings:
    """Default application settings with typed fields."""

    # Appearance
    theme: str = "dark"
    follow_system_theme: bool = True

    # Behavior
    start_minimized: bool = False
    show_notifications: bool = True
    confirm_dangerous_actions: bool = True
    restore_last_tab: bool = False
    last_tab_index: int = 0

    # Advanced
    log_level: str = "INFO"
    check_updates_on_start: bool = False

    # UX
    navigation_mode: str = "standard"
    show_advanced_tools: bool = False
    suppressed_confirmations: list = field(default_factory=list)
    locale: str = "en"
    favorite_routes: list = field(default_factory=list)
    favorite_tweaks: list = field(default_factory=list)
    overview_intro_dismissed: bool = False
    hidden_routes: list = field(default_factory=list)
    last_route_id: str = "overview"
    window_geometry: dict = field(default_factory=dict)

    # Version tracking
    last_seen_version: str = "0.0.0"
    state_schema_version: int = SETTINGS_SCHEMA_VERSION


# Canonical set of known setting keys (derived from the dataclass).
_DEFAULTS = AppSettings()
KNOWN_KEYS = set(asdict(_DEFAULTS).keys())
STATE_SCHEMA_VERSION = SETTINGS_SCHEMA_VERSION

_STRING_FIELDS = frozenset({"last_route_id", "last_seen_version"})
_STRING_LIST_FIELDS = frozenset({
    "suppressed_confirmations", "favorite_routes", "favorite_tweaks", "hidden_routes",
})
_BOOLEAN_FIELDS = frozenset({
    "follow_system_theme", "start_minimized", "show_notifications",
    "confirm_dangerous_actions", "restore_last_tab", "check_updates_on_start",
    "show_advanced_tools", "overview_intro_dismissed",
})
_SETTING_ENUMS = {
    "theme": frozenset({"dark", "light", "highcontrast"}),
    "log_level": frozenset({"DEBUG", "INFO", "WARNING", "ERROR"}),
    "navigation_mode": frozenset({"standard", "advanced", "beginner", "intermediate"}),
    "locale": frozenset({"en", "sv"}),
}


def invalid_setting_types(raw: Any) -> tuple[str, ...]:
    """Return persisted settings whose values do not match the typed contract."""
    if not isinstance(raw, dict):
        return ("<root>",)
    invalid: list[str] = []
    defaults = asdict(AppSettings())
    for key, value in raw.items():
        if key not in defaults:
            continue
        if key in _BOOLEAN_FIELDS:
            valid = isinstance(value, bool)
        elif key == "last_tab_index":
            valid = isinstance(value, int) and not isinstance(value, bool) and value >= 0
        elif key == "state_schema_version":
            valid = isinstance(value, int) and not isinstance(value, bool) and value >= 0
        elif key in _STRING_LIST_FIELDS:
            valid = isinstance(value, list) and all(isinstance(item, str) for item in value)
        elif key == "window_geometry":
            valid = _valid_window_geometry(value)
        elif key in _SETTING_ENUMS:
            valid = isinstance(value, str) and value in _SETTING_ENUMS[key]
        elif key in _STRING_FIELDS:
            valid = isinstance(value, str)
        else:
            valid = isinstance(value, type(defaults[key]))
        if not valid:
            invalid.append(key)
    if "theme" not in raw:
        for key in ("appearance.theme", "ui.theme"):
            if _contains_path(raw, key):
                if not isinstance(_first(raw, key), str) or _first(raw, key) not in _SETTING_ENUMS["theme"]:
                    invalid.append("theme")
                break
    legacy_geometry = _first(raw, "window.geometry", "main_window_geometry", "geometry")
    if legacy_geometry is not None and "window_geometry" not in raw and not _valid_window_geometry(legacy_geometry):
        invalid.append("window_geometry")
    return tuple(sorted(invalid))


def _valid_window_geometry(value: Any) -> bool:
    if isinstance(value, list):
        return len(value) >= 4 and all(isinstance(item, int) and not isinstance(item, bool) for item in value[:4])
    if not isinstance(value, dict):
        return False
    for key in ("x", "y", "width", "height"):
        if key in value and (not isinstance(value[key], int) or isinstance(value[key], bool)):
            return False
    if "state" in value and not isinstance(value["state"], str):
        return False
    return True


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


def _contains_path(raw: dict, key: str) -> bool:
    current: Any = raw
    for part in key.split("."):
        if not isinstance(current, dict) or part not in current:
            return False
        current = current[part]
    return True


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
    invalid = set(invalid_setting_types(raw))
    migrated = bool(invalid)

    for key in defaults:
        if key in raw and key not in invalid:
            defaults[key] = raw[key]

    previous_schema = raw.get("state_schema_version", 0)
    if not isinstance(previous_schema, int) or isinstance(previous_schema, bool):
        previous_schema = 0
    if previous_schema < STATE_SCHEMA_VERSION:
        # The old setting was saved but never executed. Require the user to opt
        # in again before it can trigger a network request on application start.
        defaults["check_updates_on_start"] = False
        if raw.get("check_updates_on_start") is not False:
            migrated = True

    legacy_theme = _first(raw, "appearance.theme", "ui.theme")
    valid_legacy_theme = isinstance(legacy_theme, str) and legacy_theme in {"dark", "light", "highcontrast"}
    if "theme" not in raw and valid_legacy_theme:
        defaults["theme"] = legacy_theme
        migrated = True
    if "follow_system_theme" not in raw and ("theme" in raw or valid_legacy_theme):
        # A stored theme predates the follow-system setting and represents an
        # explicit user choice.  Preserve that choice during migration.
        defaults["follow_system_theme"] = False
        migrated = True

    legacy_experience = _first(
        raw,
        "experience_level",
        "experience",
        "experienceLevel",
        "ui.experience_level",
    )
    mode_value = _first(raw, "navigation_mode", "ui_mode", "navigation.mode")
    mode = navigation_mode_from_value(
        mode_value if mode_value is not None else legacy_experience
    )
    if raw.get("navigation_mode") != mode.value:
        migrated = True
    defaults["navigation_mode"] = mode.value

    if "experience_level" in raw or legacy_experience is not None:
        migrated = True

    favorite_routes = _first(raw, "navigation.favorite_routes", "navigation.favorites", "favorite_tabs", "favorites")
    if favorite_routes is not None:
        normalized_favorites = migrate_route_references(favorite_routes)
        if defaults["favorite_routes"] != normalized_favorites:
            defaults["favorite_routes"] = normalized_favorites
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
    if hidden_routes is not None:
        normalized_hidden = migrate_route_references(hidden_routes)
        if defaults["hidden_routes"] != normalized_hidden:
            defaults["hidden_routes"] = normalized_hidden
            migrated = True

    window_geometry = _first(raw, "window.geometry", "main_window_geometry", "geometry")
    if "window_geometry" not in raw and window_geometry is not None:
        defaults["window_geometry"] = _window_geometry(window_geometry)
        migrated = True

    favorite_values = _string_list(defaults.get("favorite_routes"))
    defaults["favorite_routes"] = migrate_route_references(favorite_values)
    if defaults["favorite_routes"] != favorite_values:
        migrated = True
    favorite_tweaks = _string_list(defaults.get("favorite_tweaks"))
    if defaults.get("favorite_tweaks") != favorite_tweaks:
        migrated = True
    defaults["favorite_tweaks"] = favorite_tweaks
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
        self._read_only_reason = ""
        self._load_issues: tuple[str, ...] = ()
        self._path = Path(settings_path) if settings_path is not None else StatePaths.from_environment().config / "settings.json"
        self._legacy_path: Path | None = None
        if settings_path is None:
            home = Path(os.environ.get("HOME", str(Path.home()))).expanduser()
            self._legacy_path = home / ".config" / "loofi-fedora-tweaks" / "settings.json"
            self._migrate_xdg_path()
        self._settings: dict = asdict(AppSettings())
        self._load()

    @property
    def read_only_reason(self) -> str:
        """Explain why persistence is disabled for unsupported or corrupt input."""
        return self._read_only_reason

    @property
    def load_issues(self) -> tuple[str, ...]:
        """Setting keys with invalid stored types, retained for State Doctor."""
        return self._load_issues

    def _migrate_xdg_path(self) -> None:
        """Copy legacy settings once when a custom XDG config path is selected."""
        legacy = self._legacy_path
        if legacy is None or legacy == self._path or self._path.exists() or not legacy.is_file():
            return
        try:
            original = legacy.read_bytes()
            with advisory_lock(self._path):
                if not self._path.exists():
                    atomic_write_bytes(self._path, original, keep_backup=False)
            logger.info("Copied legacy settings to XDG config path %s; original retained at %s", self._path, legacy)
        except OSError as exc:
            logger.warning("Could not migrate legacy settings to XDG config path: %s", exc)

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
        self._settings[key] = _string_list(value) if key == "favorite_tweaks" else value

    def reset(self) -> bool:
        """Restore every setting to its default value and persist."""
        previous = self._settings
        self._settings = asdict(AppSettings())
        if self.save():
            return True
        self._settings = previous
        return False

    def reset_group(self, keys: list) -> bool:
        """Reset a specific group of setting keys to their defaults and persist."""
        previous = dict(self._settings)
        defaults = asdict(AppSettings())
        for key in keys:
            if key in defaults:
                self._settings[key] = defaults[key]
        if self.save():
            return True
        self._settings = previous
        return False

    def all(self) -> dict:
        """Return a shallow copy of the current settings dict."""
        return dict(self._settings)

    # ---- Persistence -------------------------------------------------------

    def save(self) -> bool:
        """Write settings atomically and report whether persistence succeeded."""
        if self._read_only_reason:
            logger.warning("Settings are read-only: %s", self._read_only_reason)
            return False
        try:
            payload = (json.dumps(self._settings, indent=2, sort_keys=True) + "\n").encode("utf-8")
            with advisory_lock(self._path):
                atomic_write_bytes(self._path, payload)
            logger.debug("Settings saved to %s", self._path)
            return True
        except OSError as exc:
            logger.warning("Failed to save settings: %s", exc)
            return False

    def _load(self) -> None:
        """Load settings from disk, falling back to defaults on error."""
        if not self._path.exists():
            logger.debug("No settings file found; using defaults.")
            return

        try:
            original = self._path.read_bytes()
            raw = json.loads(original.decode("utf-8"))
            if not isinstance(raw, dict):
                raise ValueError("Settings file root is not a JSON object")
            schema_version = raw.get("state_schema_version", 0)
            if isinstance(schema_version, int) and not isinstance(schema_version, bool) and schema_version > STATE_SCHEMA_VERSION:
                self._read_only_reason = f"Settings use future schema version {schema_version}."
                logger.warning("%s Preserve %s unchanged.", self._read_only_reason, self._path)
                return
            self._load_issues = invalid_setting_types(raw)
            self._settings, migrated = migrate_settings(raw)
            # Keep malformed values on disk until an explicit settings save. The
            # atomic writer then retains the exact input as .lkg for recovery.
            if migrated and not self._load_issues:
                self.save()
            logger.debug("Settings loaded from %s", self._path)
        except (UnicodeDecodeError, json.JSONDecodeError, ValueError, OSError) as exc:
            logger.warning(
                "Corrupt settings file (%s); reverting to defaults.", exc
            )
            self._settings = asdict(AppSettings())
            self._read_only_reason = "Settings are unreadable; the original file is preserved read-only."
