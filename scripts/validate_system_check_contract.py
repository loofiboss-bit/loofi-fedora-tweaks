#!/usr/bin/env python3
"""Validate the canonical System Check trust and compatibility contract."""

from __future__ import annotations

import ast
import inspect
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT / "loofi-fedora-tweaks"
sys.path.insert(0, str(SOURCE))

from core.actions.catalog import ActionCatalog  # noqa: E402
from core.system_check.handoff import FindingActionHandoff  # noqa: E402
from core.system_check.mappings import (  # noqa: E402
    FINDING_ACTION_MAPPINGS,
    FindingActionMapping,
    validate_mappings,
)
from core.system_check.service import (  # noqa: E402
    QUICK_PROFILE_ID,
    QUICK_PROFILE_SOURCES,
    SystemCheckService,
)

EXPECTED_PROFILE_ID = "system-check-quick-v1"
EXPECTED_SOURCES = (
    "state-integrity",
    "maintenance",
    "storage-reclaim",
    "action-center",
    "pending-reboot",
)
EXPECTED_TIMEOUTS = {
    "state-integrity": 20.0,
    "maintenance": 45.0,
    "storage-reclaim": 25.0,
    "action-center": 10.0,
    "pending-reboot": 20.0,
}
EXPECTED_HANDOFF_PARAMETERS = (
    "self",
    "check_result_id",
    "finding_fingerprint",
    "origin_route",
)
EXPECTED_MAPPING_FIELDS = (
    "finding_id",
    "action_id",
    "parameter_sources",
    "applicable_variants",
)


def _imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    modules = {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    }
    modules.update(
        node.module
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module
    )
    return modules


def validate() -> list[str]:
    """Return release-blocking System Check contract violations."""
    errors: list[str] = []

    if QUICK_PROFILE_ID != EXPECTED_PROFILE_ID:
        errors.append(
            f"quick profile ID changed: expected {EXPECTED_PROFILE_ID}, got {QUICK_PROFILE_ID}"
        )
    if QUICK_PROFILE_SOURCES != EXPECTED_SOURCES:
        errors.append(
            f"quick profile sources changed: expected {EXPECTED_SOURCES}, got {QUICK_PROFILE_SOURCES}"
        )

    service = SystemCheckService()
    actual_timeouts = {
        collector.source_id: collector.timeout_seconds
        for collector in service.collectors
    }
    if actual_timeouts != EXPECTED_TIMEOUTS:
        errors.append(
            f"quick profile timeout policy changed: expected {EXPECTED_TIMEOUTS}, got {actual_timeouts}"
        )

    try:
        validate_mappings()
    except ValueError as exc:
        errors.append(f"finding mappings rejected: {exc}")

    mapping_fields = tuple(FindingActionMapping.__dataclass_fields__)
    if mapping_fields != EXPECTED_MAPPING_FIELDS:
        errors.append(
            "finding mapping authority expanded beyond IDs, closed parameter "
            f"sources, and variants: {mapping_fields}"
        )

    catalog = ActionCatalog()
    for mapping in FINDING_ACTION_MAPPINGS:
        definition = catalog.get(mapping.action_id)
        if definition is None:
            errors.append(
                f"finding {mapping.finding_id} references an unknown action"
            )
            continue
        if definition.operation_class == "manual_only":
            errors.append(
                f"finding {mapping.finding_id} references a manual-only action"
            )

    parameters = tuple(
        inspect.signature(FindingActionHandoff.resolve).parameters
    )
    if parameters != EXPECTED_HANDOFF_PARAMETERS:
        errors.append(
            "finding handoff accepts authority beyond persisted identifiers: "
            f"{parameters}"
        )

    system_check_root = SOURCE / "core" / "system_check"
    for path in sorted(system_check_root.glob("*.py")):
        imports = _imports(path)
        if any(module.startswith("PyQt6") for module in imports):
            errors.append(
                f"PyQt import crossed into the System Check domain: "
                f"{path.relative_to(SOURCE)}"
            )

    return errors


def main() -> int:
    errors = validate()
    if errors:
        for error in errors:
            print(f"[system-check-contract] ERROR: {error}")
        return 1
    print(
        "[system-check-contract] OK: closed quick profile, timeout policy, "
        "finding mappings, handoff identifiers, and PyQt-free domain"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
