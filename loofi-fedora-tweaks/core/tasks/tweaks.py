"""Closed, read-only Fedora tweak catalog and current-state inspection."""

from __future__ import annotations

import re
from dataclasses import dataclass, replace
from typing import Callable, Sequence

from core.actions.contracts import ActionRuntime
from core.executor.action_result import ActionResult
from core.tweak_commands import GNOME_KEYS, KDE_KEYS, SCHEME_PATTERN, valid_value, kde_read_vector, kde_write_vector


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


TWEAKS = (
    Tweak("gnome-color", "Color preference", "Choose how GNOME apps prefer light or dark colors.", "Appearance", "gnome", "set-gnome-color", (("default", "System default"), ("prefer-light", "Light"), ("prefer-dark", "Dark"))),
    Tweak("gnome-animations", "Animations", "Turn GNOME interface motion on or off.", "Appearance", "gnome", "set-gnome-animations", (("true", "On"), ("false", "Off"))),
    Tweak("gnome-text-scale", "Text size", "Scale interface text without changing display resolution.", "Appearance", "gnome", "set-gnome-text-scale", (("1.0", "100%"), ("1.25", "125%"), ("1.5", "150%"))),
    Tweak("gnome-battery", "Battery percentage", "Show the battery percentage in the GNOME status area.", "Desktop", "gnome", "set-gnome-battery", (("true", "On"), ("false", "Off"))),
    Tweak("gnome-clock", "Clock seconds", "Show seconds in the GNOME top bar clock.", "Desktop", "gnome", "set-gnome-clock", (("true", "On"), ("false", "Off"))),
    Tweak("gnome-clock-format", "Clock format", "Use a 12-hour or 24-hour GNOME clock.", "Desktop", "gnome", "set-gnome-clock-format", (("12h", "12 hours"), ("24h", "24 hours"))),
    Tweak("gnome-clock-weekday", "Clock weekday", "Show the weekday alongside the GNOME clock.", "Desktop", "gnome", "set-gnome-clock-weekday", (("true", "Show"), ("false", "Hide"))),
    Tweak("kde-single-click", "Open files and folders", "Choose single-click or double-click opening in KDE applications.", "Interaction", "kde", "set-kde-single-click", (("true", "Single click"), ("false", "Double click"))),
    Tweak("kde-double-click-interval", "Double-click interval", "Choose how much time is allowed between the two clicks.", "Interaction", "kde", "set-kde-double-click-interval", (("200", "200 ms"), ("400", "400 ms"), ("600", "600 ms"), ("800", "800 ms"))),
    Tweak("kde-smooth-scroll", "Smooth scrolling", "Enable or disable smooth scrolling in supported KDE applications.", "Interaction", "kde", "set-kde-smooth-scroll", (("true", "On"), ("false", "Off"))),
    Tweak("kde-scrollbar-click", "Scrollbar track click", "Choose whether clicking the scrollbar track moves one page or jumps to the clicked position.", "Interaction", "kde", "set-kde-scrollbar-click", (("true", "Move one page"), ("false", "Jump to position"))),
    Tweak("kde-color", "Color scheme", "Choose an installed Plasma color scheme; custom schemes remain available.", "Appearance", "kde", "set-kde-color", ()),
    Tweak("kde-animation", "Animation speed", "Choose a Plasma animation speed; custom values remain untouched until changed.", "Appearance", "kde", "set-kde-animation", (("0", "Instant"), ("0.5", "Fast"), ("1", "Normal"))),
    Tweak("power-profile", "Power profile", "Choose an available power profile for this computer.", "Power", "all", "set-power-profile", (), True),
)
BY_ID = {tweak.id: tweak for tweak in TWEAKS}
BY_ACTION = {tweak.action_id: tweak for tweak in TWEAKS}


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
        return ["gsettings", "set", "org.gnome.desktop.interface", _GNOME_KEYS[tweak.id], value]
    if tweak.id == "kde-color":
        if not _SCHEME.fullmatch(value):
            raise ValueError("Unsupported Plasma color scheme identifier.")
        return ["plasma-apply-colorscheme", value]
    if tweak.id in KDE_KEYS:
        if not (restoring or allowed_value(tweak, value)):
            raise ValueError("Unsupported Plasma setting choice.")
        return kde_write_vector(tweak.id, value)
    if tweak.id == "power-profile":
        if not valid_value(tweak.id, value):
            raise ValueError("Unsupported power profile.")
        return ["powerprofilesctl", "set", value]
    raise ValueError("Unknown tweak.")


def _read_vector(tweak: Tweak) -> list[str]:
    if tweak.id in _GNOME_KEYS:
        return ["gsettings", "get", "org.gnome.desktop.interface", _GNOME_KEYS[tweak.id]]
    if tweak.id == "kde-color":
        return ["plasma-apply-colorscheme", "--list-schemes"]
    if tweak.id in KDE_KEYS:
        return kde_read_vector(tweak.id)
    if tweak.id == "power-profile":
        return ["powerprofilesctl", "get"]
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


def read_tweak(
    tweak: Tweak,
    profile: object,
    execute_read_only: Callable[..., ActionResult],
) -> TweakState:
    desktop = _profile_desktop(profile)
    if desktop == "unknown" or tweak.desktop not in {"all", desktop}:
        return TweakState(tweak, "unavailable", message="This Fedora desktop or deployment is not supported.")
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
    else:
        value = output.strip("'") if tweak.id in {"gnome-color", "gnome-clock-format"} else output
    if tweak.id != "kde-color" and not valid_value(tweak.id, value):
        return TweakState(tweak, "error", message="The current setting value is invalid or outside its supported range.")
    if not value:
        return TweakState(tweak, "error", message="The current value could not be read.")
    if not choices:
        return TweakState(tweak, "unavailable", value=value, message="No supported choices are available.")
    return TweakState(tweak, "ready", value=value, choices=choices)


def snapshot(profile: object, runtime: ActionRuntime) -> tuple[TweakState, ...]:
    from core.tasks.tweak_history import restoration_for, read_tweak_runs

    runs, history_error = read_tweak_runs(runtime)
    states = []
    for tweak in visible_tweaks(profile):
        state = read_tweak(tweak, profile, runtime.execute_read_only)
        offer = restoration_for(tweak, state, runs)
        states.append(replace(state, restore_run_id=offer.source_run_id, restore_value=offer.before, restore_message=history_error or offer.message))
    return tuple(states)
