"""v15 destination and route-placement definitions.

The existing route manifest remains canonical.  These definitions group those
stable IDs for the simplified shell without importing PyQt or replacing route
identities.
"""

from __future__ import annotations

from collections import Counter

from .manifest import all_routes, get_route
from .models import (
    Destination,
    FedoraVariant,
    NavigationMode,
    RoutePlacement,
    SectionDefinition,
)


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
        "updates",
        advanced_only=True,
        redirect_route_id="maintenance:updates",
        discoverable=False,
    ),
    _placement("maintenance:upgrade-assistant", "software_updates", "fedora_upgrade"),
    _placement("maintenance:action-center", "software_updates", "maintenance_review"),
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
    _placement(
        "health",
        "system",
        "troubleshooting",
        redirect_route_id="diagnostics",
        discoverable=False,
    ),
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
    _placement("settings:advanced", "settings", "advanced"),
    _placement("settings:repair", "settings", "repair"),
    _placement("settings:about", "settings", "about"),
    # Advanced specialist routes.  The logical component boundary is used by
    # policy now; any physical package split remains a Phase 9 decision.
    _placement("performance", "advanced", "performance_tuning", advanced_only=True, component_id="specialist"),
    _placement("gaming", "advanced", "gaming", advanced_only=True, component_id="specialist"),
    _placement("development", "advanced", "development", advanced_only=True, component_id="specialist"),
    _placement("development:containers", "advanced", "development", advanced_only=True, component_id="specialist"),
    _placement("development:developer", "advanced", "developer_tools", advanced_only=True, component_id="specialist"),
    _placement("profiles", "advanced", "profiles", advanced_only=True),
    _placement("extensions", "advanced", "extensions", advanced_only=True),
    _placement("community", "advanced", "community", advanced_only=True, component_id="specialist"),
    _placement("community:presets", "advanced", "community", advanced_only=True, component_id="specialist"),
    _placement("community:marketplace", "advanced", "community_marketplace", advanced_only=True, component_id="specialist"),
    _placement("community:plugins", "advanced", "community_plugins", advanced_only=True, component_id="specialist"),
    _placement("community:featured", "advanced", "community_featured", advanced_only=True, component_id="specialist"),
    _placement("mesh", "advanced", "loofi_link", advanced_only=True, component_id="specialist"),
    _placement("loofi-link:devices", "advanced", "loofi_link", advanced_only=True, component_id="specialist"),
    _placement("loofi-link:clipboard", "advanced", "loofi_link_clipboard", advanced_only=True, component_id="specialist"),
    _placement("loofi-link:file-drop", "advanced", "loofi_link_file_drop", advanced_only=True, component_id="specialist"),
    _placement(
        "logs",
        "system",
        "troubleshooting",
        redirect_route_id="diagnostics:watchtower",
        discoverable=False,
    ),
    _placement("ai_lab", "advanced", "ai_lab", advanced_only=True, component_id="specialist"),
    _placement("ai-lab:models", "advanced", "ai_lab", advanced_only=True, component_id="specialist"),
    _placement("ai-lab:voice", "advanced", "ai_lab_voice", advanced_only=True, component_id="specialist"),
    _placement("ai-lab:knowledge", "advanced", "ai_lab_knowledge", advanced_only=True, component_id="specialist"),
    _placement("agents", "advanced", "agents", advanced_only=True, component_id="specialist"),
    _placement("agents:dashboard", "advanced", "agents", advanced_only=True, component_id="specialist"),
    _placement("agents:my-agents", "advanced", "agents_list", advanced_only=True, component_id="specialist"),
    _placement("agents:create", "advanced", "agents_create", advanced_only=True, component_id="specialist"),
    _placement("agents:activity", "advanced", "agents_activity", advanced_only=True, component_id="specialist"),
    _placement("automation", "advanced", "automation", advanced_only=True, component_id="specialist"),
    _placement("automation:scheduler", "advanced", "automation", advanced_only=True, component_id="specialist"),
    _placement("automation:replicator", "advanced", "automation_replicator", advanced_only=True, component_id="specialist"),
    _placement("teleport", "advanced", "state_teleport", advanced_only=True, component_id="specialist"),
    _placement("virtualization", "advanced", "virtualization", advanced_only=True, component_id="specialist"),
    _placement("virtualization:vms", "advanced", "virtualization", advanced_only=True, component_id="specialist"),
    _placement("virtualization:gpu-passthrough", "advanced", "virtualization_gpu", advanced_only=True, component_id="specialist"),
    _placement("virtualization:disposable", "advanced", "virtualization_disposable", advanced_only=True, component_id="specialist"),
)

_PLACEMENT_BY_ROUTE = {placement.route_id: placement for placement in _PLACEMENTS}


def _section(
    section_id: str,
    destination_id: str,
    label: str,
    icon: str,
    order: int,
    default_route_id: str,
    description: str,
) -> SectionDefinition:
    return SectionDefinition(
        id=section_id,
        destination_id=destination_id,
        label=label,
        icon=icon,
        order=order,
        default_route_id=default_route_id,
        description=description,
    )


_SECTIONS: tuple[SectionDefinition, ...] = (
    _section("overview", "home", "Overview", "home", 10, "atlas_dashboard", "Current state and recommended next steps."),
    _section("applications", "software_updates", "Applications", "packages-software", 10, "software:apps", "Find and manage applications."),
    _section("repositories", "software_updates", "Repositories", "packages-software", 20, "software:repos", "Manage Fedora software sources."),
    _section("flatpak", "software_updates", "Flatpak", "packages-software", 30, "software:flatpak", "Manage Flatpak applications and remotes."),
    _section("updates", "software_updates", "Updates", "update", 40, "maintenance", "Review available system updates."),
    _section("cleanup", "software_updates", "Cleanup", "cleanup", 50, "maintenance:cleanup", "Analyze reclaimable package and cache data."),
    _section("fedora_upgrade", "software_updates", "Fedora Upgrade", "update", 60, "maintenance:upgrade-assistant", "Review Fedora release-upgrade readiness."),
    _section("maintenance_review", "software_updates", "Action Center", "maintenance-health", 70, "maintenance:action-center", "Review, plan, run, and verify maintenance actions."),
    _section("overlays", "software_updates", "Atomic Overlays", "packages-software", 80, "maintenance:overlays", "Review rpm-ostree layered packages."),
    _section("overview", "system", "System Information", "info", 10, "system_info", "Operating system, hardware, and current-state details."),
    _section("performance", "system", "Performance", "cpu-performance", 20, "monitor", "Current resource use and performance diagnostics."),
    _section("processes", "system", "Processes", "cpu-performance", 30, "system-monitor:processes", "Inspect running processes."),
    _section("hardware_power", "system", "Hardware & Power", "hardware-performance", 40, "hardware", "Hardware devices, batteries, and power state."),
    _section("storage", "system", "Storage", "storage-disk", 50, "storage", "Disk use and storage health."),
    _section("system_health_history", "system", "Health History", "maintenance-health", 60, "maintenance:health-timeline", "Review recorded system-health events."),
    _section("troubleshooting", "system", "Troubleshooting", "maintenance-health", 70, "diagnostics", "Diagnose system issues and inspect evidence."),
    _section("boot_diagnostics", "system", "Boot Diagnostics", "logs", 80, "diagnostics:boot", "Inspect boot-time diagnostics."),
    _section("recovery_points", "system", "Recovery Points", "storage-disk", 90, "snapshots", "Create and manage recovery points."),
    _section("connections", "network_security", "Connections", "network-connectivity", 10, "network", "Network connections and current connectivity."),
    _section("dns", "network_security", "DNS", "network-connectivity", 20, "network:dns", "DNS configuration and resolution."),
    _section("network_privacy", "network_security", "Connection Privacy", "security-shield", 30, "network:privacy", "Privacy settings for network connections."),
    _section("network_monitoring", "network_security", "Network Monitoring", "network-traffic", 40, "network:monitoring", "Inspect current network activity."),
    _section("security_overview", "network_security", "Security Overview", "security-shield", 50, "security", "Review the system security posture."),
    _section("firewall", "network_security", "Firewall", "security-shield", 60, "security:firewall", "Review and manage firewall state."),
    _section("privacy", "network_security", "System Privacy", "security-shield", 70, "security:privacy", "Review system-wide privacy settings."),
    _section("exposure", "network_security", "Network Exposure", "network-traffic", 80, "security:ports", "Inspect listening services and open ports."),
    _section("backups", "network_security", "Backups", "storage-disk", 90, "backup", "Configure and review data backups."),
    _section("appearance", "desktop", "Appearance", "appearance-theme", 10, "desktop", "Desktop theme and visual preferences."),
    _section("windows", "desktop", "Windows", "appearance-theme", 20, "desktop:director", "Window-management behavior."),
    _section("displays", "desktop", "Displays", "hardware-performance", 30, "desktop:display", "Display layout and scaling."),
    _section("appearance", "settings", "Appearance", "appearance-theme", 10, "settings", "Application theme and presentation settings."),
    _section("behavior", "settings", "Behavior", "settings", 20, "settings:behavior", "Application behavior and navigation preferences."),
    _section("advanced", "settings", "Advanced Tools", "developer-tools", 30, "settings:advanced", "Advanced application settings."),
    _section("repair", "settings", "Repair Loofi", "maintenance-health", 40, "settings:repair", "Repair application configuration and state."),
    _section("about", "settings", "About", "info", 50, "settings:about", "Version, support, and project information."),
    _section("performance_tuning", "advanced", "Performance Tuning", "cpu-performance", 10, "performance", "Advanced performance tuning."),
    _section("gaming", "advanced", "Gaming", "developer-tools", 20, "gaming", "Gaming-focused system tools."),
    _section("development", "advanced", "Development", "developer-tools", 30, "development", "Developer environments and containers."),
    _section("developer_tools", "advanced", "Developer Tools", "developer-tools", 31, "development:developer", "Language runtimes and editor tooling."),
    _section("profiles", "advanced", "Profiles", "settings", 40, "profiles", "Reusable configuration profiles."),
    _section("extensions", "advanced", "Extensions", "developer-tools", 50, "extensions", "Optional Loofi extensions."),
    _section("community", "advanced", "Community", "packages-software", 60, "community", "Community presets, plugins, and marketplace content."),
    _section("community_marketplace", "advanced", "Preset Marketplace", "packages-software", 61, "community:marketplace", "Browse community presets."),
    _section("community_plugins", "advanced", "Plugins", "developer-tools", 62, "community:plugins", "Manage installed plugins."),
    _section("community_featured", "advanced", "Featured Plugins", "developer-tools", 63, "community:featured", "Review curated community plugins."),
    _section("loofi_link", "advanced", "Loofi Link", "network-connectivity", 70, "mesh", "Device sharing and Loofi Link tools."),
    _section("loofi_link_clipboard", "advanced", "Shared Clipboard", "network-connectivity", 71, "loofi-link:clipboard", "Share clipboard content with paired devices."),
    _section("loofi_link_file_drop", "advanced", "File Drop", "network-connectivity", 72, "loofi-link:file-drop", "Send files to paired devices."),
    _section("ai_lab", "advanced", "AI Lab", "developer-tools", 80, "ai_lab", "Local AI models, voice, and knowledge tools."),
    _section("ai_lab_voice", "advanced", "Voice", "developer-tools", 81, "ai-lab:voice", "Record and transcribe speech locally."),
    _section("ai_lab_knowledge", "advanced", "Knowledge", "developer-tools", 82, "ai-lab:knowledge", "Build and search local knowledge indexes."),
    _section("agents", "advanced", "Agents", "developer-tools", 90, "agents", "Local agent management and activity."),
    _section("agents_list", "advanced", "My Agents", "developer-tools", 91, "agents:my-agents", "Review and manage configured agents."),
    _section("agents_create", "advanced", "Create Agent", "developer-tools", 92, "agents:create", "Create a local agent from a goal."),
    _section("agents_activity", "advanced", "Agent Activity", "developer-tools", 93, "agents:activity", "Inspect recent agent activity."),
    _section("automation", "advanced", "Automation", "settings", 100, "automation", "Schedules and automation workflows."),
    _section("automation_replicator", "advanced", "Replicator", "settings", 101, "automation:replicator", "Export reproducible system configuration."),
    _section("state_teleport", "advanced", "State Teleport", "storage-disk", 110, "teleport", "Move compatible application state."),
    _section("virtualization", "advanced", "Virtualization", "hardware-performance", 120, "virtualization", "Virtual machines and disposable environments."),
    _section("virtualization_gpu", "advanced", "GPU Passthrough", "hardware-performance", 121, "virtualization:gpu-passthrough", "Review VFIO readiness and setup guidance."),
    _section("virtualization_disposable", "advanced", "Disposable VMs", "hardware-performance", 122, "virtualization:disposable", "Create and manage disposable virtual machines."),
)

_SECTION_BY_DESTINATION_AND_ID = {
    (section.destination_id, section.id): section for section in _SECTIONS
}


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


def sections_for_destination(destination_id: str) -> tuple[SectionDefinition, ...]:
    """Return explicit section presentation metadata in stable visual order."""
    return tuple(
        sorted(
            (
                section
                for section in _SECTIONS
                if section.destination_id == str(destination_id)
            ),
            key=lambda section: section.order,
        )
    )


def get_section(
    destination_id: str,
    section_id: str,
) -> SectionDefinition | None:
    """Return explicit metadata for one destination-owned section."""
    return _SECTION_BY_DESTINATION_AND_ID.get(
        (str(destination_id), str(section_id))
    )


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

        section = get_section(placement.destination_id, placement.section_id)
        if section is None:
            errors.append(
                f"route {placement.route_id} references unknown section "
                f"{placement.destination_id}:{placement.section_id}"
            )

    for destination in _DESTINATIONS:
        sections = sections_for_destination(destination.id)
        section_ids = [section.id for section in sections]
        section_orders = [section.order for section in sections]
        for section_id, count in Counter(section_ids).items():
            if count > 1:
                errors.append(
                    f"destination {destination.id} has duplicate section {section_id}"
                )
        for order, count in Counter(section_orders).items():
            if count > 1:
                errors.append(
                    f"destination {destination.id} has duplicate section order {order}"
                )
        for section in sections:
            default_placement = placement_for_route(section.default_route_id)
            if default_placement is None:
                errors.append(
                    f"section {destination.id}:{section.id} has unknown default route "
                    f"{section.default_route_id}"
                )
            elif (
                default_placement.destination_id != destination.id
                or default_placement.section_id != section.id
            ):
                errors.append(
                    f"section {destination.id}:{section.id} default route is outside the section"
                )
            if not section.label or not section.icon:
                errors.append(
                    f"section {destination.id}:{section.id} lacks presentation metadata"
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
