"""CLI registration for host commands in Fedora Maintenance Core."""

from __future__ import annotations

import argparse

Subparsers = argparse._SubParsersAction


def register_host_commands(subparsers: Subparsers) -> None:
    """Register read-only update inspection commands."""
    updates_parser = subparsers.add_parser("updates", help="Inspect Fedora update sources")
    updates_parser.add_argument(
        "action",
        choices=["check", "conflicts", "history"],
        help="Read-only update query to perform",
    )


def register_basic_host_commands(subparsers: Subparsers) -> None:
    """Compatibility stub."""
    pass


def register_system_management_commands(subparsers: Subparsers) -> None:
    """Compatibility stub."""
    pass


def register_post_agent_commands(subparsers: Subparsers) -> None:
    """Compatibility stub."""
    pass
