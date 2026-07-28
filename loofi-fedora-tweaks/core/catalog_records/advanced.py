"""Compose the destination-owned Specialist Tools catalog records."""

from __future__ import annotations

from typing import Any, Final

from .advanced_automation import RECORDS as AUTOMATION_RECORDS
from .advanced_foundation import RECORDS as FOUNDATION_RECORDS
from .advanced_workspace import RECORDS as WORKSPACE_RECORDS


def _combine(key: str) -> tuple[dict[str, Any], ...]:
    return tuple(
        record
        for records in (FOUNDATION_RECORDS, WORKSPACE_RECORDS, AUTOMATION_RECORDS)
        for record in records[key]
    )


RECORDS: Final[dict[str, Any]] = {
    "plugins": _combine("plugins"),
    "routes": _combine("routes"),
    "placements": _combine("placements"),
    "sections": _combine("sections"),
    "destination": {
        "id": "advanced",
        "label": "Specialist Tools",
        "icon": "developer-tools",
        "default_route_id": "performance",
        "route_ids": (
            "performance",
            "gaming",
            "development",
            "development:containers",
            "development:developer",
            "profiles",
            "extensions",
            "community",
            "community:presets",
            "community:marketplace",
            "community:plugins",
            "community:featured",
            "mesh",
            "loofi-link:devices",
            "loofi-link:clipboard",
            "loofi-link:file-drop",
            "ai_lab",
            "ai-lab:models",
            "ai-lab:voice",
            "ai-lab:knowledge",
            "agents",
            "agents:dashboard",
            "agents:my-agents",
            "agents:create",
            "agents:activity",
            "automation",
            "automation:scheduler",
            "automation:replicator",
            "teleport",
            "virtualization",
            "virtualization:vms",
            "virtualization:gpu-passthrough",
            "virtualization:disposable",
        ),
        "advanced_only": True,
    },
}
