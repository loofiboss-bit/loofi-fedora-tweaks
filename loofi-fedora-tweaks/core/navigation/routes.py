"""The single, PyQt-free definition of what the application shell shows.

Everyday mode shows four jobs, with Tweaks as the start page.  Advanced mode
adds a small set of tools for people who want them.  Deeper plugin routes still
resolve through the route manifest; this module only decides which of them own
a row in the primary navigation, and which row a given route belongs to.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ShellRoute:
    """One primary navigation row."""

    id: str
    label: str
    icon: str
    default_route_id: str
    description: str = ""
    advanced: bool = False
    route_ids: tuple[str, ...] = ()


START_ROUTE_ID = "utility:tune"

_SHELL_ROUTES: tuple[ShellRoute, ...] = (
    ShellRoute(
        "tune",
        "Tweaks",
        "settings",
        "utility:tune",
        "Search and change Fedora and desktop settings, with undo.",
    ),
    ShellRoute(
        "install",
        "Apps",
        "install",
        "utility:install",
        "Discover applications and trusted software sources.",
    ),
    ShellRoute(
        "update",
        "Updates",
        "update",
        "utility:update",
        "Check system, Flatpak, and firmware updates.",
    ),
    ShellRoute(
        "fix",
        "Health",
        "maintenance-health",
        "utility:fix",
        "Diagnose a symptom and run reviewed maintenance.",
    ),
    ShellRoute(
        "system",
        "System",
        "hardware-performance",
        "system_info",
        "System details, monitoring, and hardware.",
        advanced=True,
        route_ids=("system_info", "dashboard", "monitor", "hardware"),
    ),
    ShellRoute(
        "storage",
        "Storage",
        "storage",
        "storage",
        "Disks, usage, and storage maintenance.",
        advanced=True,
        route_ids=("storage",),
    ),
    ShellRoute(
        "network",
        "Network",
        "network",
        "network",
        "Connections, DNS, and network privacy.",
        advanced=True,
        route_ids=("network",),
    ),
    ShellRoute(
        "security",
        "Security",
        "security-shield",
        "security",
        "Firewall, privacy, and exposed ports.",
        advanced=True,
        route_ids=("security",),
    ),
    ShellRoute(
        "logs",
        "Logs",
        "logs",
        "logs",
        "System and application logs.",
        advanced=True,
        route_ids=("logs", "diagnostics:watchtower"),
    ),
)

# Compatibility inputs from deep links, search, and saved settings.
LEGACY_ALIASES: dict[str, str] = {
    "home": START_ROUTE_ID,
    "tune": "utility:tune",
    "tweaks": "utility:tune",
    "install": "utility:install",
    "apps": "utility:install",
    "update": "utility:update",
    "updates": "utility:update",
    "fix": "utility:fix",
    "health": "utility:fix",
}


def all_shell_routes() -> tuple[ShellRoute, ...]:
    """Return every shell route, advanced ones included."""
    return _SHELL_ROUTES


def visible_shell_routes(advanced: bool = False) -> tuple[ShellRoute, ...]:
    """Return the rows to show in the sidebar for the selected mode."""
    return tuple(route for route in _SHELL_ROUTES if advanced or not route.advanced)


def get_shell_route(shell_route_id: str) -> ShellRoute | None:
    """Return a shell route by stable ID."""
    key = str(shell_route_id)
    return next((route for route in _SHELL_ROUTES if route.id == key), None)


def advanced_shell_route_for(route_id: str) -> ShellRoute | None:
    """Return the advanced row that owns a manifest route, if any."""
    key = str(route_id)
    for route in _SHELL_ROUTES:
        if route.advanced and key in route.route_ids:
            return route
    return None
