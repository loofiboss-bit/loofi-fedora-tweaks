"""v20 Continuity additions to the generated product catalog.

Keep the generated v18 catalog immutable while adding the v20 route through a
small, reviewable extension. Stable destination and route identifiers are
preserved for compatibility.
"""

from __future__ import annotations

from typing import Any, Mapping


def extend_catalog(base: Mapping[str, tuple[Mapping[str, Any], ...]]) -> dict[str, tuple[Mapping[str, Any], ...]]:
    """Return the base catalog with the Continuity route and presentation copy."""
    destinations = []
    for record in base["destinations"]:
        updated = dict(record)
        if updated["id"] == "system":
            updated["route_ids"] = (*updated["route_ids"], "activity")
        elif updated["id"] == "advanced":
            updated["label"] = "Specialist Tools"
        destinations.append(updated)

    return {
        **base,
        "plugins": (
            *base["plugins"],
            {
                "id": "activity",
                "name": "Activity & Recovery",
                "description": "Review trusted local change history and prepare supported recovery.",
                "icon": "logs",
                "destination_id": "system",
                "module": "ui.activity_recovery_tab",
                "class_name": "ActivityRecoveryTab",
                "component": "core",
                "visibility": "standard",
                "compat": {},
                "category": "System",
                "badge": "recommended",
                "order": 65,
            },
        ),
        "routes": (
            *base["routes"],
            {
                "id": "activity",
                "label": "Activity & Recovery",
                "plugin_id": "activity",
                "category": "System",
                "icon": "logs",
                "description": "Trusted local change history with conservative recovery guidance.",
                "aliases": ("Change Journal", "Activity", "Recovery"),
                "keywords": ("changes", "history", "dnf5", "rpm-ostree", "flatpak", "firmware", "recovery"),
                "risk": "none",
                "visibility": "beginner",
                "subroute": "",
            },
        ),
        "placements": (
            *base["placements"],
            {
                "route_id": "activity",
                "destination_id": "system",
                "section_id": "activity_recovery",
                "advanced_only": False,
                "component_id": "core",
                "required_capabilities": (),
                "allowed_variants": ("traditional", "atomic"),
                "redirect_route_id": None,
                "discoverable": True,
            },
        ),
        "sections": (
            *base["sections"],
            {
                "id": "activity_recovery",
                "destination_id": "system",
                "label": "Activity & Recovery",
                "icon": "logs",
                "order": 65,
                "default_route_id": "activity",
                "description": "Review trusted changes and prepare supported recovery.",
            },
        ),
        "destinations": tuple(destinations),
    }
