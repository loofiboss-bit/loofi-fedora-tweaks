"""Shared command allowlist and validation for executor entrypoints."""

from __future__ import annotations

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
        "fstrim",
        "fuser",
        "fwupdmgr",
        "gamemoded",
        "getenforce",
        "hostnamectl",
        "ip",
        "journalctl",
        "localectl",
        "lsblk",
        "lspci",
        "lsusb",
        "modinfo",
        "nbfc",
        "nmcli",
        "powerprofilesctl",
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


def validate_command_vector(command: Sequence[str]) -> None:
    """Validate a complete command vector."""
    if not command:
        _reject("command vector is empty")
    validate_command(str(command[0]), [str(arg) for arg in command[1:]])
