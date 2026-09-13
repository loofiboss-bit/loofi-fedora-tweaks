"""Decommissioned daemon client stub for Fedora Maintenance Core.

Always returns None to ensure all system operations run locally and natively.
"""

from __future__ import annotations

from typing import Any


def call_json(method_name: str, *args: Any, **kwargs: Any) -> Any:
    """Always return None so services fall back to direct local execution."""
    return None


def is_available() -> bool:
    """Daemon is permanently disabled in Fedora Maintenance Core."""
    return False
