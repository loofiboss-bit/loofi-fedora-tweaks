"""Focused navigation areas for the main desktop shell.

This module is deliberately PyQt-free.  It groups stable plugin/route IDs into
the smaller set of user-facing areas rendered by the sidebar while keeping the
route manifest as the canonical navigation contract.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable


@dataclass(frozen=True)
class NavigationArea:
    """A top-level navigation area shown in the focused sidebar."""

    id: str
    label: str
    icon: str
    description: str
    plugin_ids: tuple[str, ...]
    advanced_only: bool = False


_HOME_PLUGINS = ("atlas_dashboard",)
_SOFTWARE_PLUGINS = ("software", "maintenance", "snapshots", "virtualization")
_SYSTEM_PLUGINS = (
    "system_info",
    "monitor",
    "hardware",
    "storage",
    "health",
    "diagnostics",
    "performance",
    "gaming",
)
_NETWORK_SECURITY_PLUGINS = ("network", "security", "backup")
_DESKTOP_SETTINGS_PLUGINS = ("desktop", "settings", "profiles", "extensions", "development")
_MORE_PLUGINS = (
    "community",
    "mesh",
    "logs",
    "ai_lab",
    "agents",
    "automation",
    "teleport",
)


_AREAS: tuple[NavigationArea, ...] = (
    NavigationArea(
        id="home",
        label="Home",
        icon="home",
        description="Overview, guidance, and high-value Fedora tasks.",
        plugin_ids=_HOME_PLUGINS,
    ),
    NavigationArea(
        id="software_updates",
        label="Software & Updates",
        icon="packages-software",
        description="Applications, package sources, updates, snapshots, and virtual machines.",
        plugin_ids=_SOFTWARE_PLUGINS,
    ),
    NavigationArea(
        id="system_hardware",
        label="System & Hardware",
        icon="hardware-performance",
        description="System details, health, monitoring, hardware, storage, and diagnostics.",
        plugin_ids=_SYSTEM_PLUGINS,
    ),
    NavigationArea(
        id="network_security",
        label="Network & Security",
        icon="security-shield",
        description="Connectivity, privacy, hardening, and backup workflows.",
        plugin_ids=_NETWORK_SECURITY_PLUGINS,
    ),
    NavigationArea(
        id="desktop_settings",
        label="Desktop & Settings",
        icon="appearance-theme",
        description="Desktop appearance, preferences, profiles, extensions, and developer setup.",
        plugin_ids=_DESKTOP_SETTINGS_PLUGINS,
    ),
    NavigationArea(
        id="more",
        label="More",
        icon="developer-tools",
        description="Advanced, experimental, automation, community, and log tools.",
        plugin_ids=_MORE_PLUGINS,
        advanced_only=True,
    ),
)

_AREA_BY_ID = {area.id: area for area in _AREAS}
_AREA_BY_PLUGIN = {
    plugin_id: area
    for area in _AREAS
    for plugin_id in area.plugin_ids
}


def all_areas() -> tuple[NavigationArea, ...]:
    """Return every focused navigation area in display order."""
    return _AREAS


def default_areas() -> tuple[NavigationArea, ...]:
    """Return the five default primary areas."""
    return tuple(area for area in _AREAS if not area.advanced_only)


def get_area(area_id: str) -> NavigationArea | None:
    """Return a navigation area by stable ID."""
    return _AREA_BY_ID.get(str(area_id))


def area_for_plugin(plugin_id: str) -> NavigationArea | None:
    """Return the focused sidebar area for a plugin ID."""
    return _AREA_BY_PLUGIN.get(str(plugin_id))


def validate_areas(plugin_ids: Iterable[str]) -> list[str]:
    """Return consistency errors for area/plugin drift."""
    errors: list[str] = []
    known = {str(plugin_id) for plugin_id in plugin_ids}
    area_ids = [area.id for area in _AREAS]
    duplicate_area_ids = sorted({area_id for area_id in area_ids if area_ids.count(area_id) > 1})
    for area_id in duplicate_area_ids:
        errors.append(f"duplicate area id: {area_id}")

    mapped_plugins = [plugin_id for area in _AREAS for plugin_id in area.plugin_ids]
    duplicate_plugins = sorted(
        {plugin_id for plugin_id in mapped_plugins if mapped_plugins.count(plugin_id) > 1}
    )
    for plugin_id in duplicate_plugins:
        errors.append(f"plugin {plugin_id} appears in multiple navigation areas")

    for plugin_id in mapped_plugins:
        if plugin_id not in known:
            errors.append(f"area references unknown plugin {plugin_id}")

    return errors
