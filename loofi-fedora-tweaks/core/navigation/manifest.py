"""Compatibility navigation-route view generated from the v18 catalog."""

from __future__ import annotations

import re
from typing import Callable, Iterable

from core.catalog_models import NavigationRoute
from core.product_catalog import catalog_routes

_ROUTES = catalog_routes()
_ROUTE_BY_ID: dict[str, NavigationRoute] = {route.id: route for route in _ROUTES}


def _normalize_key(value: str) -> str:
    return re.sub(r"[\s_-]+", " ", str(value).strip().casefold())


def _alias_pairs() -> Iterable[tuple[str, NavigationRoute]]:
    for route in _ROUTES:
        yield route.id, route
        yield _normalize_key(route.id), route
        yield route.label, route
        yield _normalize_key(route.label), route
        for alias in route.aliases:
            yield alias, route
            yield _normalize_key(alias), route


_ROUTE_BY_ALIAS: dict[str, NavigationRoute] = {}
for alias, route in _alias_pairs():
    key = str(alias)
    _ROUTE_BY_ALIAS.setdefault(key, route)
    _ROUTE_BY_ALIAS.setdefault(_normalize_key(key), route)


def all_routes() -> tuple[NavigationRoute, ...]:
    """Return every canonical route."""
    return _ROUTES


def get_route(route_id: str) -> NavigationRoute | None:
    """Return an exact canonical route by ID."""
    return _ROUTE_BY_ID.get(route_id)


def resolve(route_id_or_alias: str) -> NavigationRoute | None:
    """Resolve a canonical route ID or legacy alias to a route."""
    if not route_id_or_alias:
        return None
    key = str(route_id_or_alias).strip()
    return _ROUTE_BY_ID.get(key) or _ROUTE_BY_ALIAS.get(key) or _ROUTE_BY_ALIAS.get(_normalize_key(key))


def routes_for_palette() -> tuple[NavigationRoute, ...]:
    """Return routes searchable from the command palette."""
    return _ROUTES


def routes_for_quick_actions() -> tuple[NavigationRoute, ...]:
    """Return routes available to quick-action navigation."""
    return _ROUTES


def validate_routes(
    plugin_ids: Iterable[str],
    icon_resolver: Callable[[str], str | None] | None = None,
) -> list[str]:
    """Return validation errors for the catalog-generated route view."""
    errors: list[str] = []
    ids = [route.id for route in _ROUTES]
    for route_id in sorted({item for item in ids if ids.count(item) > 1}):
        errors.append(f"duplicate route id: {route_id}")

    plugin_id_set = set(plugin_ids)
    for route in _ROUTES:
        if route.plugin_id not in plugin_id_set:
            errors.append(f"route {route.id} references unknown plugin {route.plugin_id}")
        if ":" in route.id and not route.subroute:
            errors.append(f"route {route.id} is missing subroute")
        if route.risk not in ("none", "low", "medium", "high"):
            errors.append(f"route {route.id} has invalid risk {route.risk}")
        if route.visibility not in ("beginner", "advanced", "all"):
            errors.append(f"route {route.id} has invalid visibility {route.visibility}")
        if icon_resolver is not None and not icon_resolver(route.icon):
            errors.append(f"route {route.id} icon does not resolve: {route.icon}")
    return errors


__all__ = [
    "NavigationRoute",
    "all_routes",
    "get_route",
    "resolve",
    "routes_for_palette",
    "routes_for_quick_actions",
    "validate_routes",
]
