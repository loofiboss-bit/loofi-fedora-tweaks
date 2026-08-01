"""CLI registration for diagnostics, support, and Action Center commands."""

from __future__ import annotations

import argparse

from core.fedora_release_policy import FEDORA_RELEASE_POLICY

Subparsers = argparse._SubParsersAction


def _add_target_argument(parser: argparse.ArgumentParser) -> None:
    """Add the stable Fedora readiness target option."""
    parser.add_argument(
        "--target", choices=FEDORA_RELEASE_POLICY.action_targets, default=FEDORA_RELEASE_POLICY.stable_target, help="Readiness target profile"
    )


def _register_diagnostics_and_compatibility(subparsers: Subparsers) -> None:
    """Register diagnostics and retired compatibility surfaces."""
    subparsers.add_parser("doctor", help="Check system dependencies and diagnostics")
    subparsers.add_parser("hardware", help="Show detected hardware profile")

    plugin_parser = subparsers.add_parser("plugins", help="Inspect retired legacy extensions")
    plugin_parser.add_argument("action", choices=["list", "enable", "disable"], help="Plugin action")
    plugin_parser.add_argument("name", nargs="?", help="Plugin name for enable/disable")

    api_key_parser = subparsers.add_parser("api-key", help="Manage the loopback Web API credential")
    api_key_parser.add_argument(
        "action",
        choices=["status", "rotate", "revoke"],
        help="Credential lifecycle action",
    )

    marketplace_parser = subparsers.add_parser("plugin-marketplace", help=argparse.SUPPRESS)
    marketplace_parser.add_argument(
        "action",
        choices=["search", "install", "uninstall", "update", "info", "list-installed", "reviews", "review-submit", "rating"],
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

    subparsers.add_parser("support-bundle", help="Export support bundle ZIP")


def _register_state_command(subparsers: Subparsers) -> None:
    """Register state inspection, backup, and restore planning."""
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


def _register_readiness_subcommands(readiness_parser: argparse.ArgumentParser) -> None:
    """Register the nested Fedora readiness command grammar."""
    readiness_subparsers = readiness_parser.add_subparsers(dest="readiness_action", help="Readiness action commands")

    readiness_actions_parser = readiness_subparsers.add_parser("actions", help="List safe readiness action candidates")
    _add_target_argument(readiness_actions_parser)
    readiness_plan_parser = readiness_subparsers.add_parser("plan", help="Show guided release upgrade plan")
    _add_target_argument(readiness_plan_parser)

    readiness_explain_parser = readiness_subparsers.add_parser("explain", help="Explain one readiness check")
    readiness_explain_parser.add_argument("action_id", help="Readiness check ID")
    _add_target_argument(readiness_explain_parser)

    readiness_export_parser = readiness_subparsers.add_parser("export", help="Export readiness support bundle")
    _add_target_argument(readiness_export_parser)
    readiness_export_parser.add_argument("--path", help="Output JSON path")

    readiness_info_parser = readiness_subparsers.add_parser("action-info", help="Show one readiness action candidate")
    readiness_info_parser.add_argument("action_id", help="Readiness action ID")
    _add_target_argument(readiness_info_parser)

    readiness_preview_parser = readiness_subparsers.add_parser("action-preview", help="Preview one readiness action")
    readiness_preview_parser.add_argument("action_id", help="Readiness action ID")
    _add_target_argument(readiness_preview_parser)

    readiness_run_parser = readiness_subparsers.add_parser("action-run", help="Create an Action Center review plan")
    readiness_run_parser.add_argument("action_id", help="Readiness action ID")
    _add_target_argument(readiness_run_parser)
    readiness_run_parser.add_argument(
        "--confirm",
        action="store_true",
        help="Deprecated compatibility flag; the new plan is never auto-applied",
    )

    readiness_verify_parser = readiness_subparsers.add_parser("action-verify", help="Verify one readiness action")
    readiness_verify_parser.add_argument("action_id", help="Readiness action ID")
    _add_target_argument(readiness_verify_parser)


def _register_action_center_command(subparsers: Subparsers) -> None:
    """Register closed Action Center planning and lifecycle commands."""
    action_center_parser = subparsers.add_parser("action-center", help="Plan, verify, and inspect guided maintenance actions")
    action_center_parser.add_argument(
        "action",
        choices=["list", "preview", "history", "recommendations", "plan", "show", "apply", "verify"],
        nargs="?",
        default="list",
        help="Action Center command",
    )
    action_center_parser.add_argument("action_id", nargs="?", help="Action ID, plan ID, or run ID for the selected command")
    _add_target_argument(action_center_parser)
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


def register_support_commands(subparsers: Subparsers) -> None:
    """Register diagnostics, support, readiness, and Action Center commands."""
    _register_diagnostics_and_compatibility(subparsers)
    _register_state_command(subparsers)

    readiness_parser = subparsers.add_parser("readiness", help="Run release readiness diagnostics")
    _add_target_argument(readiness_parser)
    readiness_parser.add_argument("--advanced", action="store_true", help="Show raw command and status details")
    _register_readiness_subcommands(readiness_parser)
    _register_action_center_command(subparsers)

    fedora44_parser = subparsers.add_parser("fedora44-readiness", help="Compatibility alias for 'readiness --target 44'")
    fedora44_parser.add_argument("--advanced", action="store_true", help="Show raw command and status details")
