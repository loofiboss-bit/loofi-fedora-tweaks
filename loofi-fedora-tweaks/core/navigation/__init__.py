"""Navigation route manifest for Beacon UX surfaces."""

from core.navigation.manifest import (
    NavigationRoute,
    all_routes,
    get_route,
    resolve,
    routes_for_palette,
    routes_for_quick_actions,
    validate_routes,
)

__all__ = [
    "NavigationRoute",
    "all_routes",
    "get_route",
    "resolve",
    "routes_for_palette",
    "routes_for_quick_actions",
    "validate_routes",
]
