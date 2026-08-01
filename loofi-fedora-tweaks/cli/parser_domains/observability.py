"""CLI registration for system information and observability commands."""

from __future__ import annotations

import argparse

from core.fedora_release_policy import FEDORA_RELEASE_POLICY

Subparsers = argparse._SubParsersAction


def _register_health_commands(subparsers: Subparsers) -> None:
    """Register system information, health, and maintenance commands."""
    subparsers.add_parser("info", help="Show system information")

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


def _register_activity_command(subparsers: Subparsers) -> None:
    """Register Trusted Change Journal inspection and recovery planning."""
    activity_parser = subparsers.add_parser(
        "activity",
        help="Inspect the Trusted Change Journal and create reviewed recovery plans",
    )
    activity_subparsers = activity_parser.add_subparsers(
        dest="activity_action",
        help="Activity commands",
    )
    activity_list = activity_subparsers.add_parser(
        "list",
        help="List recent changes from available local sources",
    )
    activity_list.add_argument("--limit", type=int, default=25)
    activity_list.add_argument(
        "--source",
        choices=["action_center", "dnf5", "rpm_ostree", "flatpak", "fwupd", "loofi_app", "session"],
        action="append",
        default=[],
        help="Restrict results to one or more sources",
    )
    activity_list.add_argument("--refresh", action="store_true")
    for action in ("show", "related", "recover"):
        action_parser = activity_subparsers.add_parser(
            action,
            help=f"{action.capitalize()} one activity event",
        )
        action_parser.add_argument("event_id")
        action_parser.add_argument("--refresh", action="store_true")
    activity_related = activity_subparsers.choices["related"]
    activity_related.add_argument("--limit", type=int, default=20)


def _register_troubleshooting_command(subparsers: Subparsers) -> None:
    """Register bounded troubleshooting session commands."""
    troubleshoot_parser = subparsers.add_parser(
        "troubleshoot",
        help="Run or inspect bounded troubleshooting sessions",
    )
    troubleshoot_subparsers = troubleshoot_parser.add_subparsers(
        dest="troubleshoot_action",
        help="Troubleshooting commands",
    )
    troubleshoot_subparsers.add_parser(
        "profiles",
        help="List the closed troubleshooting profile catalog",
    )
    troubleshoot_run = troubleshoot_subparsers.add_parser(
        "run",
        help="Explicitly run one bounded read-only profile",
    )
    troubleshoot_run.add_argument("profile_id")
    troubleshoot_run.add_argument(
        "--application-id",
        help="Package name or Flatpak application ID for application_failed",
    )
    troubleshoot_show = troubleshoot_subparsers.add_parser(
        "show",
        help="Show one saved troubleshooting session",
    )
    troubleshoot_show.add_argument("session_id")
    troubleshoot_subparsers.add_parser(
        "latest",
        help="Show the latest saved troubleshooting session",
    )
    troubleshoot_compare = troubleshoot_subparsers.add_parser(
        "compare",
        help="Compare one session with an explicit follow-up",
    )
    troubleshoot_compare.add_argument("session_id")
    troubleshoot_compare.add_argument("followup_id")
    troubleshoot_export = troubleshoot_subparsers.add_parser(
        "export",
        help="Export one selected session in Support Bundle v13",
    )
    troubleshoot_export.add_argument("session_id")
    troubleshoot_export.add_argument(
        "--output",
        help="Destination ZIP path (defaults to the user home directory)",
    )


def _register_monitoring_commands(subparsers: Subparsers) -> None:
    """Register bounded read-only system monitoring commands."""
    disk_parser = subparsers.add_parser("disk", help="Disk usage information")
    disk_parser.add_argument("--details", action="store_true", help="Show large directories")

    process_parser = subparsers.add_parser("processes", help="Show top processes")
    process_parser.add_argument("-n", "--count", type=int, default=10, help="Number of processes to show")
    process_parser.add_argument("--sort", choices=["cpu", "memory"], default="cpu", help="Sort by")

    subparsers.add_parser("temperature", help="Show temperature readings")
    netmon_parser = subparsers.add_parser("netmon", help="Network interface monitoring")
    netmon_parser.add_argument("--connections", action="store_true", help="Show active connections")


def register_observability_commands(subparsers: Subparsers) -> None:
    """Register the leading public information and observability grammar."""
    _register_health_commands(subparsers)
    _register_activity_command(subparsers)
    _register_troubleshooting_command(subparsers)
    _register_monitoring_commands(subparsers)
