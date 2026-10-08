"""Dependency-neutral, closed setting command shapes and scalar validation."""

from __future__ import annotations

import math
import re
from decimal import Decimal, InvalidOperation
from typing import Sequence, Literal

GNOME_KEYS = {
    "gnome-mouse-left-handed": "left-handed",
    "gnome-mouse-acceleration": "accel-profile",
    "gnome-keyboard-repeat": "repeat",
    "gnome-color": "color-scheme",
    "gnome-animations": "enable-animations",
    "gnome-text-scale": "text-scaling-factor",
    "gnome-battery": "show-battery-percentage",
    "gnome-clock": "clock-show-seconds",
    "gnome-clock-format": "clock-format",
    "gnome-clock-weekday": "clock-show-weekday",
    "gnome-button-layout": "button-layout",
    "gnome-tap-to-click": "tap-to-click",
    "gnome-night-light": "night-light-enabled",
    "gnome-sound-overamp": "allow-volume-above-100-percent",
    "gnome-font-antialiasing": "font-antialiasing",
    "gnome-hot-corners": "enable-hot-corners",
    "gnome-clock-date": "clock-show-date",
    "gnome-overlay-scrolling": "overlay-scrolling",
    "gnome-locate-pointer": "locate-pointer",
    "gnome-primary-paste": "gtk-enable-primary-paste",
    "gnome-recent-files": "remember-recent-files",
    "gnome-location": "enabled",
    "gnome-auto-trash": "remove-old-trash-files",
    "gnome-lock-enabled": "lock-enabled",
    "gnome-notification-banners": "show-banners",
    "gnome-lock-notifications": "show-in-lock-screen",
    "gnome-touchpad-natural-scroll": "natural-scroll",
    "gnome-mouse-natural-scroll": "natural-scroll",
    "gnome-disable-while-typing": "disable-while-typing",
    "gnome-click-method": "click-method",
    "gnome-dynamic-workspaces": "dynamic-workspaces",
    "gnome-edge-tiling": "edge-tiling",
    "gnome-center-new-windows": "center-new-windows",
    "gnome-attach-modal": "attach-modal-dialogs",
    "gnome-auto-raise": "auto-raise",
    "gnome-focus-mode": "focus-mode",
    "gnome-titlebar-double-click": "action-double-click-titlebar",
    "gnome-accent-color": "accent-color",
    "gnome-font-hinting": "font-hinting",
    "gnome-event-sounds": "event-sounds",
    "gnome-idle-dim": "idle-dim",
    "gnome-power-button": "power-button-action",
    "gnome-files-editable-location": "always-use-location-entry",
    "gnome-files-date-format": "date-time-format",
    "gnome-files-click-policy": "click-policy",
    "gnome-files-default-folder-view": "default-folder-viewer",
}
GNOME_SCHEMAS = {
    "gnome-mouse-left-handed": "org.gnome.desktop.peripherals.mouse",
    "gnome-mouse-acceleration": "org.gnome.desktop.peripherals.mouse",
    "gnome-keyboard-repeat": "org.gnome.desktop.peripherals.keyboard",
    "gnome-button-layout": "org.gnome.desktop.wm.preferences",
    "gnome-tap-to-click": "org.gnome.desktop.peripherals.touchpad",
    "gnome-night-light": "org.gnome.settings-daemon.plugins.color",
    "gnome-sound-overamp": "org.gnome.desktop.sound",
    "gnome-recent-files": "org.gnome.desktop.privacy",
    "gnome-location": "org.gnome.system.location",
    "gnome-auto-trash": "org.gnome.desktop.privacy",
    "gnome-lock-enabled": "org.gnome.desktop.screensaver",
    "gnome-notification-banners": "org.gnome.desktop.notifications",
    "gnome-lock-notifications": "org.gnome.desktop.notifications",
    "gnome-touchpad-natural-scroll": "org.gnome.desktop.peripherals.touchpad",
    "gnome-mouse-natural-scroll": "org.gnome.desktop.peripherals.mouse",
    "gnome-disable-while-typing": "org.gnome.desktop.peripherals.touchpad",
    "gnome-click-method": "org.gnome.desktop.peripherals.touchpad",
    "gnome-dynamic-workspaces": "org.gnome.mutter",
    "gnome-edge-tiling": "org.gnome.mutter",
    "gnome-center-new-windows": "org.gnome.mutter",
    "gnome-attach-modal": "org.gnome.mutter",
    "gnome-auto-raise": "org.gnome.desktop.wm.preferences",
    "gnome-focus-mode": "org.gnome.desktop.wm.preferences",
    "gnome-titlebar-double-click": "org.gnome.desktop.wm.preferences",
    "gnome-event-sounds": "org.gnome.desktop.sound",
    "gnome-idle-dim": "org.gnome.settings-daemon.plugins.power",
    "gnome-power-button": "org.gnome.settings-daemon.plugins.power",
    "gnome-files-editable-location": "org.gnome.nautilus.preferences",
    "gnome-files-date-format": "org.gnome.nautilus.preferences",
    "gnome-files-click-policy": "org.gnome.nautilus.preferences",
    "gnome-files-default-folder-view": "org.gnome.nautilus.preferences",
}


def gnome_schema(tweak_id: str) -> str:
    """Return the gsettings schema name for a GNOME tweak."""
    return GNOME_SCHEMAS.get(tweak_id, "org.gnome.desktop.interface")


CURSOR_TWEAK_IDS = frozenset({"kde-cursor-theme", "kde-cursor-size"})
THEME_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}")
CURSOR_NOTIFY = ("dbus-send", "--session", "--type=signal", "/KGlobalSettings", "org.kde.KGlobalSettings.notifyChange", "int32:5", "int32:0")

SNAP_TWEAK_IDS = frozenset({"kde-border-snap-zone", "kde-window-snap-zone"})
# Reviewed KWin enum order; validate it against the installed schema before use.
KWIN_PLACEMENT_VALUES = ("NoPlacement", "Default", "Unknown", "Random", "Smart", "Centered", "ZeroCornered", "UnderMouse", "OnMainWindow", "Maximizing")

KDE_SPECS = {
    "kde-window-placement": ("kwinrc", "Windows", "Placement", "Centered"),
    "kde-border-snap-zone": ("kwinrc", "Windows", "BorderSnapZone", "10"),
    "kde-window-snap-zone": ("kwinrc", "Windows", "WindowSnapZone", "10"),
    "kde-cursor-theme": ("kcminputrc", "Mouse", "cursorTheme", ""),
    "kde-cursor-size": ("kcminputrc", "Mouse", "cursorSize", "24"),
    "kde-plasma-style": ("plasmarc", "Theme", "name", "default"),
    "kde-animation": ("kdeglobals", "KDE", "AnimationDurationFactor", "1"),
    "kde-single-click": ("kdeglobals", "KDE", "SingleClick", "false"),
    "kde-double-click-interval": ("kdeglobals", "KDE", "DoubleClickInterval", "400"),
    "kde-smooth-scroll": ("kdeglobals", "KDE", "SmoothScroll", "true"),
    "kde-scrollbar-click": ("kdeglobals", "KDE", "ScrollbarLeftClickNavigatesByPage", "false"),
    "kde-tap-to-click": ("kcminputrc", "Touchpad", "TapToClick", "true"),
    "kde-night-color": ("kwinrc", "NightColor", "Active", "false"),
    "kde-focus-policy": ("kwinrc", "Windows", "FocusPolicy", "ClickToFocus"),
    "kde-titlebar-double-click": ("kwinrc", "Windows", "TitlebarDoubleClickCommand", "Maximize"),
    "kde-blur": ("kwinrc", "Plugins", "blurEnabled", "true"),
    "kde-translucency": ("kwinrc", "Plugins", "translucencyEnabled", "false"),
    "kde-wobbly-windows": ("kwinrc", "Plugins", "wobblywindowsEnabled", "false"),
    "kde-numlock": ("kcminputrc", "Keyboard", "NumLock", "2"),
    "kde-key-repeat": ("kcminputrc", "Keyboard", "KeyRepeat", "repeat"),
    "kde-autolock": ("kscreenlockerrc", "Daemon", "Autolock", "true"),
    "kde-lock-on-resume": ("kscreenlockerrc", "Daemon", "LockOnResume", "true"),
    "kde-confirm-logout": ("ksmserverrc", "General", "confirmLogout", "true"),
    "kde-login-mode": ("ksmserverrc", "General", "loginMode", "restorePreviousLogout"),
    "kde-show-delete": ("kdeglobals", "KDE", "ShowDeleteCommand", "false"),
    "kde-dolphin-editable-location": ("dolphinrc", "General", "EditableUrl", "false"),
    "kde-dolphin-remember-tabs": ("dolphinrc", "General", "RememberOpenedTabs", "true"),
    "kde-dolphin-external-folders-new-tab": ("dolphinrc", "General", "OpenExternallyCalledFolderInNewTab", "false"),
    "kde-dolphin-confirm-close-tabs": ("dolphinrc", "General", "ConfirmClosingMultipleTabs", "true"),
    "kde-edge-tiling": ("kwinrc", "Windows", "ElectricBorderTiling", "true"),
    "kde-focus-stealing-prevention": ("kwinrc", "Windows", "FocusStealingPreventionLevel", "1"),
    "kde-dolphin-show-full-path": ("dolphinrc", "General", "ShowFullPath", "false"),
    "kde-borderless-maximized-windows": ("kwinrc", "Windows", "BorderlessMaximizedWindows", "false"),
}
KDE_KEYS = {item: (spec[2], spec[3]) for item, spec in KDE_SPECS.items()}
SCHEME_PATTERN = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9._ -]{0,126}[A-Za-z0-9])?$")
_NUMERIC = re.compile(r"[0-9]+(?:\.[0-9]+)?(?:[eE][+-]?[0-9]+)?\Z")
_ENUMS = {
    "kde-window-placement": frozenset(KWIN_PLACEMENT_VALUES),
    "gnome-mouse-acceleration": frozenset({"default", "flat", "adaptive"}),
    "gnome-color": frozenset({"default", "prefer-light", "prefer-dark"}),
    "gnome-clock-format": frozenset({"12h", "24h"}),
    "gnome-button-layout": frozenset({":appmenu,close", ":minimize,maximize,close", "close,minimize,maximize:"}),
    "gnome-font-antialiasing": frozenset({"rgba", "grayscale", "none"}),
    "power-profile": frozenset({"power-saver", "balanced", "performance"}),
    "dnf-parallel-downloads": frozenset({"3", "5", "10", "15"}),
    "gnome-click-method": frozenset({"default", "areas", "fingers", "none"}),
    "gnome-focus-mode": frozenset({"click", "sloppy", "mouse"}),
    "gnome-titlebar-double-click": frozenset({"toggle-maximize", "minimize", "lower", "menu", "none"}),
    "gnome-accent-color": frozenset({"blue", "teal", "green", "yellow", "orange", "red", "pink", "purple", "slate"}),
    "gnome-font-hinting": frozenset({"none", "slight", "medium", "full"}),
    "gnome-power-button": frozenset({"suspend", "hibernate", "interactive", "nothing"}),
    "gnome-files-date-format": frozenset({"simple", "detailed"}),
    "kde-focus-stealing-prevention": frozenset({"0", "1", "2", "3", "4"}),
    "gnome-files-click-policy": frozenset({"single", "double"}),
    "gnome-files-default-folder-view": frozenset({"icon-view", "list-view"}),
    "kde-focus-policy": frozenset({"ClickToFocus", "FocusFollowsMouse", "FocusUnderMouse"}),
    "kde-titlebar-double-click": frozenset({"Maximize", "Minimize", "Shade", "Lower", "Nothing"}),
    "kde-numlock": frozenset({"0", "1", "2"}),
    "kde-key-repeat": frozenset({"repeat", "accent", "nothing"}),
    "kde-login-mode": frozenset({"restorePreviousLogout", "restoreSavedSession", "emptySession"}),
}
NUMERIC_TWEAKS = frozenset({"gnome-text-scale", "kde-animation", "kde-double-click-interval", "kde-cursor-size"}) | SNAP_TWEAK_IDS


def valid_value(tweak_id: str, value: str) -> bool:
    """Accept only typed setting literals, including restorable custom numbers."""
    if not isinstance(value, str) or not value or len(value) > 128:
        return False
    if tweak_id in _ENUMS:
        return value in _ENUMS[tweak_id]
    if tweak_id in {"kde-cursor-theme", "kde-plasma-style"}:
        return THEME_PATTERN.fullmatch(value) is not None
    if tweak_id == "kde-color":
        return SCHEME_PATTERN.fullmatch(value) is not None
    if tweak_id in NUMERIC_TWEAKS:
        if len(value) > 64 or not _NUMERIC.fullmatch(value):
            return False
        try:
            number = Decimal(value)
            if not math.isfinite(float(number)):
                return False
            if tweak_id == "gnome-text-scale":
                return Decimal("0.5") <= number <= Decimal("3")
            if tweak_id in SNAP_TWEAK_IDS:
                return value.isascii() and value.isdigit() and 0 <= number <= 1000
            if tweak_id == "kde-cursor-size":
                return value.isascii() and value.isdigit() and 0 <= number <= 512
            if tweak_id == "kde-double-click-interval":
                return value.isascii() and value.isdigit() and 100 <= number <= 2000
            return number >= 0
        except (InvalidOperation, OverflowError, ValueError):
            return False
    if tweak_id in GNOME_KEYS or tweak_id in KDE_KEYS:
        return value in {"true", "false"}
    return False


def values_equal(tweak_id: str, first: str, second: str) -> bool:
    """Compare numeric values without rounding or discarding saved precision."""
    if not valid_value(tweak_id, first) or not valid_value(tweak_id, second):
        return False
    if tweak_id in NUMERIC_TWEAKS:
        return Decimal(first) == Decimal(second)
    return first == second


def kde_read_vector(tweak_id: str) -> list[str]:
    file, group, key, default = KDE_SPECS[tweak_id]
    vector = ["kreadconfig6", "--file", file, "--group", group, "--key", key]
    return vector if tweak_id in CURSOR_TWEAK_IDS else vector + ["--default", default]


def kde_write_vector(tweak_id: str, value: str) -> list[str]:
    file, group, key, _default = KDE_SPECS[tweak_id]
    return ["kwriteconfig6", "--notify", "--file", file, "--group", group, "--key", key, value]


def tweak_command_class(binary: str, args: Sequence[str]) -> Literal["read_only", "session"] | None:
    """Recognize exact reviewed GNOME/KDE vectors; unknown shapes fail closed."""
    vector = tuple(args)
    if binary == "dbus-send" and vector in {KWIN_RECONFIGURE[1:], CURSOR_NOTIFY[1:]}:
        return "session"
    if binary == "gdbus" and vector == KWIN_SUPPORT[1:]:
        return "read_only"
    if binary in {"plasma-apply-cursortheme", "plasma-apply-desktoptheme"}:
        if vector == ("--list-themes",):
            return "read_only"
        if binary == "plasma-apply-desktoptheme" and len(vector) == 1 and valid_value("kde-plasma-style", vector[0]):
            return "session"
    if binary == "gsettings" and len(vector) in {3, 4}:
        schema = vector[1]
        key = vector[2]
        tweak_id = next((item for item, k in GNOME_KEYS.items() if k == key and gnome_schema(item) == schema), "")
        if tweak_id and vector[0] == "get" and len(vector) == 3:
            return "read_only"
        if tweak_id and vector[0] == "set" and len(vector) == 4 and valid_value(tweak_id, vector[3]):
            return "session"
    if binary == "kreadconfig6":
        if vector == ("--file", "kdeglobals", "--group", "General", "--key", "ColorScheme"):
            return "read_only"
        if any(vector == tuple(kde_read_vector(item)[1:]) for item in KDE_KEYS):
            return "read_only"
    if binary == "kwriteconfig6" and len(vector) == 8:
        for item in KDE_KEYS:
            if item == "kde-plasma-style":
                continue
            if vector[:-1] == tuple(kde_write_vector(item, "")[1:-1]) and valid_value(item, vector[-1]):
                return "session"
    return None


def custom_numeric_tweak(binary: str, args: Sequence[str]) -> str:
    """Identify safe custom writes requiring a matching restore authority."""
    vector = tuple(args)
    numeric_choices = {
        "gnome-text-scale": {"1.0", "1.25", "1.5"},
        "kde-animation": {"0", "0.5", "1"},
        "kde-double-click-interval": {"200", "400", "600", "800"},
        "kde-cursor-size": {"24", "32", "48", "64"},
        "kde-border-snap-zone": {"0", "10", "20", "30"},
        "kde-window-snap-zone": {"0", "10", "20", "30"},
        "kde-window-placement": {"Smart", "Centered", "UnderMouse"},
    }
    if tweak_command_class(binary, vector) != "session":
        return ""
    for tweak_id, choices in numeric_choices.items():
        if binary == "gsettings" and vector[2] == GNOME_KEYS.get(tweak_id):
            return tweak_id if vector[-1] not in choices else ""
        if tweak_id in KDE_KEYS and binary == "kwriteconfig6" and vector[:-1] == tuple(kde_write_vector(tweak_id, "")[1:-1]):
            return tweak_id if vector[-1] not in choices else ""
    return ""


KWIN_RECONFIGURE = ("dbus-send", "--session", "--type=method_call", "--dest=org.kde.KWin", "/KWin", "org.kde.KWin.reconfigure")
KWIN_SUPPORT = ("gdbus", "call", "--session", "--dest", "org.kde.KWin", "--object-path", "/KWin", "--method", "org.kde.KWin.supportInformation")
KWIN_RUNTIME_KEYS = {
    "kde-window-placement": "placement",
    "kde-border-snap-zone": "borderSnapZone",
    "kde-window-snap-zone": "windowSnapZone",
    "kde-edge-tiling": "electricBorderTiling",
    "kde-focus-stealing-prevention": "focusStealingPreventionLevel",
    "kde-borderless-maximized-windows": "borderlessMaximizedWindows",
}
