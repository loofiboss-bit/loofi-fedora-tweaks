"""Shared command allowlist and validation for executor entrypoints."""

from __future__ import annotations

import re
from typing import FrozenSet, Sequence

from core.tweak_commands import tweak_command_class


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
        "dbus-send",
        "gdbus",
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

    if executable == "flatpak" and args and args[0] == "uninstall" and "--no-related" in args:
        # Installed-app removal has one closed, scope-bound shape. Other
        # historical Flatpak builders remain governed by their audited actions.
        valid_scope = len(args) == 6 and (
            args[1] in {"--user", "--system"}
            or re.fullmatch(r"--installation=[A-Za-z0-9][A-Za-z0-9_.-]{0,127}", args[1]) is not None
        )
        valid_ref = len(args) == 6 and re.fullmatch(r"app/[A-Za-z0-9][A-Za-z0-9._-]{1,255}/[A-Za-z0-9_-]+/[A-Za-z0-9._-]+", args[5]) is not None
        if not valid_scope or not valid_ref or args[2:5] != ["--assumeyes", "--noninteractive", "--no-related"]:
            _reject("Installed Flatpak removal requires one exact ref and explicit installation, preserving data")

    if executable in {"gsettings", "kreadconfig6", "kwriteconfig6", "dbus-send", "gdbus"} and tweak_command_class(executable, args) is None:
        _reject("Setting command is outside the reviewed keys, shapes, and value types")
    if executable == "plasma-apply-colorscheme" and tuple(args) != ("--list-schemes",):
        if len(args) != 1 or not _SCHEME_PATTERN.fullmatch(args[0]):
            _reject("Plasma color schemes must be reviewed installed identifiers")


def validate_command_vector(command: Sequence[str]) -> None:
    """Validate a complete command vector."""
    if not command:
        _reject("command vector is empty")
    validate_command(str(command[0]), [str(arg) for arg in command[1:]])
