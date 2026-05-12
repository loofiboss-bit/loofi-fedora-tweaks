"""Navigation route manifest for Beacon UX surfaces."""

from core.navigation.areas import (
    DEFAULT_PLUGIN_IDS,
    HIDDEN_BY_DEFAULT_PLUGIN_IDS,
    INTERMEDIATE_PLUGIN_IDS,
    NavigationArea,
    all_areas,
    area_for_plugin,
    default_areas,
    get_area,
    is_plugin_visible_for_level,
    plugin_ids_for_level,
    sidebar_areas_for_level,
    validate_areas,
)
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
    "DEFAULT_PLUGIN_IDS",
    "HIDDEN_BY_DEFAULT_PLUGIN_IDS",
    "INTERMEDIATE_PLUGIN_IDS",
    "NavigationArea",
    "NavigationRoute",
    "all_areas",
    "all_routes",
    "area_for_plugin",
    "default_areas",
    "get_area",
    "get_route",
    "is_plugin_visible_for_level",
    "plugin_ids_for_level",
    "resolve",
    "routes_for_palette",
    "routes_for_quick_actions",
    "sidebar_areas_for_level",
    "validate_areas",
    "validate_routes",
]
