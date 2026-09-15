"""Standalone v29 utility-surface route records.

The v28 ``product_catalog`` projection is kept byte-for-byte compatible for
persisted navigation state.  These records describe the v29 landing surfaces
without silently replacing that compatibility projection; the v29 shell can
adopt them explicitly when its UI migration is ready.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any, Final, Literal


RouteClassification = Literal[
    "active_task",
    "instruction_handoff",
    "compatibility_reader",
    "retired",
]

ActionClassification = Literal[
    "active_task",
    "instruction_handoff",
    "compatibility_reader",
    "retired",
]


TASK_ROUTE_RECORDS: Final[tuple[dict[str, Any], ...]] = (
    {
        "id": "home",
        "label": "Home",
        "icon": "home",
        "description": "Fedora status, the next useful action, and recent activity.",
        "area": "home",
        "keywords": ("home", "status", "overview"),
    },
    {
        "id": "install",
        "label": "Install",
        "icon": "install",
        "description": "Find trusted Fedora RPM and Flatpak applications.",
        "area": "install",
        "keywords": ("install", "apps", "applications", "flatpak", "rpm"),
    },
    {
        "id": "tune",
        "label": "Tune",
        "icon": "settings",
        "description": "Apply reviewed Fedora and desktop adjustments.",
        "area": "tune",
        "keywords": ("tune", "privacy", "performance", "desktop", "kde", "gnome"),
    },
    {
        "id": "fix",
        "label": "Fix",
        "icon": "diagnostics",
        "description": "Diagnose a symptom and choose a verified repair.",
        "area": "fix",
        "keywords": ("fix", "diagnose", "repair", "troubleshoot"),
    },
    {
        "id": "update",
        "label": "Update",
        "icon": "update",
        "description": "Review and apply system, Flatpak, and firmware updates.",
        "area": "update",
        "keywords": ("update", "system", "flatpak", "firmware"),
    },
    {
        "id": "activity",
        "label": "Activity & Recovery",
        "icon": "history",
        "description": "Review task results, pending action, and recovery guidance.",
        "area": "activity",
        "keywords": ("activity", "history", "changes", "recovery"),
    },
)


# Deep links written by v28 remain valid but land in the single v29 activity
# surface where the persisted plan/run/outcome can be reviewed.
TASK_ROUTE_REDIRECTS: Final[dict[str, str]] = {
    "changes": "activity",
    "maintenance:action-center": "activity",
}


# Explicit route authority for the phase-one inventory.  The compatibility
# routes are deliberately named here rather than inferred from labels so a
# future rename cannot accidentally expose a retired Action Center screen.
_ROUTE_CLASSIFICATION_OVERRIDES: Final[dict[str, RouteClassification]] = {
    "changes": "compatibility_reader",
    "maintenance:action-center": "compatibility_reader",
    "dashboard": "compatibility_reader",
    "maintenance:health-timeline": "compatibility_reader",
    "settings": "instruction_handoff",
    "settings:appearance": "instruction_handoff",
    "settings:behavior": "instruction_handoff",
    "settings:application": "instruction_handoff",
    "settings:repair": "instruction_handoff",
    "settings:about": "instruction_handoff",
}


def classify_route(route_id: str) -> RouteClassification:
    """Return the v29 phase-one classification for one route ID.

    The five utility records and the Activity record are active product
    surfaces. Existing specialist routes remain safe handoffs/readers while
    their owning task pages are migrated in later vertical-flow phases.
    """
    key = str(route_id or "").strip()
    if key in {str(item["id"]) for item in TASK_ROUTE_RECORDS}:
        return "active_task"
    override = _ROUTE_CLASSIFICATION_OVERRIDES.get(key)
    if override is not None:
        return override
    return "instruction_handoff"


def route_classifications(route_ids: Iterable[str] | None = None) -> dict[str, RouteClassification]:
    """Return a complete, deterministic route classification inventory."""
    if route_ids is None:
        from core.navigation.manifest import all_routes

        route_ids = (route.id for route in all_routes())
    return {str(route_id): classify_route(str(route_id)) for route_id in route_ids}


def classify_action(definition: object) -> ActionClassification:
    """Classify an audited action without exposing its command renderer."""
    operation_class = str(getattr(definition, "operation_class", "host"))
    if operation_class == "manual_only":
        return "instruction_handoff"
    return "active_task"


def action_classifications(definitions: Iterable[object] | None = None) -> dict[str, ActionClassification]:
    """Return a complete classification inventory for the audited action catalog."""
    if definitions is None:
        from core.actions.catalog import ActionCatalog

        definitions = ActionCatalog().list()
    return {
        str(getattr(definition, "id", "")): classify_action(definition)
        for definition in definitions
        if str(getattr(definition, "id", ""))
    }


def validate_route_classifications(route_ids: Iterable[str] | None = None) -> list[str]:
    """Validate that every canonical route has a known phase-one class."""
    classifications = route_classifications(route_ids)
    errors: list[str] = []
    valid = {"active_task", "instruction_handoff", "compatibility_reader", "retired"}
    for route_id, classification in classifications.items():
        if classification not in valid:
            errors.append(f"route {route_id} has invalid classification {classification}")
    return errors


RECORDS: Final[dict[str, Any]] = {
    "routes": TASK_ROUTE_RECORDS,
    "redirects": TASK_ROUTE_REDIRECTS,
    # The complete route/action inventories are resolved lazily by the helper
    # functions so importing product metadata never probes the host.
    "route_classification_overrides": _ROUTE_CLASSIFICATION_OVERRIDES,
}


__all__ = [
    "ActionClassification",
    "RECORDS",
    "RouteClassification",
    "TASK_ROUTE_RECORDS",
    "TASK_ROUTE_REDIRECTS",
    "action_classifications",
    "classify_action",
    "classify_route",
    "route_classifications",
    "validate_route_classifications",
]
