"""CLI grammar for read-only portable setup inspection."""
from __future__ import annotations

import argparse


def register_setup_command(subparsers: argparse._SubParsersAction) -> None:
    """Register setup list, show, and compare commands; there is no apply verb."""
    setup = subparsers.add_parser("setup", help="List, show, or compare saved Fedora configurations")
    actions = setup.add_subparsers(dest="setup_action", required=True)
    for action, help_text in (
        ("list", "List locally saved configurations"),
        ("show", "Show a saved configuration and its progress"),
        ("compare", "Compare a saved configuration with this computer"),
    ):
        command = actions.add_parser(action, help=help_text)
        if action != "list":
            command.add_argument("setup_id", help="Content identity printed by setup list")
        command.add_argument("--json", action="store_true", default=argparse.SUPPRESS, help="Output in JSON format")
