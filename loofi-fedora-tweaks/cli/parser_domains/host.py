"""CLI registration for host planning and management commands."""

from __future__ import annotations

import argparse

Subparsers = argparse._SubParsersAction


def register_basic_host_commands(subparsers: Subparsers) -> None:
    """Register the compact legacy host-planning command group."""
    cleanup_parser = subparsers.add_parser("cleanup", help="System cleanup operations")
    cleanup_parser.add_argument(
        "action",
        choices=["all", "dnf", "journal", "trim", "autoremove", "rpmdb"],
        default="all",
        nargs="?",
        help="Cleanup action to perform",
    )
    cleanup_parser.add_argument("--days", type=int, choices=[7, 14, 30], default=14, help="Days to keep journal")

    tweak_parser = subparsers.add_parser("tweak", help="Hardware tweaks (power, audio, battery)")
    tweak_parser.add_argument("action", choices=["power", "audio", "battery", "status"], help="Tweak action")
    tweak_parser.add_argument(
        "--profile",
        choices=["performance", "balanced", "power-saver"],
        default="balanced",
        help="Power profile",
    )
    tweak_parser.add_argument("--limit", type=int, default=80, help="Battery limit (50-100)")

    advanced_parser = subparsers.add_parser("advanced", help="Advanced optimizations")
    advanced_parser.add_argument(
        "action",
        choices=["dnf-tweaks", "bbr", "gamemode", "swappiness"],
        help="Optimization action",
    )
    advanced_parser.add_argument("--value", type=int, default=10, help="Value for swappiness")

    network_parser = subparsers.add_parser("network", help="Network configuration")
    network_parser.add_argument("action", choices=["dns"], help="Network action")
    network_parser.add_argument(
        "--provider",
        choices=["cloudflare", "google", "quad9", "opendns"],
        default="cloudflare",
        help="DNS provider",
    )
    network_parser.add_argument(
        "--connection",
        required=True,
        help="Exact NetworkManager connection name to review",
    )


def _register_service_command(subparsers: Subparsers) -> None:
    """Register systemd service inspection and planning."""
    service_parser = subparsers.add_parser("service", help="Systemd service management")
    service_parser.add_argument(
        "action",
        choices=["list", "start", "stop", "restart", "enable", "disable", "mask", "unmask", "logs", "status"],
        help="Service action",
    )
    service_parser.add_argument("name", nargs="?", help="Service name")
    service_parser.add_argument("--user", action="store_true", help="User scope (default: system)")
    service_parser.add_argument(
        "--filter",
        choices=["active", "inactive", "failed"],
        help="Filter by state (for list)",
    )
    service_parser.add_argument("--search", help="Search filter (for list)")
    service_parser.add_argument("--lines", type=int, default=50, help="Log lines (for logs)")


def _register_package_and_firewall_commands(subparsers: Subparsers) -> None:
    """Register package and firewall inspection and planning."""
    package_parser = subparsers.add_parser("package", help="Package search and management")
    package_parser.add_argument(
        "action",
        choices=["search", "install", "remove", "list", "recent"],
        help="Package action",
    )
    package_parser.add_argument("name", nargs="?", help="Package name (for install/remove)")
    package_parser.add_argument("--query", help="Search query (for search)")
    package_parser.add_argument("--source", choices=["dnf", "flatpak", "all"], help="Package source filter")
    package_parser.add_argument("--search", help="Filter installed packages")
    package_parser.add_argument("--days", type=int, default=30, help="Days for recent")

    firewall_parser = subparsers.add_parser("firewall", help="Firewall management")
    firewall_parser.add_argument(
        "action",
        choices=["status", "ports", "open-port", "close-port", "services", "zones"],
        help="Firewall action",
    )
    firewall_parser.add_argument("spec", nargs="?", help="Port spec (e.g. 8080/tcp)")


def _register_device_and_update_commands(subparsers: Subparsers) -> None:
    """Register Bluetooth, storage, and self-update commands."""
    bluetooth_parser = subparsers.add_parser("bluetooth", help="Bluetooth management")
    bluetooth_parser.add_argument(
        "action",
        choices=["status", "devices", "scan", "power-on", "power-off", "connect", "disconnect", "pair", "unpair", "trust"],
        help="Bluetooth action",
    )
    bluetooth_parser.add_argument("address", nargs="?", help="Device MAC address")
    bluetooth_parser.add_argument("--paired", action="store_true", help="Show paired only")
    bluetooth_parser.add_argument("--timeout", type=int, default=10, help="Scan timeout")

    storage_parser = subparsers.add_parser("storage", help="Storage & disk management")
    storage_parser.add_argument(
        "action",
        choices=["disks", "mounts", "smart", "usage", "trim"],
        help="Storage action",
    )
    storage_parser.add_argument("device", nargs="?", help="Device path (e.g. /dev/sda)")

    update_parser = subparsers.add_parser("self-update", help="Check/download verified Loofi updates")
    update_parser.add_argument(
        "action", choices=["check", "run"], default="run", nargs="?", help="Self-update action: check for updates or run the update"
    )
    update_parser.add_argument(
        "--channel", choices=["auto", "rpm", "flatpak", "appimage"], default="auto", help="Update channel to use (default: auto-detect)"
    )
    update_parser.add_argument("--download-dir", default="~/.cache/loofi-fedora-tweaks/updates", help="Directory to download updates to")
    update_parser.add_argument("--timeout", type=int, default=30, help="Download timeout in seconds (default: 30)")
    update_parser.add_argument("--no-cache", action="store_true", help="Skip cached update packages")
    update_parser.add_argument("--checksum", default="", help="Expected SHA256 checksum of the update package")
    update_parser.add_argument("--signature-path", help="Path to GPG signature file for verification")
    update_parser.add_argument("--public-key-path", help="Path to GPG public key for signature verification")


def register_system_management_commands(subparsers: Subparsers) -> None:
    """Register host-management commands that precede the agent command."""
    _register_service_command(subparsers)
    _register_package_and_firewall_commands(subparsers)
    _register_device_and_update_commands(subparsers)


def register_post_agent_commands(subparsers: Subparsers) -> None:
    """Register the remaining host commands after the agent compatibility entry."""
    audit_parser = subparsers.add_parser("audit-log", help="View recent audit log entries")
    audit_parser.add_argument("--count", type=int, default=20, help="Number of entries to show (default: 20)")

    updates_parser = subparsers.add_parser("updates", help="Smart update management")
    updates_parser.add_argument(
        "action",
        choices=["check", "conflicts", "schedule", "rollback", "history"],
        help="Update action to perform",
    )
    updates_parser.add_argument("--time", default="02:00", help="Schedule time (HH:MM, default: 02:00)")

    extension_parser = subparsers.add_parser("extension", help="Desktop extension management")
    extension_parser.add_argument(
        "action",
        choices=["list", "install", "remove", "enable", "disable"],
        help="Extension action",
    )
    extension_parser.add_argument("--uuid", help="Extension UUID for install/remove/enable/disable")

    flatpak_parser = subparsers.add_parser("flatpak-manage", help="Flatpak management tools")
    flatpak_parser.add_argument(
        "action",
        choices=["sizes", "permissions", "orphans", "cleanup"],
        help="Flatpak action",
    )

    boot_parser = subparsers.add_parser("boot", help="Boot configuration management")
    boot_parser.add_argument("action", choices=["config", "kernels", "timeout", "apply"], help="Boot action")
    boot_parser.add_argument("--seconds", type=int, help="Timeout in seconds (for timeout action)")

    display_parser = subparsers.add_parser("display", help="Display and Wayland configuration")
    display_parser.add_argument(
        "action",
        choices=["list", "session", "fractional-on", "fractional-off"],
        help="Display action",
    )

    backup_parser = subparsers.add_parser("backup", help="Snapshot backup management")
    backup_parser.add_argument(
        "action",
        choices=["detect", "create", "list", "restore", "delete", "status"],
        help="Backup action",
    )
    backup_parser.add_argument("--tool", help="Backup tool (timeshift/snapper)")
    backup_parser.add_argument("--description", help="Snapshot description (for create)")
    backup_parser.add_argument("--snapshot-id", help="Snapshot ID (for restore/delete)")
