"""Public CLI parser construction."""

from __future__ import annotations

import argparse

from cli.parser_domains import (
    register_agent_command,
    register_basic_host_commands,
    register_execution_commands,
    register_observability_commands,
    register_post_agent_commands,
    register_specialist_commands,
    register_support_commands,
    register_system_management_commands,
)
from version import __version__, __version_codename__


def build_parser() -> argparse.ArgumentParser:
    """Build the public CLI parser without executing a handler."""
    parser = argparse.ArgumentParser(
        prog="loofi",
        description=f'Loofi Fedora Tweaks v{__version__} "{__version_codename__}" - System management CLI',
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
    register_observability_commands(subparsers)
    register_basic_host_commands(subparsers)
    register_support_commands(subparsers)
    register_specialist_commands(subparsers)
    register_system_management_commands(subparsers)
    register_agent_command(subparsers)
    register_post_agent_commands(subparsers)
    register_execution_commands(subparsers)
    return parser
