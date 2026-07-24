"""Public CLI parser construction."""

from __future__ import annotations

import argparse

from core.fedora_release_policy import FEDORA_RELEASE_POLICY
from version import __version__, __version_codename__


def build_parser() -> argparse.ArgumentParser:
    """Build the public CLI parser without executing a handler."""
    parser = argparse.ArgumentParser(
        prog="loofi",
        description=f'Loofi Fedora Tweaks v{__version__} "{__version_codename__}" - System management CLI',
    )
    parser.add_argument(
        "-v",
        "--version",
        action="version",
        version=f'{__version__} "{__version_codename__}"',
    )
    parser.add_argument("--json", action="store_true", help="Output in JSON format (for scripting)")
    parser.add_argument(
        "--timeout",
        type=int,
        default=300,
        help="Operation timeout in seconds (default: 300)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show commands without executing them (v35.0)",
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Info command
    subparsers.add_parser("info", help="Show system information")

    # Health command
    health_parser = subparsers.add_parser("health", help="System Check and compatibility health commands")
    health_subparsers = health_parser.add_subparsers(dest="health_action", help="System Check commands")
    health_subparsers.add_parser("check", help="Run and persist the explicit read-only System Check")
    health_subparsers.add_parser("findings", help="Show findings from the latest saved System Check")
    health_subparsers.add_parser("comparison", help="Show the latest compatible before/after finding outcomes")
    health_history_parser = health_subparsers.add_parser("history", help="Show saved checks and before/after history")
    health_history_parser.add_argument("--limit", type=int, default=10, help="History limit")
    health_snapshot_parser = health_subparsers.add_parser("snapshot", help="Record a My Fedora Today health snapshot")
    health_snapshot_parser.add_argument(
        "--target", choices=FEDORA_RELEASE_POLICY.action_targets, default=FEDORA_RELEASE_POLICY.stable_target, help="Readiness target profile"
    )
    health_timeline_parser = health_subparsers.add_parser("timeline", help="Compatibility alias for persisted health snapshots")
    health_timeline_parser.add_argument("--limit", type=int, default=10, help="Snapshot limit")

    maintenance_parser = subparsers.add_parser("maintenance", help="Daily maintenance health commands")
    maintenance_subparsers = maintenance_parser.add_subparsers(dest="maintenance_action", help="Maintenance commands")
    maintenance_today_parser = maintenance_subparsers.add_parser("today", help="Show My Fedora Today maintenance state")
    maintenance_today_parser.add_argument(
        "--target", choices=FEDORA_RELEASE_POLICY.action_targets, default=FEDORA_RELEASE_POLICY.stable_target, help="Readiness target profile"
    )
    maintenance_today_parser.add_argument("--json", action="store_true", help="Output in JSON format")

    # Disk command
    disk_parser = subparsers.add_parser("disk", help="Disk usage information")
    disk_parser.add_argument("--details", action="store_true", help="Show large directories")

    # Process monitor command
    proc_parser = subparsers.add_parser("processes", help="Show top processes")
    proc_parser.add_argument("-n", "--count", type=int, default=10, help="Number of processes to show")
    proc_parser.add_argument("--sort", choices=["cpu", "memory"], default="cpu", help="Sort by")

    # Temperature command
    subparsers.add_parser("temperature", help="Show temperature readings")

    # Network monitor command
    netmon_parser = subparsers.add_parser("netmon", help="Network interface monitoring")
    netmon_parser.add_argument("--connections", action="store_true", help="Show active connections")

    # Cleanup subcommand
    cleanup_parser = subparsers.add_parser("cleanup", help="System cleanup operations")
    cleanup_parser.add_argument(
        "action",
        choices=["all", "dnf", "journal", "trim", "autoremove", "rpmdb"],
        default="all",
        nargs="?",
        help="Cleanup action to perform",
    )
    cleanup_parser.add_argument("--days", type=int, choices=[7, 14, 30], default=14, help="Days to keep journal")

    # Tweak subcommand
    tweak_parser = subparsers.add_parser("tweak", help="Hardware tweaks (power, audio, battery)")
    tweak_parser.add_argument("action", choices=["power", "audio", "battery", "status"], help="Tweak action")
    tweak_parser.add_argument(
        "--profile",
        choices=["performance", "balanced", "power-saver"],
        default="balanced",
        help="Power profile",
    )
    tweak_parser.add_argument("--limit", type=int, default=80, help="Battery limit (50-100)")

    # Advanced subcommand
    adv_parser = subparsers.add_parser("advanced", help="Advanced optimizations")
    adv_parser.add_argument(
        "action",
        choices=["dnf-tweaks", "bbr", "gamemode", "swappiness"],
        help="Optimization action",
    )
    adv_parser.add_argument("--value", type=int, default=10, help="Value for swappiness")

    # Network subcommand
    net_parser = subparsers.add_parser("network", help="Network configuration")
    net_parser.add_argument("action", choices=["dns"], help="Network action")
    net_parser.add_argument(
        "--provider",
        choices=["cloudflare", "google", "quad9", "opendns"],
        default="cloudflare",
        help="DNS provider",
    )

    # v10.0 new commands
    subparsers.add_parser("doctor", help="Check system dependencies and diagnostics")
    subparsers.add_parser("hardware", help="Show detected hardware profile")

    # Plugin management
    plugin_parser = subparsers.add_parser("plugins", help="Inspect retired legacy extensions")
    plugin_parser.add_argument("action", choices=["list", "enable", "disable"], help="Plugin action")
    plugin_parser.add_argument("name", nargs="?", help="Plugin name for enable/disable")

    api_key_parser = subparsers.add_parser("api-key", help="Manage the loopback Web API credential")
    api_key_parser.add_argument(
        "action",
        choices=["status", "rotate", "revoke"],
        help="Credential lifecycle action",
    )

    # v26.0 - Plugin marketplace
    marketplace_parser = subparsers.add_parser("plugin-marketplace", help=argparse.SUPPRESS)
    marketplace_parser.add_argument(
        "action",
        choices=[
            "search",
            "install",
            "uninstall",
            "update",
            "info",
            "list-installed",
            "reviews",
            "review-submit",
            "rating",
        ],
        help="Marketplace action",
    )
    marketplace_parser.add_argument("plugin", nargs="?", help="Plugin name or ID")
    marketplace_parser.add_argument("--category", help="Filter by category")
    marketplace_parser.add_argument("--query", help="Search query")
    marketplace_parser.add_argument("--limit", type=int, default=20, help="Review fetch limit (for reviews)")
    marketplace_parser.add_argument("--offset", type=int, default=0, help="Review fetch offset (for reviews)")
    marketplace_parser.add_argument("--reviewer", help="Reviewer name (for review-submit)")
    marketplace_parser.add_argument("--rating", type=int, help="Rating 1-5 (for review-submit)")
    marketplace_parser.add_argument("--title", help="Review title (for review-submit)")
    marketplace_parser.add_argument("--comment", help="Review comment (for review-submit)")
    marketplace_parser.add_argument(
        "--accept-permissions",
        action="store_true",
        help="Auto-accept permissions (non-interactive)",
    )

    # Support bundle
    subparsers.add_parser("support-bundle", help="Export support bundle ZIP")

    state_parser = subparsers.add_parser("state", help="Inspect, back up, and recover Loofi state")
    state_subparsers = state_parser.add_subparsers(dest="state_action")
    state_subparsers.add_parser("doctor", help="Validate state without changing it")
    state_backup_parser = state_subparsers.add_parser("backup", help="Create a privacy-safe state archive")
    state_backup_parser.add_argument("--output", required=True, help="Destination ZIP path")
    state_restore_parser = state_subparsers.add_parser("restore", help="Plan or explicitly apply a restore")
    state_restore_subparsers = state_restore_parser.add_subparsers(dest="restore_action")
    state_restore_plan = state_restore_subparsers.add_parser("plan", help="Validate and preview an archive")
    state_restore_plan.add_argument("archive")
    state_restore_apply = state_restore_subparsers.add_parser("apply", help="Apply an existing restore plan")
    state_restore_apply.add_argument("archive")
    state_restore_apply.add_argument("--plan-id", required=True)

    readiness_parser = subparsers.add_parser("readiness", help="Run release readiness diagnostics")
    readiness_parser.add_argument(
        "--target", choices=FEDORA_RELEASE_POLICY.action_targets, default=FEDORA_RELEASE_POLICY.stable_target, help="Readiness target profile"
    )
    readiness_parser.add_argument("--advanced", action="store_true", help="Show raw command and status details")
    readiness_subparsers = readiness_parser.add_subparsers(dest="readiness_action", help="Readiness action commands")

    readiness_actions_parser = readiness_subparsers.add_parser("actions", help="List safe readiness action candidates")
    readiness_actions_parser.add_argument(
        "--target", choices=FEDORA_RELEASE_POLICY.action_targets, default=FEDORA_RELEASE_POLICY.stable_target, help="Readiness target profile"
    )

    readiness_plan_parser = readiness_subparsers.add_parser("plan", help="Show guided release upgrade plan")
    readiness_plan_parser.add_argument(
        "--target", choices=FEDORA_RELEASE_POLICY.action_targets, default=FEDORA_RELEASE_POLICY.stable_target, help="Readiness target profile"
    )

    readiness_explain_parser = readiness_subparsers.add_parser("explain", help="Explain one readiness check")
    readiness_explain_parser.add_argument("action_id", help="Readiness check ID")
    readiness_explain_parser.add_argument(
        "--target", choices=FEDORA_RELEASE_POLICY.action_targets, default=FEDORA_RELEASE_POLICY.stable_target, help="Readiness target profile"
    )

    readiness_export_parser = readiness_subparsers.add_parser("export", help="Export readiness support bundle")
    readiness_export_parser.add_argument(
        "--target", choices=FEDORA_RELEASE_POLICY.action_targets, default=FEDORA_RELEASE_POLICY.stable_target, help="Readiness target profile"
    )
    readiness_export_parser.add_argument("--path", help="Output JSON path")

    readiness_info_parser = readiness_subparsers.add_parser("action-info", help="Show one readiness action candidate")
    readiness_info_parser.add_argument("action_id", help="Readiness action ID")
    readiness_info_parser.add_argument(
        "--target", choices=FEDORA_RELEASE_POLICY.action_targets, default=FEDORA_RELEASE_POLICY.stable_target, help="Readiness target profile"
    )

    readiness_preview_parser = readiness_subparsers.add_parser("action-preview", help="Preview one readiness action")
    readiness_preview_parser.add_argument("action_id", help="Readiness action ID")
    readiness_preview_parser.add_argument(
        "--target", choices=FEDORA_RELEASE_POLICY.action_targets, default=FEDORA_RELEASE_POLICY.stable_target, help="Readiness target profile"
    )

    readiness_run_parser = readiness_subparsers.add_parser("action-run", help="Run a confirmed readiness action")
    readiness_run_parser.add_argument("action_id", help="Readiness action ID")
    readiness_run_parser.add_argument(
        "--target", choices=FEDORA_RELEASE_POLICY.action_targets, default=FEDORA_RELEASE_POLICY.stable_target, help="Readiness target profile"
    )
    readiness_run_parser.add_argument("--confirm", action="store_true", help="Confirm the selected mutating action")

    readiness_verify_parser = readiness_subparsers.add_parser("action-verify", help="Verify one readiness action")
    readiness_verify_parser.add_argument("action_id", help="Readiness action ID")
    readiness_verify_parser.add_argument(
        "--target", choices=FEDORA_RELEASE_POLICY.action_targets, default=FEDORA_RELEASE_POLICY.stable_target, help="Readiness target profile"
    )

    action_center_parser = subparsers.add_parser("action-center", help="Plan, verify, and inspect guided maintenance actions")
    action_center_parser.add_argument(
        "action",
        choices=["list", "preview", "history", "recommendations", "plan", "show", "apply", "verify"],
        nargs="?",
        default="list",
        help="Action Center command",
    )
    action_center_parser.add_argument("action_id", nargs="?", help="Action ID, plan ID, or run ID for the selected command")
    action_center_parser.add_argument(
        "--target", choices=FEDORA_RELEASE_POLICY.action_targets, default=FEDORA_RELEASE_POLICY.stable_target, help="Readiness target profile"
    )
    action_center_parser.add_argument("--limit", type=int, default=25, help="History entry limit")
    action_center_parser.add_argument("--service", help="Exact failed systemd unit for restart-failed-service")
    action_center_parser.add_argument("--package-id", help="Exact Fedora package name or Flatpak reference")
    action_center_parser.add_argument("--source", choices=["fedora", "flatpak"], help="Application package source")
    action_center_parser.add_argument("--backend", choices=["timeshift", "snapper"], help="Recovery-point backend")
    action_center_parser.add_argument("--description", help="Recovery-point description")
    action_center_parser.add_argument("--days", type=int, choices=[7, 14, 30], help="Journal retention in days")
    action_center_parser.add_argument("--confirm", action="store_true", help="Explicitly confirm application of the reviewed plan")
    action_center_parser.add_argument(
        "--accept-no-rollback",
        action="store_true",
        help="Explicitly accept a medium/high-risk action without supported rollback",
    )

    fedora44_parser = subparsers.add_parser("fedora44-readiness", help="Compatibility alias for 'readiness --target 44'")
    fedora44_parser.add_argument("--advanced", action="store_true", help="Show raw command and status details")

    # ==================== v11.5 / v12.0 subparsers ====================

    # VM management
    vm_parser = subparsers.add_parser("vm", help="Virtual machine management")
    vm_parser.add_argument("action", choices=["list", "status", "start", "stop"], help="VM action")
    vm_parser.add_argument("name", nargs="?", help="VM name (for status/start/stop)")

    # VFIO GPU passthrough
    vfio_parser = subparsers.add_parser("vfio", help="GPU passthrough assistant")
    vfio_parser.add_argument("action", choices=["check", "gpus", "plan"], help="VFIO action")

    # Mesh networking
    mesh_parser = subparsers.add_parser("mesh", help="Loofi Link mesh networking")
    mesh_parser.add_argument("action", choices=["discover", "status"], help="Mesh action")

    # State Teleport
    teleport_parser = subparsers.add_parser("teleport", help="State Teleport workspace capture/restore")
    teleport_parser.add_argument("action", choices=["capture", "list", "restore"], help="Teleport action")
    teleport_parser.add_argument("--path", help="Workspace path for capture")
    teleport_parser.add_argument("--target", default="unknown", help="Target device name")
    teleport_parser.add_argument("package_id", nargs="?", help="Package ID for restore")

    # AI Models
    ai_models_parser = subparsers.add_parser("ai-models", help="AI model management")
    ai_models_parser.add_argument("action", choices=["list", "recommend"], help="AI models action")

    # Preset management
    preset_parser = subparsers.add_parser("preset", help="Manage system presets")
    preset_parser.add_argument("action", choices=["list", "apply", "export"], help="Preset action")
    preset_parser.add_argument("name", nargs="?", help="Preset name (for apply/export)")
    preset_parser.add_argument("path", nargs="?", help="Export path (for export)")

    # Focus mode
    focus_parser = subparsers.add_parser("focus-mode", help="Focus mode distraction blocking")
    focus_parser.add_argument("action", choices=["on", "off", "status"], help="Focus mode action")
    focus_parser.add_argument("--profile", default="default", help="Profile to use (default: default)")

    # Security audit
    subparsers.add_parser("security-audit", help="Run security audit and show score")

    # v13.0 Nexus Update - Profile management
    profile_parser = subparsers.add_parser("profile", help="System profile management")
    profile_parser.add_argument(
        "action",
        choices=[
            "list",
            "apply",
            "create",
            "delete",
            "export",
            "import",
            "export-all",
            "import-all",
        ],
        help="Profile action",
    )
    profile_parser.add_argument("name", nargs="?", help="Profile name (for apply/create/delete/export)")
    profile_parser.add_argument("path", nargs="?", help="Import/export file path")
    profile_parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Overwrite existing custom profiles on import",
    )
    profile_parser.add_argument(
        "--no-snapshot",
        action="store_true",
        help="Skip snapshot creation when applying profiles",
    )
    profile_parser.add_argument(
        "--include-builtins",
        action="store_true",
        help="Include built-in profiles in export-all bundle",
    )

    # v13.0 Nexus Update - Health history
    health_history_parser = subparsers.add_parser("health-history", help="Health timeline metrics")
    health_history_parser.add_argument(
        "action",
        choices=["show", "record", "export", "prune"],
        help="Health history action",
    )
    health_history_parser.add_argument("path", nargs="?", help="Export path (for export)")

    # ==================== v15.0 Nebula subparsers ====================

    # Performance auto-tuner
    tuner_parser = subparsers.add_parser("tuner", help="Performance auto-tuner")
    tuner_parser.add_argument("action", choices=["analyze", "apply", "history"], help="Tuner action")

    # Snapshot management
    snapshot_parser = subparsers.add_parser("snapshot", help="System snapshot management")
    snapshot_parser.add_argument(
        "action",
        choices=["list", "create", "delete", "backends"],
        help="Snapshot action",
    )
    snapshot_parser.add_argument("--label", help="Snapshot label (for create)")
    snapshot_parser.add_argument("--backend", choices=["timeshift", "snapper"], help="Verified backend for create")
    snapshot_parser.add_argument("snapshot_id", nargs="?", help="Snapshot ID (for delete)")

    # Smart log viewer
    logs_parser = subparsers.add_parser("logs", help="Smart log viewer with pattern detection")
    logs_parser.add_argument("action", choices=["show", "errors", "export"], help="Logs action")
    logs_parser.add_argument("--unit", help="Filter by systemd unit")
    logs_parser.add_argument("--priority", type=int, help="Max priority level (0-7)")
    logs_parser.add_argument("--since", help="Time filter (e.g. '1h ago', '2024-01-01')")
    logs_parser.add_argument("--lines", type=int, default=100, help="Number of lines")
    logs_parser.add_argument("path", nargs="?", help="Export path (for export)")

    # ==================== v16.0 Horizon subparsers ====================

    # Service management
    service_parser = subparsers.add_parser("service", help="Systemd service management")
    service_parser.add_argument(
        "action",
        choices=[
            "list",
            "start",
            "stop",
            "restart",
            "enable",
            "disable",
            "mask",
            "unmask",
            "logs",
            "status",
        ],
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

    # Package management
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

    # Firewall management
    firewall_parser = subparsers.add_parser("firewall", help="Firewall management")
    firewall_parser.add_argument(
        "action",
        choices=["status", "ports", "open-port", "close-port", "services", "zones"],
        help="Firewall action",
    )
    firewall_parser.add_argument("spec", nargs="?", help="Port spec (e.g. 8080/tcp)")

    # v17.0 Atlas - Bluetooth management
    bt_parser = subparsers.add_parser("bluetooth", help="Bluetooth management")
    bt_parser.add_argument(
        "action",
        choices=[
            "status",
            "devices",
            "scan",
            "power-on",
            "power-off",
            "connect",
            "disconnect",
            "pair",
            "unpair",
            "trust",
        ],
        help="Bluetooth action",
    )
    bt_parser.add_argument("address", nargs="?", help="Device MAC address")
    bt_parser.add_argument("--paired", action="store_true", help="Show paired only")
    bt_parser.add_argument("--timeout", type=int, default=10, help="Scan timeout")

    # v17.0 Atlas - Storage management
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

    # Agent management
    agent_parser = subparsers.add_parser("agent", help="Autonomous system agent management")
    agent_parser.add_argument(
        "action",
        choices=[
            "list",
            "status",
            "enable",
            "disable",
            "run",
            "create",
            "remove",
            "logs",
            "templates",
            "notify",
        ],
        help="Agent action",
    )
    agent_parser.add_argument(
        "agent_id",
        nargs="?",
        help="Agent ID (for enable/disable/run/remove/logs/notify)",
    )
    agent_parser.add_argument("--goal", help="Natural language goal (for create)")
    agent_parser.add_argument("--webhook", help="Webhook URL for notifications (for notify)")
    agent_parser.add_argument(
        "--min-severity",
        help="Minimum severity to notify: info/low/medium/high/critical",
    )

    # v35.0 Fortress - Audit log viewer
    audit_parser = subparsers.add_parser("audit-log", help="View recent audit log entries")
    audit_parser.add_argument("--count", type=int, default=20, help="Number of entries to show (default: 20)")

    # v37.0 Pinnacle - Smart Updates
    updates_parser = subparsers.add_parser("updates", help="Smart update management")
    updates_parser.add_argument(
        "action",
        choices=["check", "conflicts", "schedule", "rollback", "history"],
        help="Update action to perform",
    )
    updates_parser.add_argument("--time", default="02:00", help="Schedule time (HH:MM, default: 02:00)")

    # v37.0 Pinnacle - Extensions
    ext_parser = subparsers.add_parser("extension", help="Desktop extension management")
    ext_parser.add_argument(
        "action",
        choices=["list", "install", "remove", "enable", "disable"],
        help="Extension action",
    )
    ext_parser.add_argument("--uuid", help="Extension UUID for install/remove/enable/disable")

    # v37.0 Pinnacle - Flatpak Manager
    flatpak_parser = subparsers.add_parser("flatpak-manage", help="Flatpak management tools")
    flatpak_parser.add_argument(
        "action",
        choices=["sizes", "permissions", "orphans", "cleanup"],
        help="Flatpak action",
    )

    # v37.0 Pinnacle - Boot Configuration
    boot_parser = subparsers.add_parser("boot", help="Boot configuration management")
    boot_parser.add_argument("action", choices=["config", "kernels", "timeout", "apply"], help="Boot action")
    boot_parser.add_argument("--seconds", type=int, help="Timeout in seconds (for timeout action)")

    # v37.0 Pinnacle - Display
    display_parser = subparsers.add_parser("display", help="Display and Wayland configuration")
    display_parser.add_argument(
        "action",
        choices=["list", "session", "fractional-on", "fractional-off"],
        help="Display action",
    )

    # v37.0 Pinnacle - Backup
    backup_parser = subparsers.add_parser("backup", help="Snapshot backup management")
    backup_parser.add_argument(
        "action",
        choices=["detect", "create", "list", "restore", "delete", "status"],
        help="Backup action",
    )
    backup_parser.add_argument("--tool", help="Backup tool (timeshift/snapper)")
    backup_parser.add_argument("--description", help="Snapshot description (for create)")
    backup_parser.add_argument("--snapshot-id", help="Snapshot ID (for restore/delete)")

    return parser
