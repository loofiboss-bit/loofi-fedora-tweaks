"""Pure, idempotent adapters for persisted v14 navigation state."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

from .destinations import placement_for_route
from .manifest import resolve
from .models import NavigationMode

_DEFAULT_ROUTE_ID = "atlas_dashboard"
_MODE_ALIASES = {
    "beginner": NavigationMode.STANDARD,
    "standard": NavigationMode.STANDARD,
    "intermediate": NavigationMode.ADVANCED,
    "advanced": NavigationMode.ADVANCED,
}


def navigation_mode_from_value(value: object) -> NavigationMode:
    """Map v14 experience values and v15 mode values to the v15 contract."""
    if isinstance(value, NavigationMode):
        return value
    return _MODE_ALIASES.get(
        str(value or "").strip().lower(),
        NavigationMode.STANDARD,
    )


def legacy_experience_for_mode(mode: NavigationMode) -> str:
    """Return a safe v14-shell adapter value for a v15 navigation mode."""
    if mode is NavigationMode.ADVANCED:
        return "advanced"
    return "beginner"


def canonical_persisted_route(
    value: object,
    *,
    fallback: str | None = None,
    preserve_unknown: bool = False,
) -> str | None:
    """Normalize a route/alias and apply compatibility redirects for storage."""
    text = str(value or "").strip()
    route = resolve(text)
    if route is None:
        if preserve_unknown and text:
            return text
        return fallback

    placement = placement_for_route(route.id)
    if placement and placement.redirect_route_id:
        return placement.redirect_route_id
    return route.id


def migrate_route_references(
    values: object,
    *,
    preserve_unknown: bool = True,
) -> list[str]:
    """Normalize and de-duplicate a persisted route collection."""
    if isinstance(values, (str, bytes)) or not isinstance(values, Iterable):
        return []

    migrated: list[str] = []
    for value in values:
        route_id = canonical_persisted_route(
            value,
            preserve_unknown=preserve_unknown,
        )
        if route_id and route_id not in migrated:
            migrated.append(route_id)
    return migrated


def migrate_last_route(value: object) -> str:
    """Return a safe canonical route for restored navigation state."""
    return canonical_persisted_route(value, fallback=_DEFAULT_ROUTE_ID) or _DEFAULT_ROUTE_ID


def migrate_quick_action(action: Mapping[str, Any]) -> dict[str, Any]:
    """Normalize one quick-action route reference without changing its action."""
    migrated = dict(action)
    route_value = migrated.get("route_id") or migrated.get("target_tab")
    if route_value:
        route_id = canonical_persisted_route(
            route_value,
            preserve_unknown="route_id" in migrated,
        )
        if route_id:
            migrated["route_id"] = route_id
        else:
            migrated.pop("route_id", None)
    migrated.pop("target_tab", None)
    return migrated


def migrate_quick_actions(actions: object) -> list[dict[str, Any]]:
    """Normalize a quick-action list while ignoring malformed entries."""
    if not isinstance(actions, list):
        return []
    return [
        migrate_quick_action(action)
        for action in actions
        if isinstance(action, Mapping)
    ]
