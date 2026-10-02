"""CLI parser domain for curated Fedora application installation."""

from __future__ import annotations

import argparse

Subparsers = argparse._SubParsersAction


def register_apps_command(subparsers: Subparsers) -> None:
    """Register the public apps command for curated application management."""
    apps_parser = subparsers.add_parser(
        "apps",
        help="List and install curated Fedora Flatpak and RPM applications",
    )
    apps_sub = apps_parser.add_subparsers(dest="apps_action", help="Application actions")

    # apps list
    list_p = apps_sub.add_parser("list", help="List curated applications and installation status")
    list_p.add_argument("--category", help="Filter applications by category")
    list_p.add_argument("--json", action="store_true", default=argparse.SUPPRESS, help="Output in JSON format")

    # apps install <app_id>
    install_p = apps_sub.add_parser("install", help="Install a curated application")
    install_p.add_argument("app_id", help="Application identifier (e.g. flatseal, vlc, code)")
    install_p.add_argument("--yes", action="store_true", help="Confirm execution without interactive prompt")
    install_p.add_argument("--json", action="store_true", default=argparse.SUPPRESS, help="Output in JSON format")
