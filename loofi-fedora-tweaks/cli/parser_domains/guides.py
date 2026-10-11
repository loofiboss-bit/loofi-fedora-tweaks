"""CLI grammar for read-only curated Fedora guide discovery."""

from __future__ import annotations

import argparse


def register_guides_command(subparsers: argparse._SubParsersAction) -> None:
    """Register read-only guide catalog commands."""
    guides = subparsers.add_parser("guides", help="Browse or inspect everyday Fedora guides")
    guide_actions = guides.add_subparsers(dest="guides_action", required=True)
    list_parser = guide_actions.add_parser("list", help="List available guides and saved progress")
    list_parser.add_argument("--json", action="store_true", default=argparse.SUPPRESS, help="Output in JSON format")
    show_parser = guide_actions.add_parser("show", help="Show one guide and its saved progress")
    show_parser.add_argument("guide_id")
    show_parser.add_argument("--json", action="store_true", default=argparse.SUPPRESS, help="Output in JSON format")
