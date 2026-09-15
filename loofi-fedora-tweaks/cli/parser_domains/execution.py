"""CLI grammar for the bounded direct-action workflow."""

from __future__ import annotations

import argparse

from core.fedora_release_policy import FEDORA_RELEASE_POLICY

Subparsers = argparse._SubParsersAction


def register_execution_commands(subparsers: Subparsers) -> None:
    """Register the v29 Activity alias and retained explicit execution verbs."""
    changes_parser = subparsers.add_parser(
        "changes",
        help="Compatibility alias for Activity with retained apply and verify verbs",
    )
    changes_sub = changes_parser.add_subparsers(dest="changes_action", help="Activity compatibility actions")

    # changes list
    list_p = changes_sub.add_parser("list", help="List recent Activity & Recovery entries")
    list_p.add_argument("--limit", type=int, default=25, help="Number of records to show")
    list_p.add_argument("--json", action="store_true", default=argparse.SUPPRESS, help="Output in JSON format")

    # changes show <id>
    show_p = changes_sub.add_parser("show", help="Show one Activity & Recovery entry")
    show_p.add_argument("id", help="Plan ID or Run ID")
    show_p.add_argument("--json", action="store_true", default=argparse.SUPPRESS, help="Output in JSON format")

    # changes apply <target>
    apply_p = changes_sub.add_parser("apply", help="Apply a previously reviewed compatibility plan")
    apply_p.add_argument("target", help="Action ID or Plan ID")
    apply_p.add_argument("--param", action="append", default=[], metavar="KEY=VALUE", help="Typed action parameter")
    apply_p.add_argument("--yes", action="store_true", help="Accept execution confirmation")
    apply_p.add_argument("--dry-run", action="store_true", default=argparse.SUPPRESS, help="Create plan without executing")
    apply_p.add_argument("--json", action="store_true", default=argparse.SUPPRESS, help="Output in JSON format")
    apply_p.add_argument("--timeout", type=int, default=argparse.SUPPRESS, help="Execution timeout in seconds")
    apply_p.add_argument(
        "--target",
        dest="release_target",
        choices=FEDORA_RELEASE_POLICY.action_targets,
        default=FEDORA_RELEASE_POLICY.stable_target,
        help="Fedora action target profile",
    )

    # changes verify <run_id>
    verify_p = changes_sub.add_parser("verify", help="Verify a previously executed compatibility run")
    verify_p.add_argument("run_id", help="Run ID to verify")
    verify_p.add_argument("--json", action="store_true", default=argparse.SUPPRESS, help="Output in JSON format")
