"""v15 destination and route-placement definitions.

The existing route manifest remains canonical.  These definitions group those
stable IDs for the simplified shell without importing PyQt or replacing route
identities.
"""

from __future__ import annotations

from collections import Counter

from .manifest import all_routes, get_route
from .models import Destination, FedoraVariant, NavigationMode, RoutePlacement


def _placement(
    route_id: str,
    destination_id: str,
    section_id: str,
    *,
    advanced_only: bool = False,
    component_id: str = "core",
    atomic_only: bool = False,
    required_capabilities: frozenset[str] = frozenset(),
    redirect_route_id: str | None = None,
    discoverable: bool = True,
) -> RoutePlacement:
    variants = (
        frozenset({FedoraVariant.ATOMIC})
        if atomic_only
        else frozenset({FedoraVariant.TRADITIONAL, FedoraVariant.ATOMIC})
    )
    return RoutePlacement(
        route_id=route_id,
        destination_id=destination_id,
        section_id=section_id,
        advanced_only=advanced_only,
        component_id=component_id,
        required_capabilities=required_capabilities,
        allowed_variants=variants,
        redirect_route_id=redirect_route_id,
        discoverable=discoverable,
    )


_PLACEMENTS: tuple[RoutePlacement, ...] = (
    # Home
    _placement("atlas_dashboard", "home", "overview"),
    # Software & Updates
    _placement("software", "software_updates", "applications"),
    _placement("software:apps", "software_updates", "applications"),
    _placement("software:repos", "software_updates", "repositories"),
    _placement("software:flatpak", "software_updates", "flatpak"),
    _placement("maintenance", "software_updates", "updates"),
    _placement("maintenance:updates", "software_updates", "updates"),
    _placement("maintenance:cleanup", "software_updates", "cleanup"),
    _placement(
        "maintenance:smart-updates",
        "software_updates",
        "advanced_updates",
        advanced_only=True,
    ),
    _placement("maintenance:upgrade-assistant", "software_updates", "fedora_upgrade"),
    _placement("maintenance:action-center", "software_updates", "action_center"),
    _placement(
        "maintenance:overlays",
        "software_updates",
        "overlays",
        advanced_only=True,
        atomic_only=True,
        required_capabilities=frozenset({"rpm-ostree"}),
    ),
    # System
    _placement(
        "dashboard",
        "system",
        "overview",
        redirect_route_id="system_info",
        discoverable=False,
    ),
    _placement("system_info", "system", "overview"),
    _placement("monitor", "system", "performance"),
    _placement("system-monitor:performance", "system", "performance"),
    _placement("system-monitor:processes", "system", "processes"),
    _placement("hardware", "system", "hardware_power"),
    _placement("storage", "system", "storage"),
    _placement("health", "system", "system_health"),
    _placement("maintenance:health-timeline", "system", "system_health_history"),
    _placement("diagnostics", "system", "troubleshooting"),
    _placement("diagnostics:watchtower", "system", "troubleshooting"),
    _placement(
        "diagnostics:boot",
        "system",
        "boot_diagnostics",
        advanced_only=True,
    ),
    _placement("snapshots", "system", "recovery_points"),
    # Network & Security
    _placement("network", "network_security", "connections"),
    _placement("network:connections", "network_security", "connections"),
    _placement("network:dns", "network_security", "dns"),
    _placement("network:privacy", "network_security", "network_privacy"),
    _placement("network:monitoring", "network_security", "network_monitoring"),
    _placement("security", "network_security", "security_overview"),
    _placement("security:overview", "network_security", "security_overview"),
    _placement("security:firewall", "network_security", "firewall"),
    _placement("security:privacy", "network_security", "privacy"),
    _placement("security:ports", "network_security", "exposure"),
    _placement("backup", "network_security", "backups"),
    # Desktop
    _placement("desktop", "desktop", "appearance"),
    _placement("desktop:director", "desktop", "windows"),
    _placement("desktop:theming", "desktop", "appearance"),
    _placement("desktop:display", "desktop", "displays"),
    # Settings
    _placement("settings", "settings", "appearance"),
    _placement("settings:appearance", "settings", "appearance"),
    _placement("settings:behavior", "settings", "behavior"),
    _placement(
        "settings:advanced",
        "settings",
        "advanced",
        advanced_only=True,
    ),
    # Advanced specialist routes.  The logical component boundary is used by
    # policy now; any physical package split remains a Phase 9 decision.
    _placement("performance", "advanced", "performance_tuning", advanced_only=True, component_id="specialist"),
    _placement("gaming", "advanced", "gaming", advanced_only=True, component_id="specialist"),
    _placement("development", "advanced", "development", advanced_only=True, component_id="specialist"),
    _placement("development:containers", "advanced", "development", advanced_only=True, component_id="specialist"),
    _placement("development:developer", "advanced", "development", advanced_only=True, component_id="specialist"),
    _placement("profiles", "advanced", "profiles", advanced_only=True),
    _placement("extensions", "advanced", "extensions", advanced_only=True),
    _placement("community", "advanced", "community", advanced_only=True, component_id="specialist"),
    _placement("community:presets", "advanced", "community", advanced_only=True, component_id="specialist"),
    _placement("community:marketplace", "advanced", "community", advanced_only=True, component_id="specialist"),
    _placement("community:plugins", "advanced", "community", advanced_only=True, component_id="specialist"),
    _placement("community:featured", "advanced", "community", advanced_only=True, component_id="specialist"),
    _placement("mesh", "advanced", "loofi_link", advanced_only=True, component_id="specialist"),
    _placement("loofi-link:devices", "advanced", "loofi_link", advanced_only=True, component_id="specialist"),
    _placement("loofi-link:clipboard", "advanced", "loofi_link", advanced_only=True, component_id="specialist"),
    _placement("loofi-link:file-drop", "advanced", "loofi_link", advanced_only=True, component_id="specialist"),
    _placement("logs", "advanced", "logs", advanced_only=True, component_id="specialist"),
    _placement("ai_lab", "advanced", "ai_lab", advanced_only=True, component_id="specialist"),
    _placement("ai-lab:models", "advanced", "ai_lab", advanced_only=True, component_id="specialist"),
    _placement("ai-lab:voice", "advanced", "ai_lab", advanced_only=True, component_id="specialist"),
    _placement("ai-lab:knowledge", "advanced", "ai_lab", advanced_only=True, component_id="specialist"),
    _placement("agents", "advanced", "agents", advanced_only=True, component_id="specialist"),
    _placement("agents:dashboard", "advanced", "agents", advanced_only=True, component_id="specialist"),
    _placement("agents:my-agents", "advanced", "agents", advanced_only=True, component_id="specialist"),
    _placement("agents:create", "advanced", "agents", advanced_only=True, component_id="specialist"),
    _placement("agents:activity", "advanced", "agents", advanced_only=True, component_id="specialist"),
    _placement("automation", "advanced", "automation", advanced_only=True, component_id="specialist"),
    _placement("automation:scheduler", "advanced", "automation", advanced_only=True, component_id="specialist"),
    _placement("automation:replicator", "advanced", "automation", advanced_only=True, component_id="specialist"),
    _placement("teleport", "advanced", "state_teleport", advanced_only=True, component_id="specialist"),
    _placement("virtualization", "advanced", "virtualization", advanced_only=True, component_id="specialist"),
    _placement("virtualization:vms", "advanced", "virtualization", advanced_only=True, component_id="specialist"),
    _placement("virtualization:gpu-passthrough", "advanced", "virtualization", advanced_only=True, component_id="specialist"),
    _placement("virtualization:disposable", "advanced", "virtualization", advanced_only=True, component_id="specialist"),
)

_PLACEMENT_BY_ROUTE = {placement.route_id: placement for placement in _PLACEMENTS}


def _route_ids(destination_id: str) -> tuple[str, ...]:
    return tuple(
        placement.route_id
        for placement in _PLACEMENTS
        if placement.destination_id == destination_id
    )


STANDARD_DESTINATIONS: tuple[Destination, ...] = (
    Destination("home", "Home", "home", "atlas_dashboard", _route_ids("home")),
    Destination(
        "software_updates",
        "Software & Updates",
        "packages-software",
        "software:apps",
        _route_ids("software_updates"),
    ),
    Destination(
        "system",
        "System",
        "hardware-performance",
        "system_info",
        _route_ids("system"),
    ),
    Destination(
        "network_security",
        "Network & Security",
        "security-shield",
        "network",
        _route_ids("network_security"),
    ),
    Destination(
        "desktop",
        "Desktop",
        "appearance-theme",
        "desktop",
        _route_ids("desktop"),
    ),
    Destination(
        "settings",
        "Settings",
        "settings",
        "settings",
        _route_ids("settings"),
    ),
)

ADVANCED_DESTINATION = Destination(
    "advanced",
    "Advanced",
    "developer-tools",
    "performance",
    _route_ids("advanced"),
    advanced_only=True,
)

_DESTINATIONS = STANDARD_DESTINATIONS + (ADVANCED_DESTINATION,)
_DESTINATION_BY_ID = {destination.id: destination for destination in _DESTINATIONS}


def all_destinations() -> tuple[Destination, ...]:
    """Return all destination definitions, including Advanced."""
    return _DESTINATIONS


def destinations_for_mode(mode: NavigationMode) -> tuple[Destination, ...]:
    """Return the six Standard destinations and optional Advanced destination."""
    if mode is NavigationMode.ADVANCED:
        return _DESTINATIONS
    return STANDARD_DESTINATIONS


def get_destination(destination_id: str) -> Destination | None:
    """Return a destination by stable ID."""
    return _DESTINATION_BY_ID.get(str(destination_id))


def placement_for_route(route_id: str) -> RoutePlacement | None:
    """Return placement metadata for an exact canonical route ID."""
    return _PLACEMENT_BY_ROUTE.get(str(route_id))


def validate_destinations() -> list[str]:
    """Return destination/placement errors against the canonical manifest."""
    errors: list[str] = []
    manifest_ids = {route.id for route in all_routes()}
    placement_ids = [placement.route_id for placement in _PLACEMENTS]

    for route_id, count in Counter(placement_ids).items():
        if count > 1:
            errors.append(f"route {route_id} has {count} destination placements")

    for route_id in sorted(manifest_ids - set(placement_ids)):
        errors.append(f"route {route_id} has no destination placement")
    for route_id in sorted(set(placement_ids) - manifest_ids):
        errors.append(f"placement references unknown route {route_id}")

    destination_ids = [destination.id for destination in _DESTINATIONS]
    for destination_id, count in Counter(destination_ids).items():
        if count > 1:
            errors.append(f"duplicate destination id: {destination_id}")

    for destination in _DESTINATIONS:
        if get_route(destination.default_route_id) is None:
            errors.append(
                f"destination {destination.id} has unknown default route "
                f"{destination.default_route_id}"
            )
        if destination.default_route_id not in destination.route_ids:
            errors.append(
                f"destination {destination.id} default route is outside the destination"
            )

    for placement in _PLACEMENTS:
        placed_destination = get_destination(placement.destination_id)
        if placed_destination is None:
            errors.append(
                f"route {placement.route_id} references unknown destination "
                f"{placement.destination_id}"
            )
        elif placement.route_id not in placed_destination.route_ids:
            errors.append(
                f"route {placement.route_id} missing from destination "
                f"{placement.destination_id}"
            )
        if placement.redirect_route_id and get_route(placement.redirect_route_id) is None:
            errors.append(
                f"route {placement.route_id} redirects to unknown route "
                f"{placement.redirect_route_id}"
            )

    redirects = {
        placement.route_id: placement.redirect_route_id
        for placement in _PLACEMENTS
        if placement.redirect_route_id
    }
    for route_id, redirect_route_id in redirects.items():
        seen = {route_id}
        current = redirect_route_id
        while current in redirects:
            if current in seen:
                errors.append(f"route {route_id} has a redirect cycle")
                break
            seen.add(current)
            current = redirects[current]

    return errors
