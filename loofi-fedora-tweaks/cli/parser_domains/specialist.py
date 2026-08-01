"""CLI registration for specialist and advanced user commands."""

from __future__ import annotations

import argparse

Subparsers = argparse._SubParsersAction


def _register_virtualization_and_sharing(subparsers: Subparsers) -> None:
    """Register virtualization and device-sharing inspection commands."""
    vm_parser = subparsers.add_parser("vm", help="Virtual machine management")
    vm_parser.add_argument("action", choices=["list", "status", "start", "stop"], help="VM action")
    vm_parser.add_argument("name", nargs="?", help="VM name (for status/start/stop)")

    vfio_parser = subparsers.add_parser("vfio", help="GPU passthrough assistant")
    vfio_parser.add_argument("action", choices=["check", "gpus", "plan"], help="VFIO action")

    mesh_parser = subparsers.add_parser("mesh", help="Loofi Link mesh networking")
    mesh_parser.add_argument("action", choices=["discover", "status"], help="Mesh action")

    teleport_parser = subparsers.add_parser("teleport", help="State Teleport workspace capture/restore")
    teleport_parser.add_argument("action", choices=["capture", "list", "restore"], help="Teleport action")
    teleport_parser.add_argument("--path", help="Workspace path for capture")
    teleport_parser.add_argument("--target", default="unknown", help="Target device name")
    teleport_parser.add_argument("package_id", nargs="?", help="Package ID for restore")


def _register_user_tools(subparsers: Subparsers) -> None:
    """Register retained specialist profile and focus-mode commands."""
    ai_models_parser = subparsers.add_parser("ai-models", help="AI model management")
    ai_models_parser.add_argument("action", choices=["list", "recommend"], help="AI models action")

    preset_parser = subparsers.add_parser("preset", help="Manage system presets")
    preset_parser.add_argument("action", choices=["list", "apply", "export"], help="Preset action")
    preset_parser.add_argument("name", nargs="?", help="Preset name (for apply/export)")
    preset_parser.add_argument("path", nargs="?", help="Export path (for export)")

    focus_parser = subparsers.add_parser("focus-mode", help="Focus mode distraction blocking")
    focus_parser.add_argument("action", choices=["on", "off", "status"], help="Focus mode action")
    focus_parser.add_argument("--profile", default="default", help="Profile to use (default: default)")

    subparsers.add_parser("security-audit", help="Run security audit and show score")

    profile_parser = subparsers.add_parser("profile", help="System profile management")
    profile_parser.add_argument(
        "action",
        choices=["list", "apply", "create", "delete", "export", "import", "export-all", "import-all"],
        help="Profile action",
    )
    profile_parser.add_argument("name", nargs="?", help="Profile name (for apply/create/delete/export)")
    profile_parser.add_argument("path", nargs="?", help="Import/export file path")
    profile_parser.add_argument("--overwrite", action="store_true", help="Overwrite existing custom profiles on import")
    profile_parser.add_argument("--no-snapshot", action="store_true", help="Skip snapshot creation when applying profiles")
    profile_parser.add_argument("--include-builtins", action="store_true", help="Include built-in profiles in export-all bundle")


def _register_history_tools(subparsers: Subparsers) -> None:
    """Register specialist history, tuning, snapshot, and log commands."""
    health_history_parser = subparsers.add_parser("health-history", help="Health timeline metrics")
    health_history_parser.add_argument(
        "action",
        choices=["show", "record", "export", "prune"],
        help="Health history action",
    )
    health_history_parser.add_argument("path", nargs="?", help="Export path (for export)")

    tuner_parser = subparsers.add_parser("tuner", help="Performance auto-tuner")
    tuner_parser.add_argument("action", choices=["analyze", "apply", "history"], help="Tuner action")

    snapshot_parser = subparsers.add_parser("snapshot", help="System snapshot management")
    snapshot_parser.add_argument(
        "action",
        choices=["list", "create", "delete", "backends"],
        help="Snapshot action",
    )
    snapshot_parser.add_argument("--label", help="Snapshot label (for create)")
    snapshot_parser.add_argument("--backend", choices=["timeshift", "snapper"], help="Verified backend for create")
    snapshot_parser.add_argument("snapshot_id", nargs="?", help="Snapshot ID (for delete)")

    logs_parser = subparsers.add_parser("logs", help="Smart log viewer with pattern detection")
    logs_parser.add_argument("action", choices=["show", "errors", "export"], help="Logs action")
    logs_parser.add_argument("--unit", help="Filter by systemd unit")
    logs_parser.add_argument("--priority", type=int, help="Max priority level (0-7)")
    logs_parser.add_argument("--since", help="Time filter (e.g. '1h ago', '2024-01-01')")
    logs_parser.add_argument("--lines", type=int, default=100, help="Number of lines")
    logs_parser.add_argument("path", nargs="?", help="Export path (for export)")


def register_specialist_commands(subparsers: Subparsers) -> None:
    """Register specialist commands that precede host management."""
    _register_virtualization_and_sharing(subparsers)
    _register_user_tools(subparsers)
    _register_history_tools(subparsers)


def register_agent_command(subparsers: Subparsers) -> None:
    """Register the retained agent compatibility command in public order."""
    agent_parser = subparsers.add_parser("agent", help="Autonomous system agent management")
    agent_parser.add_argument(
        "action",
        choices=["list", "status", "enable", "disable", "run", "create", "remove", "logs", "templates", "notify"],
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
