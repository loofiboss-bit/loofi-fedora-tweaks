"""
Operations Layer - Business logic extracted from UI tabs.
Provides reusable operations for both GUI and CLI.
"""

import logging
import subprocess
from dataclasses import dataclass
from typing import List, Tuple

logger = logging.getLogger(__name__)

from services.system import SystemManager  # noqa: E402
from utils.commands import PrivilegedCommand  # noqa: E402

from core.executor.action_result import ActionResult  # noqa: E402


@dataclass
class OperationResult:
    """Result of an operation."""

    success: bool
    message: str
    output: str = ""
    needs_reboot: bool = False


class CleanupOps:
    """Cleanup and maintenance operations."""

    @staticmethod
    def clean_dnf_cache() -> Tuple[str, List[str], str]:
        """Clean DNF package cache."""
        pm = SystemManager.get_package_manager()
        if pm == "rpm-ostree":
            return (
                "pkexec",
                ["rpm-ostree", "cleanup", "--base"],
                "Cleaning rpm-ostree base...",
            )
        return ("pkexec", ["dnf", "clean", "all"], "Cleaning DNF cache...")

    @staticmethod
    def autoremove() -> Tuple[str, List[str], str]:
        """Remove unused packages."""
        pm = SystemManager.get_package_manager()
        if pm == "rpm-ostree":
            return (
                "pkexec",
                ["rpm-ostree", "cleanup", "-m"],
                "Cleaning rpm-ostree metadata...",
            )
        return ("pkexec", ["dnf", "autoremove", "-y"], "Removing unused packages...")

    @staticmethod
    def vacuum_journal(days: int = 14) -> Tuple[str, List[str], str]:
        """Vacuum system journal."""
        return (
            "pkexec",
            ["journalctl", f"--vacuum-time={days}d"],
            f"Vacuuming journal ({days} days)...",
        )

    @staticmethod
    def trim_ssd() -> Tuple[str, List[str], str]:
        """TRIM SSD for performance."""
        return ("pkexec", ["fstrim", "-av"], "Trimming SSD...")

    @staticmethod
    def rebuild_rpmdb() -> Tuple[str, List[str], str]:
        """Rebuild RPM database."""
        return ("pkexec", ["rpm", "--rebuilddb"], "Rebuilding RPM database...")

    @staticmethod
    def list_timeshift() -> Tuple[str, List[str], str]:
        """List Timeshift snapshots."""
        return ("pkexec", ["timeshift", "--list"], "Listing Timeshift snapshots...")


class TweakOps:
    """HP Elitebook specific tweaks."""

    BATTERY_SYSFS = "/sys/class/power_supply/BAT0/charge_control_end_threshold"

    @staticmethod
    def set_power_profile(profile: str) -> Tuple[str, List[str], str]:
        """Set power profile (performance/balanced/power-saver)."""
        valid = ["performance", "balanced", "power-saver"]
        if profile not in valid:
            profile = "balanced"
        return (
            "powerprofilesctl",
            ["set", profile],
            f"Setting power profile to {profile}...",
        )

    @staticmethod
    def get_power_profile() -> str:
        """Get current power profile."""
        try:
            result = subprocess.run(
                ["powerprofilesctl", "get"],
                capture_output=True,
                text=True,
                check=False,
                timeout=10,
            )
            return result.stdout.strip() if result.returncode == 0 else "unknown"
        except (subprocess.SubprocessError, OSError) as e:
            logger.debug("Failed to get power profile: %s", e)
            return "unknown"

    @staticmethod
    def restart_audio() -> Tuple[str, List[str], str]:
        """Restart Pipewire audio services."""
        return (
            "systemctl",
            ["--user", "restart", "pipewire", "pipewire-pulse", "wireplumber"],
            "Restarting audio services...",
        )

    @staticmethod
    def set_battery_limit(limit: int) -> OperationResult:
        """Reject legacy direct mutation; use the named Action Center workflow."""
        if not 50 <= limit <= 100:
            return OperationResult(False, "Invalid limit (50-100)")
        return OperationResult(
            False,
            "Direct battery changes are disabled; review set-battery-limit in Action Center.",
        )

    @staticmethod
    def install_nbfc() -> Tuple[str, List[str], str]:
        """Install NBFC fan control.

        Note: systemctl enable must be run separately after install.
        """
        result: Tuple[str, List[str], str] = PrivilegedCommand.dnf(
            "install", "nbfc-linux"
        )
        return result

    @staticmethod
    def set_fan_profile(profile: str) -> Tuple[str, List[str], str]:
        """Set NBFC fan profile."""
        return (
            "nbfc",
            ["config", "-a", profile.lower()],
            f"Setting fan profile to {profile}...",
        )


class AdvancedOps:
    """Advanced system optimization operations."""

    @staticmethod
    def apply_dnf_tweaks() -> OperationResult:
        """Reject legacy direct mutation; use the named Action Center workflow."""
        return OperationResult(
            False,
            "Direct DNF configuration changes are disabled; review optimize-dnf-config in Action Center.",
        )

    @staticmethod
    def enable_tcp_bbr() -> OperationResult:
        """Reject legacy direct mutation; use the named Action Center workflow."""
        return OperationResult(
            False,
            "Direct kernel tuning is disabled; review enable-tcp-bbr in Action Center.",
        )

    @staticmethod
    def install_gamemode() -> OperationResult:
        """Reject legacy direct mutation; use the named Action Center workflow."""
        return OperationResult(
            False,
            "Direct package and group changes are disabled; review install-gamemode in Action Center.",
        )

    @staticmethod
    def set_swappiness(value: int = 10) -> OperationResult:
        """Reject legacy direct mutation; use the named Action Center workflow."""
        if not 0 <= value <= 100:
            return OperationResult(False, "Invalid swappiness value (0-100)")
        return OperationResult(
            False,
            "Direct kernel tuning is disabled; review set-swappiness in Action Center.",
        )


class NetworkOps:
    """Network configuration operations."""

    DNS_PROVIDERS = {
        "cloudflare": ("1.1.1.1", "1.0.0.1"),
        "google": ("8.8.8.8", "8.8.4.4"),
        "quad9": ("9.9.9.9", "149.112.112.112"),
        "opendns": ("208.67.222.222", "208.67.220.220"),
    }

    @staticmethod
    def set_dns(provider: str) -> OperationResult:
        """Reject legacy direct mutation; use the connection-scoped workflow."""
        if provider.lower() not in NetworkOps.DNS_PROVIDERS:
            return OperationResult(False, f"Unknown provider: {provider}")
        return OperationResult(
            False,
            "Direct DNS changes are disabled; review configure-network-dns in Action Center.",
        )


def execute_operation(
    op_tuple: Tuple[str, List[str], str],
    *,
    preview: bool = False,
) -> ActionResult:
    """
    Execute a tuple-style operation through the centralized ActionExecutor.

    Bridges existing (command, args, status) tuples to v19.0 ActionResult.
    Use this for CLI and headless execution paths.
    GUI paths continue using CommandRunner + QProcess.
    """
    from core.executor.action_executor import ActionExecutor

    command, args, _status = op_tuple
    pkexec = command == "pkexec"
    if pkexec:
        command = args[0]
        args = args[1:]
    return ActionExecutor.run(command, args, preview=preview, pkexec=pkexec)


# CLI command registry for future use
CLI_COMMANDS = {
    "cleanup": {
        "dnf": CleanupOps.clean_dnf_cache,
        "autoremove": CleanupOps.autoremove,
        "journal": CleanupOps.vacuum_journal,
        "trim": CleanupOps.trim_ssd,
        "rpmdb": CleanupOps.rebuild_rpmdb,
    },
    "tweak": {
        "power": TweakOps.set_power_profile,
        "audio": TweakOps.restart_audio,
        "battery": TweakOps.set_battery_limit,
    },
    "advanced": {
        "dnf-tweaks": AdvancedOps.apply_dnf_tweaks,
        "bbr": AdvancedOps.enable_tcp_bbr,
        "gamemode": AdvancedOps.install_gamemode,
        "swappiness": AdvancedOps.set_swappiness,
    },
    "network": {
        "dns": NetworkOps.set_dns,
    },
}
