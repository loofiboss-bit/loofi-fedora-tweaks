"""CLI grammar for the bounded direct-action workflow."""

from __future__ import annotations

import argparse

from core.fedora_release_policy import FEDORA_RELEASE_POLICY

Subparsers = argparse._SubParsersAction


def register_execution_commands(subparsers: Subparsers) -> None:
    """Register named Action Center-backed execution only."""
    parser = subparsers.add_parser(
        "run",
        help="Run one registered eligible action through Action Center",
    )
    parser.add_argument("action_id", help="Registered Action Center action ID")
    parser.add_argument(
        "--param",
        action="append",
        default=[],
        metavar="KEY=VALUE",
        help="Typed action parameter; repeat for multiple parameters",
    )
    parser.add_argument(
        "--yes",
        action="store_true",
        help="Accept low-risk execution or the single medium-risk confirmation",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=argparse.SUPPRESS,
        help="Create and show the exact plan without executing it",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        default=argparse.SUPPRESS,
        help="Output the versioned direct-action envelope as JSON",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=argparse.SUPPRESS,
        help="Execution timeout in seconds",
    )
    parser.add_argument(
        "--target",
        choices=FEDORA_RELEASE_POLICY.action_targets,
        default=FEDORA_RELEASE_POLICY.stable_target,
        help="Fedora action target profile",
    )
