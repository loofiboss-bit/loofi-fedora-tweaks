"""CLI parser domain for Fedora desktop and system tweaks."""

from __future__ import annotations

import argparse

Subparsers = argparse._SubParsersAction


def register_tweaks_command(subparsers: Subparsers) -> None:
    """Register the public tweaks command for querying and applying Fedora tweaks."""
    tweaks_parser = subparsers.add_parser(
        "tweaks",
        help="Inspect, change, and restore Fedora desktop and system tweaks",
    )
    tweaks_sub = tweaks_parser.add_subparsers(dest="tweaks_action", help="Tweak actions")

    # tweaks list
    list_p = tweaks_sub.add_parser("list", help="List all available tweaks and current settings")
    list_p.add_argument(
        "--desktop",
        choices=["gnome", "kde", "all"],
        default="all",
        help="Filter tweaks by desktop environment",
    )
    list_p.add_argument("--json", action="store_true", default=argparse.SUPPRESS, help="Output in JSON format")

    # tweaks get <tweak_id>
    get_p = tweaks_sub.add_parser("get", help="Get current value and choices for a setting")
    get_p.add_argument("tweak_id", help="Setting identifier (e.g. gnome-color, dnf-parallel-downloads)")
    get_p.add_argument("--json", action="store_true", default=argparse.SUPPRESS, help="Output in JSON format")

    # tweaks set <tweak_id> <value>
    set_p = tweaks_sub.add_parser("set", help="Apply a setting value")
    set_p.add_argument("tweak_id", help="Setting identifier")
    set_p.add_argument("value", help="Setting value to apply")
    set_p.add_argument("--yes", action="store_true", help="Confirm execution without interactive prompt")
    set_p.add_argument("--json", action="store_true", default=argparse.SUPPRESS, help="Output in JSON format")

    # tweaks restore <tweak_id>
    restore_p = tweaks_sub.add_parser("restore", help="Restore previous verified setting value")
    restore_p.add_argument("tweak_id", help="Setting identifier")
    restore_p.add_argument("--yes", action="store_true", help="Confirm execution without interactive prompt")
    restore_p.add_argument("--json", action="store_true", default=argparse.SUPPRESS, help="Output in JSON format")
