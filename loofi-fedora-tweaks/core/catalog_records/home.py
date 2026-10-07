# flake8: noqa
"""Destination-owned product catalog records for home."""

from __future__ import annotations

from typing import Any, Final

RECORDS: Final[dict[str, Any]] = {'plugins': ({'id': 'atlas_dashboard',
              'name': 'Home',
              'description': 'System status, the next useful action, and common Fedora tasks.',
              'icon': 'home',
              'destination_id': 'home',
              'module': 'ui.atlas_dashboard_tab',
              'class_name': 'AtlasDashboardTab',
              'component': 'core',
              'visibility': 'standard',
              'compat': {},
              'category': 'System',
              'badge': 'recommended',
              'order': 0},),
 'routes': ({'id': 'atlas_dashboard',
             'label': 'Home',
             'plugin_id': 'atlas_dashboard',
             'category': 'System',
             'icon': 'home',
             'description': 'System status, the next useful action, and common Fedora tasks.',
             'aliases': ('atlas', 'atlas-home', 'fedora-control-center'),
             'keywords': ('home', 'beacon', 'tasks', 'readiness'),
             'risk': 'none',
             'visibility': 'beginner',
             'subroute': ''},),
 'placements': ({'route_id': 'atlas_dashboard',
                 'destination_id': 'home',
                 'section_id': 'overview',
                 'advanced_only': False,
                 'component_id': 'core',
                 'required_capabilities': (),
                 'allowed_variants': ('traditional', 'atomic'),
                 'redirect_route_id': None,
                 'discoverable': True},),
 'sections': ({'id': 'overview',
               'destination_id': 'home',
               'label': 'Overview',
               'icon': 'home',
               'order': 10,
               'default_route_id': 'atlas_dashboard',
               'description': 'Current state and recommended next steps.'},),
 'destination': {'id': 'home',
                 'label': 'Home',
                 'icon': 'home',
                 'default_route_id': 'atlas_dashboard',
                 'route_ids': ('atlas_dashboard',),
                 'advanced_only': False}}

# Overview is a separate route: saved Atlas links retain their Tweaks meaning.
RECORDS["plugins"] += ({
    "id": "overview", "name": "Overview",
    "description": "Live resources, hardware readings, and recent maintenance.",
    "icon": "overview-dashboard", "destination_id": "home",
    "module": "ui.overview_page", "class_name": "OverviewPage",
    "component": "core", "visibility": "standard", "compat": {},
    "category": "System", "badge": "", "order": -10,
},)
RECORDS["routes"] += ({
    "id": "overview", "label": "Overview", "plugin_id": "overview",
    "category": "System", "icon": "overview-dashboard",
    "description": "Live resource use, hardware readings, and recent maintenance.",
    "aliases": ("resource-overview",),
    "keywords": ("overview", "cpu", "ram", "gpu", "battery", "temperature", "resources"),
    "risk": "none", "visibility": "beginner", "subroute": "",
},)
RECORDS["placements"] += ({
    "route_id": "overview", "destination_id": "home", "section_id": "live_status",
    "advanced_only": False, "component_id": "core", "required_capabilities": (),
    "allowed_variants": ("traditional", "atomic"), "redirect_route_id": None,
    "discoverable": True,
},)
RECORDS["sections"] += ({
    "id": "live_status", "destination_id": "home", "label": "Overview",
    "icon": "overview-dashboard", "order": 0, "default_route_id": "overview",
    "description": "Resource and hardware readings while the page is visible.",
},)
RECORDS["destination"]["default_route_id"] = "overview"
RECORDS["destination"]["route_ids"] = ("overview", "atlas_dashboard")
