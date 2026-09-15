"""Public CLI parser construction."""

from __future__ import annotations

import argparse

from cli.parser_domains import (
    register_activity_command,
    register_execution_commands,
    register_health_commands,
    register_host_commands,
    register_support_commands,
    register_troubleshooting_command,
)
from version import __version__, __version_codename__


def build_parser() -> argparse.ArgumentParser:
    """Build the public CLI parser for Fedora Maintenance Core."""
    parser = argparse.ArgumentParser(
        prog="loofi",
        description=f'Loofi Fedora Tweaks v{__version__} "{__version_codename__}" - Curated Fedora Utility CLI',
    )
    parser.add_argument(
        "-v",
        "--version",
        action="version",
        version=f'{__version__} "{__version_codename__}"',
    )
    parser.add_argument("--json", action="store_true", help="Output in JSON format (for scripting)")
    parser.add_argument(
        "--timeout",
        type=int,
        default=300,
        help="Operation timeout in seconds (default: 300)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show commands without executing them",
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")
    register_health_commands(subparsers)          # info, check
    register_host_commands(subparsers)            # updates
    register_troubleshooting_command(subparsers)  # troubleshoot
    register_execution_commands(subparsers)       # changes
    register_activity_command(subparsers)         # activity
    register_support_commands(subparsers)         # doctor, support-bundle
    return parser
