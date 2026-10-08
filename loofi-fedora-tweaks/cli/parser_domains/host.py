"""CLI registration for host commands in Fedora Maintenance Core."""

from __future__ import annotations

import argparse

Subparsers = argparse._SubParsersAction


def register_host_commands(subparsers: Subparsers) -> None:
    """Register read-only update inspection commands."""
    updates_parser = subparsers.add_parser("updates", help="Inspect Fedora update sources")
    updates_parser.add_argument(
        "action",
        choices=["check", "conflicts", "history", "diagnose", "prepare-upgrade"],
        help="Read-only update query to perform",
    )

    updates_parser.add_argument("--source", choices=["system", "flatpak", "firmware"], default="system", help="Update source to diagnose")
    updates_parser.add_argument("--run-id", help="Exact recorded update run to inspect")

    from core.fedora_release_policy import FEDORA_RELEASE_POLICY

    updates_parser.add_argument("--target", choices=FEDORA_RELEASE_POLICY.action_targets, default=FEDORA_RELEASE_POLICY.stable_target, help="Release policy target for local preparation")
