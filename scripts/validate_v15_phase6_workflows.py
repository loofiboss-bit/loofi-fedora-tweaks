#!/usr/bin/env python3
"""Validate v15 Phase 6 workflow routing without probing or mutating the host."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "loofi-fedora-tweaks"
if str(SOURCE) not in sys.path:
    sys.path.insert(0, str(SOURCE))

from core.actions import ActionCatalog  # noqa: E402
from core.navigation import placement_for_route, resolve  # noqa: E402
from core.workflows import CORE_WORKFLOWS, ReclaimAnalysisService  # noqa: E402
from services.software.applications import ApplicationOperationService  # noqa: E402


def validate() -> list[str]:
    """Return contract errors; this function performs no system probe."""
    errors: list[str] = []
    if len(CORE_WORKFLOWS) != 5:
        errors.append("exactly five canonical workflows are required")
    for workflow in CORE_WORKFLOWS:
        if resolve(workflow.preferred_route_id) is None:
            errors.append(f"workflow {workflow.id} has an unknown preferred route")

    catalog_ids = {definition.id for definition in ActionCatalog().list()}
    legacy_ids = {"dnf-clean-all", "fstrim-all", "restart-failed-service"}
    if not legacy_ids.issubset(catalog_ids):
        errors.append("the v14 executable catalog is no longer preserved")

    expected_routes = {
        "maintenance:action-center": ("software_updates", "maintenance_review", None),
        "maintenance:smart-updates": ("software_updates", "updates", "maintenance:updates"),
        "health": ("system", "system_check", None),
        "logs": ("system", "troubleshooting", "diagnostics:watchtower"),
    }
    for route_id, expected in expected_routes.items():
        placement = placement_for_route(route_id)
        actual = (
            placement.destination_id,
            placement.section_id,
            placement.redirect_route_id,
        ) if placement is not None else None
        if actual != expected:
            errors.append(f"route placement drift: {route_id}")

    reclaim = ReclaimAnalysisService.build(
        atomic=False,
        package_cache_bytes=1,
        journal_bytes=1,
    )
    linked_ids = {
        category.action_center_link.action_id
        for category in reclaim.categories
        if category.action_center_link is not None
    }
    if linked_ids != {"dnf-clean-all", "fstrim-all"}:
        errors.append("reclaim links bypass or expand the v14 Action Center catalog")

    catalog_path = SOURCE / "config" / "apps.json"
    entries = json.loads(catalog_path.read_text(encoding="utf-8"))
    for entry in entries:
        arguments = [str(item) for item in entry.get("args", [])]
        if "-c" in arguments and ApplicationOperationService.describe(entry).available:
            errors.append(f"scripted catalog entry is executable: {entry.get('name')}")

    maintenance_source = (SOURCE / "ui" / "maintenance_tab.py").read_text(encoding="utf-8")
    storage_source = (SOURCE / "ui" / "storage_tab.py").read_text(encoding="utf-8")
    cleanup_slice = maintenance_source.split("class _CleanupSubTab", 1)[-1].split("class _OverlaysSubTab", 1)[0]
    if 'PrivilegedCommand.dnf("clean", "all")' in cleanup_slice:
        errors.append("Cleanup still executes dnf-clean-all directly")
    if '["fstrim", "-av"]' in cleanup_slice:
        errors.append("Cleanup still executes fstrim-all directly")
    trim_method = storage_source.split("def _trim_ssd", 1)[-1].split("def _check_filesystem", 1)[0]
    if "StorageManager.trim_ssd" in trim_method:
        errors.append("Storage still executes fstrim-all directly")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    errors = validate()
    payload = {
        "phase": 6,
        "workflows": [workflow.id for workflow in CORE_WORKFLOWS],
        "host_probes": 0,
        "mutations": 0,
        "status": "passed" if not errors else "failed",
        "errors": errors,
    }
    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print(f"Phase 6 workflow validation: {payload['status']}")
        for error in errors:
            print(f"- {error}")
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
