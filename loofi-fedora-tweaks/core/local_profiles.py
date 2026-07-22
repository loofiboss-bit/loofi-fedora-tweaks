"""Closed, data-only schema for imported local profiles."""

from __future__ import annotations

from typing import Any, Mapping

PROFILE_SCHEMA_VERSION = 1
PROFILE_KEYS = frozenset(
    {
        "schema_version",
        "name",
        "theme",
        "icon_theme",
        "cursor_theme",
        "color_scheme",
        "battery_limit",
        "power_profile",
    }
)


def validate_local_profile(payload: Any) -> dict[str, Any]:
    """Return a normalized local profile or reject unknown and unsafe data."""
    if not isinstance(payload, Mapping):
        raise ValueError("Profile root must be an object.")
    unknown = sorted(set(payload) - PROFILE_KEYS)
    if unknown:
        raise ValueError(f"Unknown profile fields: {', '.join(unknown)}")
    version = payload.get("schema_version", PROFILE_SCHEMA_VERSION)
    if version != PROFILE_SCHEMA_VERSION:
        raise ValueError(f"Unsupported profile schema: {version}")
    name = payload.get("name")
    if not isinstance(name, str) or not name.strip():
        raise ValueError("Profile name must be a non-empty string.")
    for key in ("theme", "icon_theme", "cursor_theme", "color_scheme", "power_profile"):
        value = payload.get(key)
        if value is not None and not isinstance(value, str):
            raise ValueError(f"Profile field '{key}' must be a string or null.")
    battery_limit = payload.get("battery_limit")
    if battery_limit is not None and (
        not isinstance(battery_limit, int)
        or isinstance(battery_limit, bool)
        or not 0 <= battery_limit <= 100
    ):
        raise ValueError("Profile battery_limit must be an integer from 0 to 100.")
    return {"schema_version": PROFILE_SCHEMA_VERSION, **dict(payload)}
