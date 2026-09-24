"""Shared command allowlist and validation for executor entrypoints."""

from __future__ import annotations

import re
from typing import FrozenSet, Sequence


class CommandValidationError(ValueError):
    """Raised when a command fails executor policy validation."""


COMMAND_ALLOWLIST: FrozenSet[str] = frozenset(
    {
        "akmods",
        "btrfs",
        "cpupower",
        "df",
        "dnf",
        "dnf5",
        "echo",
        "firewall-cmd",
        "flatpak",
        "free",
        "gsettings",
        "fstrim",
        "fuser",
        "fwupdmgr",
        "gamemoded",
        "getenforce",
        "hostnamectl",
        "ip",
        "journalctl",
        "kreadconfig6",
        "kwriteconfig6",
        "localectl",
        "lsblk",
        "lspci",
        "lsusb",
        "modinfo",
        "nbfc",
        "nmcli",
        "powerprofilesctl",
        "plasma-apply-colorscheme",
        "rpm",
        "rpm-ostree",
        "sensors",
        "snapper",
        "ss",
        "sysctl",
        "systemctl",
        "timedatectl",
        "timeshift",
        "uname",
        "uptime",
        "usermod",
    }
)

_WRAPPERS: FrozenSet[str] = frozenset({"pkexec", "flatpak-spawn"})
_REJECTED_EXECUTABLES: FrozenSet[str] = frozenset({"sudo", "sh", "bash", "zsh", "fish", "dash"})
_RPM_EVALUATION_FLAGS: FrozenSet[str] = frozenset({"--eval", "-E", "--define", "--macros", "--rcfile"})
_GNOME_VALUES = {
    "color-scheme": frozenset({"default", "prefer-light", "prefer-dark"}),
    "enable-animations": frozenset({"true", "false"}),
    "text-scaling-factor": frozenset({"1.0", "1.25", "1.5"}),
    "show-battery-percentage": frozenset({"true", "false"}),
    "clock-show-seconds": frozenset({"true", "false"}),
}
_KDE_READ = ("--file", "kdeglobals", "--group", "KDE", "--key", "AnimationDurationFactor", "--default", "1")
_KDE_COLOR_READ = ("--file", "kdeglobals", "--group", "General", "--key", "ColorScheme")
_KDE_WRITE = ("--notify",) + _KDE_READ[:-2]
_SCHEME_PATTERN = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9._ -]{0,126}[A-Za-z0-9])?$")


def _reject(message: str) -> None:
    raise CommandValidationError(message)


def _validate_executable(command: str, *, allow_wrapper: bool = False) -> str:
    executable = str(command or "").strip()
    if not executable:
        _reject("command is empty")
    if "/" in executable or "\\" in executable:
        _reject(f"command must be a basename: {executable}")
    if executable in _REJECTED_EXECUTABLES:
        _reject(f"command is rejected by policy: {executable}")
    if executable in _WRAPPERS:
        if allow_wrapper:
            return executable
        _reject(f"wrapper command is only allowed at executor boundary: {executable}")
    if executable not in COMMAND_ALLOWLIST:
        _reject(f"command is not in allowlist: {executable}")
    return executable


def validate_command(command: str, args: Sequence[str] | None = None) -> None:
    """Validate an executor command before preview or execution."""
    args = list(args or [])
    executable = _validate_executable(command, allow_wrapper=True)

    if executable == "pkexec":
        if not args:
            _reject("pkexec requires a wrapped command")
        validate_command(args[0], args[1:])
        return

    if executable == "flatpak-spawn":
        if len(args) < 2 or args[0] != "--host":
            _reject("flatpak-spawn is only allowed as '--host <command>'")
        validate_command(args[1], args[2:])
        return

    if executable == "rpm" and any(str(arg).split("=", 1)[0] in _RPM_EVALUATION_FLAGS for arg in args):
        _reject("rpm macro evaluation and configuration flags are rejected by policy")

    if executable == "gsettings":
        if len(args) not in {3, 4} or args[0] not in {"get", "set"} or args[1] != "org.gnome.desktop.interface":
            _reject("gsettings is limited to reviewed GNOME interface settings")
        key = args[2]
        if key not in _GNOME_VALUES or (args[0] == "get" and len(args) != 3) or (args[0] == "set" and (len(args) != 4 or args[3] not in _GNOME_VALUES[key])):
            _reject("gsettings key or value is outside the reviewed tweak catalog")

    if executable == "kreadconfig6" and tuple(args) not in {_KDE_READ, _KDE_COLOR_READ}:
        _reject("kreadconfig6 is limited to reviewed Plasma settings")
    if executable == "kwriteconfig6" and (tuple(args[:-1]) != _KDE_WRITE or len(args) != len(_KDE_WRITE) + 1 or args[-1] not in {"0", "0.5", "1"}):
        _reject("kwriteconfig6 is limited to reviewed Plasma animation speeds")
    if executable == "plasma-apply-colorscheme" and tuple(args) != ("--list-schemes",):
        if len(args) != 1 or not _SCHEME_PATTERN.fullmatch(args[0]):
            _reject("Plasma color schemes must be reviewed installed identifiers")


def validate_command_vector(command: Sequence[str]) -> None:
    """Validate a complete command vector."""
    if not command:
        _reject("command vector is empty")
    validate_command(str(command[0]), [str(arg) for arg in command[1:]])
