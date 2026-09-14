"""CLI registration for system information and observability commands."""

from __future__ import annotations

import argparse

from core.fedora_release_policy import FEDORA_RELEASE_POLICY

Subparsers = argparse._SubParsersAction


def _register_health_commands(subparsers: Subparsers) -> None:
    """Register system information and check commands."""
    subparsers.add_parser("info", help="Show system information")

    check_parser = subparsers.add_parser("check", help="Run and persist the explicit read-only System Check")
    check_parser.add_argument("--json", action="store_true", default=argparse.SUPPRESS, help="Output in JSON format")
    check_parser.add_argument(
        "--target",
        choices=FEDORA_RELEASE_POLICY.action_targets,
        default=FEDORA_RELEASE_POLICY.stable_target,
        help="Readiness target profile",
    )


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
        "--cursor",
        help="Continue after the opaque marker returned by the previous page",
    )
    activity_list.add_argument(
        "--source",
        choices=["action_center", "dnf5", "rpm_ostree", "flatpak", "fwupd", "loofi_app", "session"],
        action="append",
        default=[],
        help="Restrict results to one or more sources",
    )
    activity_list.add_argument("--refresh", action="store_true")
    activity_list.add_argument("--since", type=float, help="Include events at or after this Unix timestamp")
    activity_list.add_argument("--until", type=float, help="Include events at or before this Unix timestamp")
    activity_list.add_argument(
        "--status",
        action="append",
        dest="statuses",
        choices=["running", "verifying", "awaiting_reboot", "succeeded", "failed", "verification_failed", "cancelled", "interrupted", "recorded"],
        default=[],
        help="Restrict results to one or more recorded states",
    )
    activity_list.add_argument(
        "--reboot",
        choices=["required", "not-required"],
        help="Filter by recorded reboot requirement",
    )
    activity_list.add_argument("--search", help="Bounded search over action, package, resource, and summary facts")
    for action in ("show", "related", "recover"):
        action_parser = activity_subparsers.add_parser(
            action,
            help=f"{action.capitalize()} one activity event",
        )
        action_parser.add_argument("event_id")
        action_parser.add_argument("--refresh", action="store_true")
    export_parser = activity_subparsers.add_parser(
        "export",
        help="Export one selected event as redacted JSON or Markdown",
    )
    export_parser.add_argument("event_id")
    export_parser.add_argument("--format", choices=["json", "markdown"], default="json")
    export_parser.add_argument("--refresh", action="store_true")
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


register_health_commands = _register_health_commands
register_troubleshooting_command = _register_troubleshooting_command
register_activity_command = _register_activity_command


def register_observability_commands(subparsers: Subparsers) -> None:
    """Register the leading public information and observability grammar."""
    _register_health_commands(subparsers)
    _register_troubleshooting_command(subparsers)
    _register_activity_command(subparsers)
