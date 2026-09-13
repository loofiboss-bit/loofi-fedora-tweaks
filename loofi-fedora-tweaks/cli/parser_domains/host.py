"""CLI registration for host commands in Fedora Maintenance Core."""

from __future__ import annotations

import argparse

Subparsers = argparse._SubParsersAction


def register_host_commands(subparsers: Subparsers) -> None:
    """Register smart update management."""
    updates_parser = subparsers.add_parser("updates", help="Smart update management")
    updates_parser.add_argument(
        "action",
        choices=["check", "conflicts", "schedule", "rollback", "history"],
        help="Update action to perform",
    )
    updates_parser.add_argument("--time", default="02:00", help="Schedule time (HH:MM, default: 02:00)")


def register_basic_host_commands(subparsers: Subparsers) -> None:
    """Compatibility stub."""
    pass


def register_system_management_commands(subparsers: Subparsers) -> None:
    """Compatibility stub."""
    pass


def register_post_agent_commands(subparsers: Subparsers) -> None:
    """Compatibility stub."""
    pass
