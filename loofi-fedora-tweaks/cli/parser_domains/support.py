"""CLI registration for diagnostics and support in Fedora Maintenance Core."""

from __future__ import annotations

import argparse

Subparsers = argparse._SubParsersAction


def register_support_commands(subparsers: Subparsers) -> None:
    """Register diagnostics and support bundle commands."""
    subparsers.add_parser("doctor", help="Check system dependencies, Fedora version, and Polkit status")
    subparsers.add_parser("support-bundle", help="Export support bundle ZIP")
