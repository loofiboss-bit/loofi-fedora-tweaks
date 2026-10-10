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

    installed_p = apps_sub.add_parser("installed", help="List installed Flatpak applications and curated RPMs")
    installed_p.add_argument("--json", action="store_true", default=argparse.SUPPRESS, help="Output in JSON format")
    compare_p = apps_sub.add_parser("compare", help="Compare exact installations from captured inventory")
    compare_p.add_argument("app_id", help="Exact Flatpak application ID")
    compare_p.add_argument("--json", action="store_true", default=argparse.SUPPRESS, help="Output in JSON format")
    permissions_p = apps_sub.add_parser("permissions", help="Inspect permissions declared by one installed Flatpak")
    permissions_p.add_argument("ref", help="Full app/id/architecture/branch ref")
    permissions_p.add_argument("--installation", required=True, help="Explicit user, system, or named installation")
    permissions_p.add_argument("--json", action="store_true", default=argparse.SUPPRESS, help="Output in JSON format")
    remove_p = apps_sub.add_parser("remove", help="Review removal of one exact installed Flatpak ref")
    remove_p.add_argument("ref", help="Full app/id/architecture/branch ref")
    remove_p.add_argument("--installation", required=True, help="Explicit user, system, or named installation")
    remove_p.add_argument("--yes", action="store_true", help="Confirm removal while preserving application data")
    remove_p.add_argument("--json", action="store_true", default=argparse.SUPPRESS, help="Output in JSON format")

    access_p = apps_sub.add_parser("access", help="Inspect declarations and scoped Flatpak override layers")
    access_p.add_argument("ref", help="Full app/id/architecture/branch ref")
    access_p.add_argument("--installation", required=True, help="Explicit user, system, or named installation")
    access_p.add_argument("--json", action="store_true", default=argparse.SUPPRESS, help="Output in JSON format")

    details_p = apps_sub.add_parser("details", help="Inspect local app and runtime metadata")
    details_p.add_argument("ref", help="Full app/id/architecture/branch ref")
    details_p.add_argument("--installation", required=True, help="Explicit user, system, or named installation")
    details_p.add_argument("--json", action="store_true", default=argparse.SUPPRESS, help="Output in JSON format")
    unused_p = apps_sub.add_parser("unused", help="Inspect unused runtimes without changing the installation")
    unused_p.add_argument("--installation", required=True, help="Explicit user, system, or named installation")
    unused_p.add_argument("--json", action="store_true", default=argparse.SUPPRESS, help="Output in JSON format")
    cleanup_p = apps_sub.add_parser("cleanup", help="Review exact unused runtimes before cleanup")
    cleanup_p.add_argument("--installation", required=True, help="Explicit user, system, or named installation")
    cleanup_p.add_argument("--ref", dest="refs", required=True, action="append", help="Exact runtime ref; repeat to select more")
    cleanup_p.add_argument("--yes", action="store_true", help="Confirm exact runtime removal and accept manual reinstallation without rollback")
    cleanup_p.add_argument("--json", action="store_true", default=argparse.SUPPRESS, help="Output in JSON format")
