# flake8: noqa
"""Destination-owned product catalog records for changes."""

from __future__ import annotations

from typing import Any, Final

RECORDS: Final[dict[str, Any]] = {
    'plugins': (
        {
            'id': 'changes',
            'name': 'Changes',
            'description': 'Linear review, confirmation, execution, and verification for system actions.',
            'icon': 'maintenance-health',
            'destination_id': 'changes',
            'module': 'ui.maintenance_action_center',
            'class_name': 'ChangesTab',
            'component': 'core',
            'visibility': 'standard',
            'compat': {},
            'category': 'Maintenance',
            'badge': '',
            'order': 10,
        },
    ),
    'routes': (
        {
            'id': 'changes',
            'label': 'Changes',
            'plugin_id': 'changes',
            'category': 'Maintenance',
            'icon': 'maintenance-health',
            'description': 'Review and verify pending and recent system changes.',
            'aliases': ('Changes', 'Action Center', 'Review Changes'),
            'keywords': ('changes', 'action', 'review', 'verify', 'history'),
            'risk': 'none',
            'visibility': 'beginner',
            'subroute': '',
        },
        {
            'id': 'maintenance:action-center',
            'label': 'Action Center',
            'plugin_id': 'changes',
            'category': 'Maintenance',
            'icon': 'maintenance-health',
            'description': 'Preview, queue, confirm, verify, and review recent maintenance actions.',
            'aliases': ('Action Center', 'Action Inbox', 'Harbor Actions'),
            'keywords': ('action', 'preview', 'queue', 'rollback', 'maintenance', 'harbor'),
            'risk': 'medium',
            'visibility': 'all',
            'subroute': 'action-center',
        },
    ),
    'placements': (
        {
            'route_id': 'changes',
            'destination_id': 'changes',
            'section_id': 'review',
            'advanced_only': False,
            'component_id': 'core',
            'required_capabilities': (),
            'allowed_variants': ('traditional', 'atomic'),
            'redirect_route_id': None,
            'discoverable': True,
        },
        {
            'route_id': 'maintenance:action-center',
            'destination_id': 'changes',
            'section_id': 'review',
            'advanced_only': False,
            'component_id': 'core',
            'required_capabilities': (),
            'allowed_variants': ('traditional', 'atomic'),
            'redirect_route_id': None,
            'discoverable': True,
        },
    ),
    'sections': (
        {
            'id': 'review',
            'destination_id': 'changes',
            'label': 'Review & Verify',
            'icon': 'maintenance-health',
            'order': 10,
            'default_route_id': 'changes',
            'description': 'Review, confirm, and verify system maintenance changes.',
        },
    ),
    'destination': {
        'id': 'changes',
        'label': 'Changes',
        'icon': 'maintenance-health',
        'default_route_id': 'changes',
        'route_ids': ('changes', 'maintenance:action-center'),
        'advanced_only': False,
    },
}
