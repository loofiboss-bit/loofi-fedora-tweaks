"""Closed, read-only Fedora tweak catalog and current-state inspection."""

from __future__ import annotations

import json
import math
import os
import re
import shutil
import time
from dataclasses import dataclass, replace
from pathlib import Path
from xml.etree.ElementTree import Element
from defusedxml import ElementTree
from defusedxml.common import DefusedXmlException
from typing import Callable, Sequence

from core.actions.contracts import ActionRuntime
from core.executor.action_result import ActionResult
from core.tweak_commands import GNOME_KEYS, KDE_KEYS, SCHEME_PATTERN, valid_value, kde_read_vector, kde_write_vector, gnome_schema, KDE_SPECS, KWIN_RUNTIME_KEYS, CURSOR_TWEAK_IDS, THEME_PATTERN, SNAP_TWEAK_IDS, KWIN_PLACEMENT_VALUES


_SCHEME = SCHEME_PATTERN
_GNOME_KEYS = GNOME_KEYS


@dataclass(frozen=True)
class Tweak:
    id: str
    title: str
    description: str
    group: str
    desktop: str
    action_id: str
    choices: tuple[tuple[str, str], ...]
    system_wide: bool = False
    privileged: bool = False
    control_kind: str = "auto"
    search_terms: tuple[str, ...] = ()
    effect_hint: str = ""


@dataclass(frozen=True)
class TweakState:
    tweak: Tweak
    status: str
    value: str = ""
    choices: tuple[tuple[str, str], ...] = ()
    message: str = ""
    restore_run_id: str = ""
    restore_value: str = ""
    restore_message: str = ""


TWEAKS: tuple[Tweak, ...] = (
    Tweak("gnome-mouse-left-handed", "Left-handed mouse", "Swap the primary and secondary mouse buttons.", "Input", "gnome", "set-gnome-mouse-left-handed", (("true", "On"), ("false", "Off"))),
    Tweak("gnome-mouse-acceleration", "Mouse acceleration", "Choose how pointer speed responds to mouse movement.", "Input", "gnome", "set-gnome-mouse-acceleration", (("default", "System default"), ("flat", "Constant speed"), ("adaptive", "Adaptive"))),
    Tweak("gnome-keyboard-repeat", "Keyboard repeat", "Repeat a key while it is held down.", "Input", "gnome", "set-gnome-keyboard-repeat", (("true", "On"), ("false", "Off"))),
    Tweak("gnome-color", "Color preference", "Choose how GNOME apps prefer light or dark colors.", "Appearance", "gnome", "set-gnome-color", (("default", "System default"), ("prefer-light", "Light"), ("prefer-dark", "Dark"))),
    Tweak("gnome-animations", "Animations", "Turn GNOME interface motion on or off.", "Appearance", "gnome", "set-gnome-animations", (("true", "On"), ("false", "Off"))),
    Tweak("gnome-text-scale", "Text size", "Scale interface text without changing display resolution.", "Appearance", "gnome", "set-gnome-text-scale", (("1.0", "100%"), ("1.25", "125%"), ("1.5", "150%"))),
    Tweak("gnome-battery", "Battery percentage", "Show the battery percentage in the GNOME status area.", "Desktop", "gnome", "set-gnome-battery", (("true", "On"), ("false", "Off"))),
    Tweak("gnome-clock", "Clock seconds", "Show seconds in the GNOME top bar clock.", "Desktop", "gnome", "set-gnome-clock", (("true", "On"), ("false", "Off"))),
    Tweak("gnome-clock-format", "Clock format", "Use a 12-hour or 24-hour GNOME clock.", "Desktop", "gnome", "set-gnome-clock-format", (("12h", "12 hours"), ("24h", "24 hours"))),
    Tweak("gnome-clock-weekday", "Clock weekday", "Show the weekday alongside the GNOME clock.", "Desktop", "gnome", "set-gnome-clock-weekday", (("true", "Show"), ("false", "Hide"))),
    Tweak("gnome-button-layout", "Window titlebar buttons", "Choose which window control buttons appear in GNOME application titlebars.", "Desktop", "gnome", "set-gnome-button-layout", ((":appmenu,close", "Close only (Fedora default)"), (":minimize,maximize,close", "Minimize, Maximize, Close"), ("close,minimize,maximize:", "Left side controls"))),
    Tweak("gnome-tap-to-click", "Touchpad tap-to-click", "Tap the touchpad to click instead of pressing down.", "Interaction", "gnome", "set-gnome-tap-to-click", (("true", "On"), ("false", "Off"))),
    Tweak("gnome-night-light", "Night Light", "Warm display colors at night to reduce eye strain.", "Appearance", "gnome", "set-gnome-night-light", (("true", "On"), ("false", "Off"))),
    Tweak("gnome-sound-overamp", "Sound over-amplification", "Allow volume above 100% in GNOME volume controls.", "Desktop", "gnome", "set-gnome-sound-overamp", (("true", "On (>100%)"), ("false", "Off (100% max)"))),
    Tweak("gnome-font-antialiasing", "Font antialiasing", "Configure font rendering mode for sharp text display.", "Appearance", "gnome", "set-gnome-font-antialiasing", (("rgba", "Subpixel LCD (ClearType)"), ("grayscale", "Grayscale"), ("none", "None"))),
    Tweak("kde-single-click", "Open files and folders", "Choose single-click or double-click opening in KDE applications.", "Interaction", "kde", "set-kde-single-click", (("true", "Single click"), ("false", "Double click"))),
    Tweak("kde-double-click-interval", "Double-click interval", "Choose how much time is allowed between the two clicks.", "Interaction", "kde", "set-kde-double-click-interval", (("200", "200 ms"), ("400", "400 ms"), ("600", "600 ms"), ("800", "800 ms"))),
    Tweak("kde-smooth-scroll", "Smooth scrolling", "Enable or disable smooth scrolling in supported KDE applications.", "Interaction", "kde", "set-kde-smooth-scroll", (("true", "On"), ("false", "Off"))),
    Tweak("kde-scrollbar-click", "Scrollbar track click", "Choose whether clicking the scrollbar track moves one page or jumps to the clicked position.", "Interaction", "kde", "set-kde-scrollbar-click", (("true", "Move one page"), ("false", "Jump to position"))),
    Tweak("kde-color", "Color scheme", "Choose an installed Plasma color scheme; custom schemes remain available.", "Appearance", "kde", "set-kde-color", ()),
    Tweak("kde-cursor-theme", "Pointer theme", "Choose an installed pointer theme for KDE Wayland. Existing applications may render it differently.", "Appearance", "kde", "set-kde-cursor-theme", ()),
    Tweak("kde-cursor-size", "Pointer size", "Choose a requested pointer size for KDE Wayland; the theme may render it at a different size.", "Appearance", "kde", "set-kde-cursor-size", (("24", "24"), ("32", "32"), ("48", "48"), ("64", "64"))),
    Tweak("kde-plasma-style", "Plasma style", "Choose an installed style for Plasma panels and widgets.", "Appearance", "kde", "set-kde-plasma-style", ()),
    Tweak("kde-animation", "Animation speed", "Choose a Plasma animation speed; custom values remain untouched until changed.", "Appearance", "kde", "set-kde-animation", (("0", "Instant"), ("0.5", "Fast"), ("1", "Normal"))),
    Tweak("kde-tap-to-click", "Touchpad tap-to-click", "Tap the touchpad to click in KDE Plasma.", "Interaction", "kde", "set-kde-tap-to-click", (("true", "On"), ("false", "Off"))),
    Tweak("kde-night-color", "Night Color", "Warm display colors at night in KDE Plasma.", "Appearance", "kde", "set-kde-night-color", (("true", "On"), ("false", "Off"))),
    Tweak("gnome-hot-corners", "Hot corner", "Open the Activities overview when the pointer hits the top-left corner.", "Desktop", "gnome", "set-gnome-hot-corners", (("true", "On"), ("false", "Off"),)),
    Tweak("gnome-clock-date", "Clock date", "Show the date next to the time in the top bar.", "Desktop", "gnome", "set-gnome-clock-date", (("true", "On"), ("false", "Off"),)),
    Tweak("gnome-overlay-scrolling", "Overlay scrollbars", "Hide scrollbars until you scroll.", "Appearance", "gnome", "set-gnome-overlay-scrolling", (("true", "On"), ("false", "Off"),)),
    Tweak("gnome-locate-pointer", "Locate pointer", "Highlight the pointer when you press Ctrl.", "Interaction", "gnome", "set-gnome-locate-pointer", (("true", "On"), ("false", "Off"),)),
    Tweak("gnome-primary-paste", "Middle-click paste", "Paste selected text with a middle click.", "Interaction", "gnome", "set-gnome-primary-paste", (("true", "On"), ("false", "Off"),)),
    Tweak("gnome-recent-files", "Remember recent files", "Keep a list of recently used files.", "Privacy", "gnome", "set-gnome-recent-files", (("true", "On"), ("false", "Off"),)),
    Tweak("gnome-location", "Location services", "Let apps request your location.", "Privacy", "gnome", "set-gnome-location", (("true", "On"), ("false", "Off"),)),
    Tweak("gnome-auto-trash", "Empty trash automatically", "Delete old files from the trash automatically.", "Privacy", "gnome", "set-gnome-auto-trash", (("true", "On"), ("false", "Off"),)),
    Tweak("gnome-lock-enabled", "Automatic screen lock", "Lock the screen automatically when the screen turns off.", "Privacy", "gnome", "set-gnome-lock-enabled", (("true", "On"), ("false", "Off"),)),
    Tweak("gnome-notification-banners", "Notification banners", "Show notification banners on screen.", "Privacy", "gnome", "set-gnome-notification-banners", (("true", "On"), ("false", "Off"),)),
    Tweak("gnome-lock-notifications", "Notifications on lock screen", "Show notifications while the screen is locked.", "Privacy", "gnome", "set-gnome-lock-notifications", (("true", "On"), ("false", "Off"),)),
    Tweak("gnome-touchpad-natural-scroll", "Touchpad natural scrolling", "Content follows your fingers on the touchpad.", "Input", "gnome", "set-gnome-touchpad-natural-scroll", (("true", "On"), ("false", "Off"),)),
    Tweak("gnome-mouse-natural-scroll", "Mouse natural scrolling", "Content follows the wheel direction on a mouse.", "Input", "gnome", "set-gnome-mouse-natural-scroll", (("true", "On"), ("false", "Off"),)),
    Tweak("gnome-disable-while-typing", "Disable touchpad while typing", "Ignore accidental touchpad touches while typing.", "Input", "gnome", "set-gnome-disable-while-typing", (("true", "On"), ("false", "Off"),)),
    Tweak("gnome-click-method", "Touchpad click method", "Choose how physical touchpad clicks are interpreted.", "Input", "gnome", "set-gnome-click-method", (("default", "System default"), ("areas", "Button areas"), ("fingers", "Finger count"), ("none", "Off"),)),
    Tweak("gnome-dynamic-workspaces", "Dynamic workspaces", "Create and remove workspaces automatically.", "Windows", "gnome", "set-gnome-dynamic-workspaces", (("true", "On"), ("false", "Off"),)),
    Tweak("gnome-edge-tiling", "Edge tiling", "Tile windows by dragging them to screen edges.", "Windows", "gnome", "set-gnome-edge-tiling", (("true", "On"), ("false", "Off"),)),
    Tweak("gnome-center-new-windows", "Center new windows", "Open new windows in the center of the screen.", "Windows", "gnome", "set-gnome-center-new-windows", (("true", "On"), ("false", "Off"),)),
    Tweak("gnome-attach-modal", "Attach dialogs to windows", "Keep modal dialogs attached to their parent window.", "Windows", "gnome", "set-gnome-attach-modal", (("true", "On"), ("false", "Off"),)),
    Tweak("gnome-auto-raise", "Raise windows on hover", "Bring a window to the front when the pointer rests on it.", "Windows", "gnome", "set-gnome-auto-raise", (("true", "On"), ("false", "Off"),)),
    Tweak("gnome-focus-mode", "Window focus", "Choose how windows receive keyboard focus.", "Windows", "gnome", "set-gnome-focus-mode", (("click", "Click to focus"), ("sloppy", "Focus follows mouse"), ("mouse", "Focus under mouse"),)),
    Tweak("gnome-titlebar-double-click", "Titlebar double-click", "Choose what double-clicking a titlebar does.", "Windows", "gnome", "set-gnome-titlebar-double-click", (("toggle-maximize", "Maximize"), ("minimize", "Minimize"), ("lower", "Lower"), ("menu", "Window menu"), ("none", "Nothing"),)),
    Tweak("gnome-accent-color", "Accent color", "Choose the GNOME accent color (GNOME 47 or newer).", "Appearance", "gnome", "set-gnome-accent-color", (("blue", "Blue"), ("teal", "Teal"), ("green", "Green"), ("yellow", "Yellow"), ("orange", "Orange"), ("red", "Red"), ("pink", "Pink"), ("purple", "Purple"), ("slate", "Slate"),)),
    Tweak("gnome-font-hinting", "Font hinting", "Choose how fonts are fitted to the pixel grid.", "Appearance", "gnome", "set-gnome-font-hinting", (("none", "None"), ("slight", "Slight"), ("medium", "Medium"), ("full", "Full"),)),
    Tweak("gnome-event-sounds", "System sounds", "Play sounds for system events.", "Sound", "gnome", "set-gnome-event-sounds", (("true", "On"), ("false", "Off"),)),
    Tweak("gnome-idle-dim", "Dim screen when idle", "Reduce brightness when the computer is idle.", "Power", "gnome", "set-gnome-idle-dim", (("true", "On"), ("false", "Off"),)),
    Tweak("gnome-power-button", "Power button action", "Choose what pressing the power button does.", "Power", "gnome", "set-gnome-power-button", (("suspend", "Suspend"), ("hibernate", "Hibernate"), ("interactive", "Ask"), ("nothing", "Nothing"),)),
    Tweak("gnome-files-click-policy", "Open files and folders", "Choose whether a single or double click opens files and folders in GNOME Files.", "Files", "gnome", "set-gnome-files-click-policy", (("single", "Single click"), ("double", "Double click"))),
    Tweak("gnome-files-default-folder-view", "Default folder view", "Choose the view used for folders in GNOME Files.", "Files", "gnome", "set-gnome-files-default-folder-view", (("icon-view", "Icons"), ("list-view", "List"))),
    Tweak("kde-window-placement", "New window placement", "Choose where new windows open in Plasma.", "Windows", "kde", "set-kde-window-placement", (("Smart", "Smart"), ("Centered", "Centered"), ("UnderMouse", "Under pointer"))),
    Tweak("kde-border-snap-zone", "Screen edge snap distance", "Choose how close a window must be to snap to a screen edge.", "Windows", "kde", "set-kde-border-snap-zone", (("0", "Off"), ("10", "10 px"), ("20", "20 px"), ("30", "30 px"))),
    Tweak("kde-window-snap-zone", "Window snap distance", "Choose how close a window must be to snap to another window.", "Windows", "kde", "set-kde-window-snap-zone", (("0", "Off"), ("10", "10 px"), ("20", "20 px"), ("30", "30 px"))),
    Tweak("kde-focus-policy", "Window focus", "Choose how windows receive keyboard focus in Plasma.", "Windows", "kde", "set-kde-focus-policy", (("ClickToFocus", "Click to focus"), ("FocusFollowsMouse", "Focus follows mouse"), ("FocusUnderMouse", "Focus under mouse"),)),
    Tweak("kde-titlebar-double-click", "Titlebar double-click", "Choose what double-clicking a titlebar does.", "Windows", "kde", "set-kde-titlebar-double-click", (("Maximize", "Maximize"), ("Minimize", "Minimize"), ("Shade", "Roll up"), ("Lower", "Lower"), ("Nothing", "Nothing"),)),
    Tweak("kde-blur", "Background blur", "Blur the background behind translucent windows.", "Appearance", "kde", "set-kde-blur", (("true", "On"), ("false", "Off"),)),
    Tweak("kde-translucency", "Window translucency", "Make windows translucent while moving them.", "Appearance", "kde", "set-kde-translucency", (("true", "On"), ("false", "Off"),)),
    Tweak("kde-wobbly-windows", "Wobbly windows", "Wobble windows while dragging them.", "Appearance", "kde", "set-kde-wobbly-windows", (("true", "On"), ("false", "Off"),)),
    Tweak("kde-numlock", "NumLock on startup", "Choose the NumLock state at login.", "Input", "kde", "set-kde-numlock", (("0", "On"), ("1", "Off"), ("2", "Leave unchanged"),)),
    Tweak("kde-key-repeat", "Holding a key", "Choose what happens when you hold down a key.", "Input", "kde", "set-kde-key-repeat", (("repeat", "Repeat the key"), ("accent", "Show accent menu"), ("nothing", "Do nothing"),)),
    Tweak("kde-autolock", "Automatic screen lock", "Lock the screen automatically after inactivity.", "Privacy", "kde", "set-kde-autolock", (("true", "On"), ("false", "Off"),)),
    Tweak("kde-lock-on-resume", "Lock after sleep", "Require a password after waking from sleep.", "Privacy", "kde", "set-kde-lock-on-resume", (("true", "On"), ("false", "Off"),)),
    Tweak("kde-confirm-logout", "Confirm logout", "Ask for confirmation before logging out.", "Desktop", "kde", "set-kde-confirm-logout", (("true", "On"), ("false", "Off"),)),
    Tweak("kde-login-mode", "On login", "Choose which session is restored at login.", "Desktop", "kde", "set-kde-login-mode", (("restorePreviousLogout", "Restore previous session"), ("restoreSavedSession", "Restore saved session"), ("emptySession", "Start empty"),)),
    Tweak("kde-show-delete", "Show Delete command", "Show a permanent Delete command in context menus.", "Interaction", "kde", "set-kde-show-delete", (("true", "On"), ("false", "Off"),)),
    Tweak("kde-dolphin-show-full-path", "Show full path in location bar", "Show the complete folder path in Dolphin's location bar.", "Files", "kde", "set-kde-dolphin-show-full-path", (("true", "On"), ("false", "Off"))),
    Tweak("kde-borderless-maximized-windows", "Hide titlebar when maximized", "Hide the window titlebar when a window is maximized in KDE Plasma.", "Windows", "kde", "set-kde-borderless-maximized-windows", (("true", "On"), ("false", "Off"))),
    Tweak("kde-dolphin-editable-location", "Editable location bar", "Enter a folder path directly in Dolphin's location bar.", "Files", "kde", "set-kde-dolphin-editable-location", (("true", "On"), ("false", "Off"))),
    Tweak("kde-dolphin-remember-tabs", "Reopen folders and tabs", "Restore Dolphin's open folders and tabs when it starts.", "Files", "kde", "set-kde-dolphin-remember-tabs", (("true", "On"), ("false", "Off"))),
    Tweak("kde-dolphin-external-folders-new-tab", "Open external folders in a new tab", "Use a new Dolphin tab for folders opened by other applications.", "Files", "kde", "set-kde-dolphin-external-folders-new-tab", (("true", "On"), ("false", "Off"))),
    Tweak("kde-dolphin-confirm-close-tabs", "Confirm closing multiple tabs", "Ask before closing a Dolphin window containing multiple tabs.", "Files", "kde", "set-kde-dolphin-confirm-close-tabs", (("true", "On"), ("false", "Off"))),
    Tweak("kde-edge-tiling", "Edge tiling", "Tile windows by dragging them to screen edges in Plasma.", "Windows", "kde", "set-kde-edge-tiling", (("true", "On"), ("false", "Off"))),
    Tweak("kde-focus-stealing-prevention", "Focus stealing prevention", "Limit how newly opened windows take keyboard focus.", "Windows", "kde", "set-kde-focus-stealing-prevention", (("0", "None"), ("1", "Low"), ("2", "Normal"), ("3", "High"), ("4", "Extreme"))),
    Tweak("gnome-files-editable-location", "Editable location bar", "Enter a folder path directly in GNOME Files.", "Files", "gnome", "set-gnome-files-editable-location", (("true", "On"), ("false", "Off"))),
    Tweak("gnome-files-date-format", "File date display", "Choose simple or detailed dates in GNOME Files.", "Files", "gnome", "set-gnome-files-date-format", (("simple", "Simple"), ("detailed", "Detailed"))),
    Tweak("power-profile", "Power profile", "Choose an available power profile for this computer.", "Power", "all", "set-power-profile", (), True),
    Tweak("dnf-parallel-downloads", "DNF parallel downloads", "Speed up package downloads by downloading multiple packages simultaneously.", "System & Packaging", "all", "set-dnf-parallel-downloads", (("3", "3 (Fedora default)"), ("5", "5 (Fast)"), ("10", "10 (Ultra fast - Recommended)"), ("15", "15 (Maximum)")), True, True),
)


# Presentation metadata is derived once from the canonical semantic choices.
def _presentation(tweak: Tweak) -> Tweak:
    labels = {label for _value, label in tweak.choices}
    boolean = {value for value, _label in tweak.choices} == {"true", "false"}
    kind = "switch" if boolean and all(label.startswith(("On", "Off", "Show", "Hide")) for label in labels) else "segmented" if 1 < len(tweak.choices) <= 3 else "dropdown"
    terms: tuple[str, ...] = ("Dolphin", "files", "folders") if tweak.id.startswith("kde-dolphin-") else ("Files", "Nautilus", "folders") if tweak.id.startswith("gnome-files-") else ()
    hint = "Saved pointer values and notification delivery are verified separately. Theme rendering and already-open applications may differ." if tweak.id in CURSOR_TWEAK_IDS else "Saved settings and application in the current Plasma session are verified separately." if tweak.id in KWIN_RUNTIME_KEYS else "Reopen the file manager to apply this setting to existing windows." if terms else ""
    if tweak.id in CURSOR_TWEAK_IDS:
        terms = ("cursor", "pointer", "mouse")
    elif tweak.id == "kde-plasma-style":
        terms = ("Plasma theme", "desktop style", "panels", "widgets")
        hint = "The saved Plasma style is verified. Visible panel and widget rendering remains unverified."
    return replace(tweak, control_kind=kind, search_terms=terms, effect_hint=hint)


TWEAKS = tuple(_presentation(tweak) for tweak in TWEAKS)
BY_ID = {tweak.id: tweak for tweak in TWEAKS}
BY_ACTION = {tweak.action_id: tweak for tweak in TWEAKS}

# Fedora/upstream defaults for GNOME, power and packaging controls. KDE defaults
# come from the reviewed kreadconfig6 specs so there is one source of truth.
_DEFAULTS = {
    "gnome-mouse-left-handed": "false", "gnome-mouse-acceleration": "default", "gnome-keyboard-repeat": "true",
    "gnome-color": "default", "gnome-animations": "true", "gnome-text-scale": "1.0",
    "gnome-battery": "false", "gnome-clock": "false", "gnome-clock-format": "24h",
    "gnome-clock-weekday": "false", "gnome-button-layout": ":appmenu,close",
    "gnome-tap-to-click": "true", "gnome-night-light": "false", "gnome-sound-overamp": "false",
    "gnome-font-antialiasing": "grayscale", "gnome-hot-corners": "true", "gnome-clock-date": "false",
    "gnome-overlay-scrolling": "true", "gnome-locate-pointer": "false", "gnome-primary-paste": "true",
    "gnome-recent-files": "true", "gnome-location": "true", "gnome-auto-trash": "false",
    "gnome-lock-enabled": "true", "gnome-notification-banners": "true", "gnome-lock-notifications": "true",
    "gnome-touchpad-natural-scroll": "true", "gnome-mouse-natural-scroll": "false",
    "gnome-disable-while-typing": "true", "gnome-click-method": "default",
    "gnome-dynamic-workspaces": "true", "gnome-edge-tiling": "true", "gnome-center-new-windows": "false",
    "gnome-attach-modal": "true", "gnome-auto-raise": "false", "gnome-focus-mode": "click",
    "gnome-titlebar-double-click": "toggle-maximize", "gnome-accent-color": "blue",
    "gnome-font-hinting": "slight", "gnome-event-sounds": "true", "gnome-idle-dim": "true",
    "gnome-power-button": "suspend", "power-profile": "balanced", "dnf-parallel-downloads": "3",
    "gnome-files-editable-location": "false", "gnome-files-date-format": "simple",
    "gnome-files-click-policy": "double", "gnome-files-default-folder-view": "icon-view",
}


def default_for(tweak: Tweak) -> str:
    """Return the known default value for a tweak, or an empty string if none is defined."""
    if tweak.id in {"kde-cursor-theme", "kde-plasma-style"}:
        return ""
    if tweak.id in KDE_KEYS:
        return KDE_KEYS[tweak.id][1]
    return _DEFAULTS.get(tweak.id, "")


def _profile_desktop(profile: object) -> str:
    if not bool(getattr(profile, "is_fedora", False)):
        return "unknown"
    backend = getattr(getattr(profile, "deployment_backend", None), "value", "unknown")
    if backend not in {"dnf5", "rpm_ostree"}:
        return "unknown"
    return str(getattr(getattr(profile, "desktop", None), "value", "unknown"))


def visible_tweaks(profile: object) -> tuple[Tweak, ...]:
    desktop = _profile_desktop(profile)
    if desktop not in {"gnome", "kde"}:
        return ()
    return tuple(tweak for tweak in TWEAKS if tweak.desktop in {"all", desktop})


def allowed_value(tweak: Tweak, value: str, choices: Sequence[tuple[str, str]] | None = None) -> bool:
    return value in {choice for choice, _label in (choices if choices is not None else tweak.choices)}


def command_for(tweak: Tweak, value: str, *, restoring: bool = False) -> list[str]:
    if not valid_value(tweak.id, value):
        raise ValueError("Unsupported setting literal.")
    if tweak.id in _GNOME_KEYS:
        if not (restoring or allowed_value(tweak, value)):
            raise ValueError("Unsupported GNOME tweak value.")
        return ["gsettings", "set", gnome_schema(tweak.id), _GNOME_KEYS[tweak.id], value]
    if tweak.id == "kde-color":
        if not _SCHEME.fullmatch(value):
            raise ValueError("Unsupported Plasma color scheme identifier.")
        return ["plasma-apply-colorscheme", value]
    if tweak.id == "kde-plasma-style":
        return ["plasma-apply-desktoptheme", value]
    if tweak.id in KDE_KEYS:
        if not (restoring or tweak.id == "kde-cursor-theme" or allowed_value(tweak, value)):
            raise ValueError("Unsupported Plasma setting choice.")
        return kde_write_vector(tweak.id, value)
    if tweak.id == "power-profile":
        if not valid_value(tweak.id, value):
            raise ValueError("Unsupported power profile.")
        return ["powerprofilesctl", "set", value]
    if tweak.id == "dnf-parallel-downloads":
        if not (restoring or allowed_value(tweak, value)):
            raise ValueError("Unsupported DNF parallel downloads choice.")
        return ["dnf5", "config-manager", "setopt", f"max_parallel_downloads={value}"]
    raise ValueError("Unknown tweak.")


def _read_vector(tweak: Tweak) -> list[str]:
    if tweak.id in _GNOME_KEYS:
        return ["gsettings", "get", gnome_schema(tweak.id), _GNOME_KEYS[tweak.id]]
    if tweak.id == "kde-color":
        return ["plasma-apply-colorscheme", "--list-schemes"]
    if tweak.id in KDE_KEYS:
        return kde_read_vector(tweak.id)
    if tweak.id == "power-profile":
        return ["powerprofilesctl", "get"]
    if tweak.id == "dnf-parallel-downloads":
        return ["dnf5", "--dump-main-config"]
    raise ValueError("Unknown tweak.")


def _parse_schemes(output: str) -> tuple[str, tuple[tuple[str, str], ...]]:
    choices: list[tuple[str, str]] = []
    current = ""
    for line in output.splitlines():
        stripped = line.strip()
        if not stripped.startswith("* "):
            continue
        name = stripped[2:].removesuffix(" (current color scheme)").strip()
        if " (current color scheme)" in stripped:
            current = name
        if _SCHEME.fullmatch(name):
            choices.append((name, name))
    return current, tuple(choices)


_KDE_SCHEMA_LIMIT = 256 * 1024
_KDE_KCFG_DOCTYPE = b'<!DOCTYPE kcfg SYSTEM "http://www.kde.org/standards/kcfg/1.0/kcfg.dtd">'
_SNAPSHOT_BUDGET_SECONDS = 20.0
_DOLPHIN_SCHEMA = Path("/usr/share/config.kcfg/dolphin_generalsettings.kcfg")
_KWIN_SCHEMA = Path("/usr/share/config.kcfg/kwin.kcfg")
_CURSOR_SCHEMA = Path("/usr/share/config.kcfg/cursorthemesettings.kcfg")
_KDESchemaCache = dict[Path, tuple[Element | None, str]]


def kde_capability_error(tweak_id: str, *, schema_cache: _KDESchemaCache | None = None) -> str:
    """Inspect only the installed, fixed schemas for reviewed file/window controls."""
    if tweak_id.startswith("kde-dolphin-") and tweak_id in KDE_SPECS:
        if shutil.which("dolphin") is None:
            return "Dolphin is not installed."
        path, application = _DOLPHIN_SCHEMA, "Dolphin"
    elif tweak_id in KWIN_RUNTIME_KEYS:
        if shutil.which("kwin_wayland") is None and shutil.which("kwin_x11") is None:
            return "KWin is not installed."
        path, application = _KWIN_SCHEMA, "KWin"
    elif tweak_id in CURSOR_TWEAK_IDS:
        path, application = _CURSOR_SCHEMA, "pointer"
    elif tweak_id == "kde-plasma-style":
        for tool in ("kreadconfig6", "plasma-apply-desktoptheme"):
            if shutil.which(tool) is None:
                return f"The required KDE settings tool {tool} is unavailable."
        return ""
    else:
        return ""
    for tool in ("kreadconfig6", "kwriteconfig6"):
        if shutil.which(tool) is None:
            return f"The required KDE settings tool {tool} is unavailable."
    cached = schema_cache.get(path) if schema_cache is not None else None
    if cached is None:
        try:
            with path.open("rb") as stream:
                data = stream.read(_KDE_SCHEMA_LIMIT + 1)
        except OSError:
            cached = (None, f"The installed {application} settings schema is unavailable.")
        else:
            if len(data) > _KDE_SCHEMA_LIMIT:
                cached = (None, f"The installed {application} settings schema exceeds the supported size.")
            else:
                try:
                    # KDE's installed KConfig schemas include this external DTD
                    # declaration. Remove only the known declaration; parsing
                    # still forbids every remaining DTD, entity, and external
                    # reference so no content is fetched or expanded.
                    data = data.replace(_KDE_KCFG_DOCTYPE, b"", 1)
                    cached = (ElementTree.fromstring(data, forbid_dtd=True, forbid_entities=True, forbid_external=True), "")
                except (DefusedXmlException, ElementTree.ParseError, ValueError):
                    cached = (None, f"The installed {application} settings schema could not be read safely.")
        if schema_cache is not None:
            schema_cache[path] = cached
    root, error = cached
    if error:
        return error
    if root is None:
        return f"The installed {application} settings schema could not be read safely."
    _file, group, key, _default = KDE_SPECS[tweak_id]
    expected_type = "Enum" if tweak_id == "kde-window-placement" else "String" if tweak_id == "kde-cursor-theme" else "Int" if tweak_id in {"kde-focus-stealing-prevention", "kde-cursor-size"} | SNAP_TWEAK_IDS else "Bool"
    entries = [entry for section in root.findall(".//{*}group") if section.get("name") == group
               for entry in section.findall("{*}entry") if entry.get("key", entry.get("name")) == key]
    if len(entries) != 1 or entries[0].get("type") != expected_type:
        return f"The installed {application} schema does not support {group}/{key}."
    if tweak_id == "kde-window-placement":
        choices = entries[0].findall("{*}choices/{*}choice")
        values = tuple(choice.get("value", choice.get("name", "")) for choice in choices)
        if values != KWIN_PLACEMENT_VALUES:
            return "The installed KWin placement enum is unsupported."
    if tweak_id in CURSOR_TWEAK_IDS:
        defaults = entries[0].findall("{*}default")
        if len(defaults) != 1 or not valid_value(tweak_id, defaults[0].text or ""):
            return f"The installed pointer schema has an unsupported default for {key}."
    return ""


def normalize_kwin_runtime_value(tweak_id: str, value: str) -> str:
    """Translate only reviewed, installed KWin enum indexes to saved literals."""
    if tweak_id != "kde-window-placement":
        return value
    if kde_capability_error(tweak_id):
        return ""
    if value in KWIN_PLACEMENT_VALUES:
        return value
    if value.isascii() and value.isdigit() and len(value) <= 2:
        index = int(value)
        if index < len(KWIN_PLACEMENT_VALUES):
            return KWIN_PLACEMENT_VALUES[index]
    return ""


def _cursor_session_error(profile: object) -> str:
    session = getattr(profile, "session_type", None)
    if _profile_desktop(profile) != "kde" or getattr(session, "value", session) != "wayland":
        return "Pointer changes require KDE Wayland. Open KDE System Settings → Mouse & Touchpad → Cursor on X11."
    return ""


def read_cursor_config(
    profile: object,
    execute_read_only: Callable[..., ActionResult],
    *,
    schema_cache: _KDESchemaCache | None = None,
) -> tuple[dict[str, str], str]:
    """Read both independent pointer keys using only validated installed defaults."""
    error = _cursor_session_error(profile)
    if error:
        return {}, error
    cache = schema_cache if schema_cache is not None else {}
    for tweak_id in sorted(CURSOR_TWEAK_IDS):
        error = kde_capability_error(tweak_id, schema_cache=cache)
        if error:
            return {}, error
    root = cache.get(_CURSOR_SCHEMA, (None, ""))[0]
    if root is None:
        return {}, "The installed pointer settings schema is unavailable."
    values: dict[str, str] = {}
    for tweak_id in sorted(CURSOR_TWEAK_IDS):
        key = KDE_SPECS[tweak_id][2]
        entry = next(entry for group in root.findall(".//{*}group") if group.get("name") == "Mouse"
                     for entry in group.findall("{*}entry") if entry.get("key", entry.get("name")) == key)
        result = execute_read_only(kde_read_vector(tweak_id), action_id=f"set-{tweak_id}-read", timeout=8)
        if not result.success:
            return {}, result.message or "The current pointer configuration could not be read."
        value = result.stdout.strip() or entry.findtext("{*}default", "")
        if not valid_value(tweak_id, value):
            return {}, "The current pointer setting is invalid or outside its supported range."
        values[tweak_id] = value
    return values, ""


def _plasma_style_label(theme_id: str) -> str:
    """Read bounded presentation metadata; only the CLI grants theme membership."""
    roots = [Path(os.environ.get("XDG_DATA_HOME", str(Path.home() / ".local/share")))]
    for item in os.environ.get("XDG_DATA_DIRS", "/usr/local/share:/usr/share").split(":"):
        if len(roots) >= 16:
            break
        path = Path(item)
        if item and path not in roots:
            roots.append(path)
    for root in roots:
        try:
            with (root / "plasma/desktoptheme" / theme_id / "metadata.json").open("rb") as stream:
                data = stream.read(65537)
            if len(data) > 65536:
                continue
            name = json.loads(data).get("KPlugin", {}).get("Name", "")
            if isinstance(name, str) and name.strip() and len(name) <= 256 and not any(ord(char) < 32 for char in name):
                return name.strip()
        except (OSError, ValueError, TypeError, AttributeError, RecursionError):
            continue
    return theme_id


def _parse_themes(output: str, *, cursor: bool) -> tuple[str, tuple[tuple[str, str], ...]]:
    """Parse the closed Plasma CLI list format without accepting partial lists."""
    choices: list[tuple[str, str]] = []
    current = ""
    seen: set[str] = set()
    if len(output) > 256 * 1024:
        return "", ()
    for line in output.splitlines():
        stripped = line.strip()
        if not stripped.startswith("*"):
            continue
        match = re.fullmatch(r"\* (.+?) \[([^\[\]]+)\](?: \([^()\r\n]*\))?", stripped) if cursor else re.fullmatch(r"\* ([^ ()]+)(?: \([^()\r\n]*\))?", stripped)
        if not match:
            return "", ()
        identifier = match.group(2) if cursor else match.group(1)
        if not THEME_PATTERN.fullmatch(identifier) or identifier in seen or len(choices) >= 256:
            return "", ()
        label = match.group(1) if cursor else _plasma_style_label(identifier)
        if len(label) > 256 or any(ord(char) < 32 for char in label):
            return "", ()
        seen.add(identifier)
        choices.append((identifier, label))
        if stripped.endswith(")"):
            if current:
                return "", ()
            current = identifier
    return current, tuple(choices)


def read_tweak(
    tweak: Tweak,
    profile: object,
    execute_read_only: Callable[..., ActionResult],
    *,
    schema_cache: _KDESchemaCache | None = None,
) -> TweakState:
    desktop = _profile_desktop(profile)
    if desktop == "unknown" or tweak.desktop not in {"all", desktop}:
        return TweakState(tweak, "unavailable", message="This Fedora desktop or deployment is not supported.")
    if tweak.id == "dnf-parallel-downloads" and bool(getattr(profile, "is_atomic", False)):
        return TweakState(tweak, "unavailable", message="DNF configuration is not supported on Atomic Fedora.")
    if tweak.id.startswith("kde-dolphin-") and shutil.which("dolphin") is None:
        return TweakState(tweak, "unavailable", message="Dolphin is not installed.")
    capability_error = kde_capability_error(tweak.id, schema_cache=schema_cache) if schema_cache is not None else kde_capability_error(tweak.id)
    if capability_error:
        return TweakState(tweak, "unavailable", message=capability_error)
    if tweak.id in CURSOR_TWEAK_IDS:
        values, error = read_cursor_config(profile, execute_read_only, schema_cache=schema_cache)
        if error:
            return TweakState(tweak, "unavailable", message=error)
        choices = tweak.choices
        if tweak.id == "kde-cursor-theme":
            if shutil.which("plasma-apply-cursortheme") is None:
                return TweakState(tweak, "unavailable", value=values[tweak.id], message="The required KDE settings tool plasma-apply-cursortheme is unavailable.")
            listed = execute_read_only(["plasma-apply-cursortheme", "--list-themes"], action_id="set-kde-cursor-theme-list", timeout=8)
            if not listed.success:
                return TweakState(tweak, "unavailable", message=listed.message or "Installed pointer themes could not be read.")
            _current, choices = _parse_themes(listed.stdout, cursor=True)
        if not choices:
            return TweakState(tweak, "unavailable", value=values[tweak.id], message="No supported installed themes are available.")
        return TweakState(tweak, "ready", value=values[tweak.id], choices=choices)
    if tweak.id == "kde-plasma-style":
        listed = execute_read_only(["plasma-apply-desktoptheme", "--list-themes"], action_id="set-kde-plasma-style-list", timeout=8)
        if not listed.success:
            return TweakState(tweak, "unavailable", message=listed.message or "Installed Plasma styles could not be read.")
        _listed_current, choices = _parse_themes(listed.stdout, cursor=False)
        configured = execute_read_only(kde_read_vector(tweak.id), action_id="set-kde-plasma-style-read", timeout=8)
        if not configured.success:
            return TweakState(tweak, "unavailable", message=configured.message or "The saved Plasma style could not be read.")
        value = configured.stdout.strip()
        if not valid_value(tweak.id, value):
            return TweakState(tweak, "error", message="The saved Plasma style could not be validated.")
        if not choices:
            return TweakState(tweak, "unavailable", value=value, message="No supported installed themes are available.")
        return TweakState(tweak, "ready", value=value, choices=choices)
    result = execute_read_only(_read_vector(tweak), action_id=f"{tweak.action_id}-read", timeout=8)
    if not result.success:
        return TweakState(tweak, "unavailable", message=result.message or "The required system tool is unavailable.")
    output = result.stdout.strip()
    choices = tweak.choices
    if tweak.id == "kde-color":
        listed_current, choices = _parse_schemes(output)
        configured = execute_read_only(
            ["kreadconfig6", "--file", "kdeglobals", "--group", "General", "--key", "ColorScheme"],
            action_id="set-kde-color-current-read",
            timeout=8,
        )
        value = (configured.stdout.strip()[:128] if configured.success else "") or listed_current
    elif tweak.id == "power-profile":
        value = output
        available = execute_read_only(["powerprofilesctl", "list"], action_id="set-power-profile-list", timeout=8)
        if not available.success:
            return TweakState(tweak, "unavailable", message="Available power profiles could not be read.")
        choices = tuple((name, name.replace("-", " ").title()) for name in ("power-saver", "balanced", "performance") if re.search(rf"(?m)^\s*\*?\s*{name}:\s*$", available.stdout))
    elif tweak.id == "dnf-parallel-downloads":
        match = re.search(r"(?m)^\s*max_parallel_downloads\s*=\s*(\d+)", output)
        if match:
            value = match.group(1)
        elif output.isdigit():
            value = output
        else:
            value = ""
        choices = tweak.choices
    else:
        value = output.strip("'") if tweak.id in _GNOME_KEYS else output
    if tweak.id != "kde-color" and not valid_value(tweak.id, value):
        return TweakState(tweak, "error", message="The current setting value is invalid or outside its supported range.")
    if not value:
        return TweakState(tweak, "error", message="The current value could not be read.")
    if not choices:
        return TweakState(tweak, "unavailable", value=value, message="No supported choices are available.")
    return TweakState(tweak, "ready", value=value, choices=choices)


def snapshot(
    profile: object,
    runtime: ActionRuntime,
    *,
    tweak_ids: Sequence[str] | None = None,
    budget_seconds: float = 20.0,
    is_cancelled: Callable[[], bool] | None = None,
    on_progress: Callable[[int, int], None] | None = None,
    clock: Callable[[], float] = time.monotonic,
) -> tuple[TweakState, ...]:
    """Inspect visible settings within one bounded, cancellable time budget."""
    from core.tasks.tweak_history import restoration_for, read_tweak_runs

    runs, history_error = read_tweak_runs(runtime)
    visible = visible_tweaks(profile)
    if tweak_ids is None:
        tweaks = visible
    else:
        requested = tuple(dict.fromkeys(str(item) for item in tweak_ids))
        available = {tweak.id: tweak for tweak in visible}
        unknown = set(requested) - set(available)
        if unknown:
            raise ValueError("The requested setting is unavailable on this desktop.")
        tweaks = tuple(available[tweak_id] for tweak_id in requested)
    states: list[TweakState] = []
    requested_budget = float(budget_seconds)
    limit_seconds = min(_SNAPSHOT_BUDGET_SECONDS, max(0.0, requested_budget)) if math.isfinite(requested_budget) else 0.0
    started_at = clock()
    deadline = started_at + limit_seconds
    schema_cache: _KDESchemaCache = {}
    should_cancel = is_cancelled or (lambda: False)

    def bounded_reader(vector: list[str], *, action_id: str, timeout: int = 8) -> ActionResult:
        if should_cancel():
            return ActionResult.fail("Setting inspection cancelled.")
        remaining = deadline - clock()
        if remaining <= 0:
            return ActionResult.fail("The setting inspection time limit was reached.")
        return runtime.execute_read_only(vector, action_id=action_id, timeout=min(float(timeout), remaining))

    processed = 0
    for index, tweak in enumerate(tweaks):
        if should_cancel():
            stop_message = "Setting inspection cancelled before this setting was checked."
        elif clock() >= deadline:
            limit = f"{limit_seconds:g}"
            stop_message = f"Not checked because the {limit}-second setting inspection limit was reached."
        else:
            stop_message = ""
        if stop_message:
            remaining_states = tweaks[index:]
            states.extend(TweakState(item, "unavailable", message=stop_message) for item in remaining_states)
            if on_progress is not None:
                on_progress(processed, len(tweaks))
            break

        state = read_tweak(tweak, profile, bounded_reader, schema_cache=schema_cache)
        offer = restoration_for(tweak, state, runs)
        states.append(replace(state, restore_run_id=offer.source_run_id, restore_value=offer.before, restore_message=history_error or offer.message))
        processed += 1
        if on_progress is not None:
            on_progress(processed, len(tweaks))
    if not tweaks and on_progress is not None:
        on_progress(0, 0)
    return tuple(states)


def inspect_one(
    tweak_id: str,
    profile: object,
    runtime: ActionRuntime,
    *,
    budget_seconds: float = 8.0,
    is_cancelled: Callable[[], bool] | None = None,
    clock: Callable[[], float] = time.monotonic,
) -> TweakState:
    """Inspect one setting and its restore offer within one shared budget."""
    from core.tasks.tweak_history import read_tweak_runs, restoration_for

    tweak = BY_ID.get(str(tweak_id))
    if tweak is None:
        raise ValueError("Unknown tweak setting.")
    started = clock()
    budget = min(8.0, max(0.0, float(budget_seconds)))
    deadline = started + budget
    cancelled = is_cancelled or (lambda: False)

    def bounded_reader(vector: list[str], *, action_id: str, timeout: int = 8) -> ActionResult:
        if cancelled():
            return ActionResult.fail("Setting inspection cancelled.")
        remaining = deadline - clock()
        if remaining <= 0:
            return ActionResult.fail("The 8-second setting inspection time limit was reached.")
        return runtime.execute_read_only(vector, action_id=action_id, timeout=min(float(timeout), remaining))

    runs, history_error = read_tweak_runs(runtime)
    if cancelled():
        return TweakState(tweak, "unavailable", message="Setting inspection cancelled.")
    if clock() >= deadline:
        return TweakState(tweak, "unavailable", message="The 8-second setting inspection time limit was reached.")
    state = read_tweak(tweak, profile, bounded_reader)
    offer = restoration_for(tweak, state, runs)
    if cancelled():
        return TweakState(tweak, "unavailable", message="Setting inspection cancelled.")
    if clock() > deadline:
        return TweakState(tweak, "unavailable", message="The 8-second setting inspection time limit was reached.")
    return replace(state, restore_run_id=offer.source_run_id, restore_value=offer.before,
                   restore_message=history_error or offer.message)
