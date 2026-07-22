"""Fail-closed classification for commands crossing execution boundaries."""

from __future__ import annotations

from pathlib import Path
from typing import Literal, Sequence

ExecutionClass = Literal["read_only", "host", "app_state", "session", "manual_only"]
ExecutionAuthority = Literal["legacy", "action_center"]

# Presentation-layer service calls that intentionally remain outside Action
# Center because they only affect user-owned application or live session state.
# Any mutator-like call not listed here is rejected by the Haven AST gate.
PRESENTATION_OPERATION_CLASSES: dict[tuple[str, str], ExecutionClass] = {
    ("BluetoothManager", "power_off"): "session",
    ("BluetoothManager", "power_on"): "session",
    ("ContainerManager", "create_container"): "app_state",
    ("ContainerManager", "delete_container"): "app_state",
    ("ContainerManager", "stop_container"): "session",
    ("DisposableVMManager", "create_base_image"): "app_state",
    ("DotfileManager", "create_dotfile_repo"): "app_state",
    ("KWinManager", "apply_tiling_preset"): "session",
    ("KWinManager", "enable_quick_tiling"): "session",
    ("KWinManager", "install_tiling_script"): "app_state",
    ("NavigationModeManager", "set_mode"): "app_state",
    ("NetworkUtils", "connect_wifi"): "session",
    ("NetworkUtils", "disconnect_wifi"): "session",
    ("ProfileManager", "create_custom_profile"): "app_state",
    ("ProfileManager", "delete_custom_profile"): "app_state",
    ("StateTeleportManager", "apply_teleport"): "app_state",
    ("StateTeleportManager", "create_teleport_package"): "app_state",
    ("TaskScheduler", "disable_service"): "app_state",
    ("TaskScheduler", "enable_service"): "app_state",
    ("TaskScheduler", "enable_task"): "app_state",
    ("TaskScheduler", "remove_task"): "app_state",
    ("VMManager", "create_vm"): "app_state",
    ("VMManager", "delete_vm"): "app_state",
    ("VMManager", "start_vm"): "session",
    ("VMManager", "stop_vm"): "session",
    ("WaylandDisplayManager", "disable_fractional_scaling"): "session",
    ("WaylandDisplayManager", "enable_fractional_scaling"): "session",
}


def presentation_operation_class(owner: str, method: str) -> ExecutionClass | None:
    """Return the explicit class for a presentation-to-service mutation."""
    return PRESENTATION_OPERATION_CLASSES.get((owner, method))


_SESSION_COMMANDS = frozenset(
    {
        "echo",
        "false",
        "git",
        "gio",
        "gsettings",
        "kscreen-doctor",
        "konsole",
        "lookandfeeltool",
        "bluetoothctl",
        "notify-send",
        "ollama",
        "xdg-open",
    }
)
_READ_ONLY_COMMANDS = frozenset(
    {
        "cat",
        "df",
        "du",
        "findmnt",
        "free",
        "fuser",
        "getent",
        "hostnamectl",
        "ip",
        "lsblk",
        "lscpu",
        "lspci",
        "lsusb",
        "mountpoint",
        "ps",
        "ss",
        "stat",
        "uname",
        "uptime",
    }
)


def _unwrap(command: str, args: Sequence[str]) -> tuple[str, tuple[str, ...], bool]:
    binary = Path(str(command)).name
    vector = tuple(str(item) for item in args)
    privileged = False
    if binary == "flatpak-spawn" and vector[:1] == ("--host",) and len(vector) >= 2:
        binary, vector = Path(vector[1]).name, vector[2:]
    if binary == "pkexec" and vector:
        privileged = True
        binary, vector = Path(vector[0]).name, vector[1:]
    return binary, vector, privileged


def classify_command(command: str, args: Sequence[str]) -> ExecutionClass:
    """Classify a complete command conservatively without executing probes."""
    binary, vector, privileged = _unwrap(command, args)
    first = vector[0] if vector else ""
    if privileged:
        return "host"
    if binary in _SESSION_COMMANDS:
        return "session"
    if binary in _READ_ONLY_COMMANDS:
        return "read_only"
    if binary in {"dnf", "dnf5"}:
        return "read_only" if first in {"check", "check-update", "info", "list", "repoquery", "repolist", "search"} else "host"
    if binary == "rpm":
        return "read_only" if first.startswith("-q") else "host"
    if binary == "rpm-ostree":
        if first in {"status", "db", "diff"} or (first == "upgrade" and "--check" in vector):
            return "read_only"
        return "host"
    if binary == "flatpak":
        return "read_only" if first in {"info", "list", "remote-info", "remote-ls", "remotes", "search"} else "host"
    if binary == "fwupdmgr":
        return "read_only" if first in {"get-devices", "get-history", "get-releases", "get-updates", "get-remotes"} else "host"
    if binary == "systemctl":
        return "read_only" if first in {"is-active", "is-enabled", "is-failed", "list-dependencies", "list-unit-files", "list-units", "show", "status", "--failed"} else "host"
    if binary == "journalctl":
        return "host" if any(item.startswith("--vacuum") for item in vector) else "read_only"
    if binary == "firewall-cmd":
        return "read_only" if first in {"--state", "--get-active-zones", "--get-default-zone", "--get-zones"} or any(item.startswith("--list") for item in vector) else "host"
    if binary == "nmcli":
        mutating = {"add", "connect", "delete", "disconnect", "down", "modify", "reload", "up"}
        return "host" if any(item in mutating for item in vector) else "read_only"
    if binary == "timeshift":
        return "read_only" if first in {"--list", "--check"} else "host"
    if binary == "snapper":
        return "read_only" if first in {"list", "list-configs", "status"} else "host"
    if binary in {"btrfs", "grub2-mkconfig", "modprobe", "rfkill", "sysctl", "tee", "tuned-adm"}:
        return "host"
    return "manual_only"


def execution_allowed(
    command: str,
    args: Sequence[str],
    *,
    authority: ExecutionAuthority = "legacy",
) -> bool:
    classification = classify_command(command, args)
    if classification in {"read_only", "session", "app_state"}:
        return True
    return authority == "action_center" and classification == "host"


def blocked_execution_message(command: str, args: Sequence[str]) -> str:
    classification = classify_command(command, args)
    if classification == "manual_only":
        return "The command is not classified for automatic execution and remains manual-only."
    return "Host changes must be planned, reviewed, and confirmed in Action Center."
