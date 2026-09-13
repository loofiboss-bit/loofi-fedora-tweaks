# flake8: noqa
"""Compose destination-owned source records into stable global projections."""

from __future__ import annotations

from typing import Any, Final

from .changes import RECORDS as CHANGES_RECORDS
from .home import RECORDS as HOME_RECORDS
from .network_security import RECORDS as NETWORK_SECURITY_RECORDS
from .settings import RECORDS as SETTINGS_RECORDS
from .software_updates import RECORDS as SOFTWARE_UPDATES_RECORDS
from .system import RECORDS as SYSTEM_RECORDS

DESTINATION_RECORDS: Final[dict[str, dict[str, Any]]] = {
    "home": HOME_RECORDS,
    "software_updates": SOFTWARE_UPDATES_RECORDS,
    "system": SYSTEM_RECORDS,
    "network_security": NETWORK_SECURITY_RECORDS,
    "changes": CHANGES_RECORDS,
    "settings": SETTINGS_RECORDS,
}

PLUGIN_ORDER = (
    'atlas_dashboard',
    'software',
    'maintenance',
    'system_info',
    'monitor',
    'health',
    'hardware',
    'storage',
    'snapshots',
    'diagnostics',
    'activity',
    'network',
    'security',
    'backup',
    'changes',
    'settings',
)

ROUTE_ORDER = (
    'atlas_dashboard',
    'software',
    'software:apps',
    'software:repos',
    'software:flatpak',
    'maintenance',
    'maintenance:updates',
    'maintenance:cleanup',
    'maintenance:smart-updates',
    'maintenance:upgrade-assistant',
    'maintenance:overlays',
    'dashboard',
    'system_info',
    'monitor',
    'system-monitor:performance',
    'system-monitor:processes',
    'maintenance:health-timeline',
    'snapshots',
    'hardware',
    'storage',
    'health',
    'logs',
    'diagnostics',
    'diagnostics:watchtower',
    'diagnostics:boot',
    'activity',
    'network',
    'network:connections',
    'network:dns',
    'network:privacy',
    'network:monitoring',
    'security',
    'security:overview',
    'security:firewall',
    'security:privacy',
    'security:ports',
    'backup',
    'changes',
    'maintenance:action-center',
    'settings',
    'settings:appearance',
    'settings:behavior',
    'settings:advanced',
    'settings:repair',
    'settings:about',
)

PLACEMENT_ORDER = ROUTE_ORDER

SECTION_ORDER = (
    ('home', 'overview'),
    ('software_updates', 'applications'),
    ('software_updates', 'repositories'),
    ('software_updates', 'flatpak'),
    ('software_updates', 'updates'),
    ('software_updates', 'cleanup'),
    ('software_updates', 'fedora_upgrade'),
    ('software_updates', 'overlays'),
    ('system', 'overview'),
    ('system', 'performance'),
    ('system', 'processes'),
    ('system', 'hardware_power'),
    ('system', 'storage'),
    ('system', 'system_check'),
    ('system', 'troubleshooting'),
    ('system', 'boot_diagnostics'),
    ('system', 'recovery_points'),
    ('system', 'activity_recovery'),
    ('network_security', 'connections'),
    ('network_security', 'dns'),
    ('network_security', 'network_privacy'),
    ('network_security', 'network_monitoring'),
    ('network_security', 'security_overview'),
    ('network_security', 'firewall'),
    ('network_security', 'privacy'),
    ('network_security', 'exposure'),
    ('network_security', 'backups'),
    ('changes', 'review'),
    ('settings', 'appearance'),
    ('settings', 'behavior'),
    ('settings', 'advanced'),
    ('settings', 'repair'),
    ('settings', 'about'),
)

DESTINATION_ORDER = (
    'home',
    'software_updates',
    'system',
    'network_security',
    'changes',
    'settings',
)


def compose_catalog_data() -> dict[str, tuple[dict[str, Any], ...]]:
    """Compose destination-owned records into the established global order."""
    plugins = {record["id"]: record for records in DESTINATION_RECORDS.values() for record in records["plugins"]}
    routes = {record["id"]: record for records in DESTINATION_RECORDS.values() for record in records["routes"]}
    placements = {
        record["route_id"]: record
        for records in DESTINATION_RECORDS.values()
        for record in records["placements"]
    }
    sections = {
        (record["destination_id"], record["id"]): record
        for records in DESTINATION_RECORDS.values()
        for record in records["sections"]
    }
    destinations = {destination_id: records["destination"] for destination_id, records in DESTINATION_RECORDS.items()}
    return {
        "plugins": tuple(plugins[plugin_id] for plugin_id in PLUGIN_ORDER),
        "routes": tuple(routes[route_id] for route_id in ROUTE_ORDER),
        "placements": tuple(placements[route_id] for route_id in PLACEMENT_ORDER),
        "sections": tuple(sections[section_key] for section_key in SECTION_ORDER),
        "destinations": tuple(destinations[destination_id] for destination_id in DESTINATION_ORDER),
    }
