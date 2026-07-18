#!/usr/bin/env python3
"""Verify the six destinations and five workflows with core-only files."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SOURCE_ROOT = Path(
    os.environ.get("LOOFI_SOURCE_ROOT", ROOT / "loofi-fedora-tweaks")
).resolve()
if str(SOURCE_ROOT) not in sys.path:
    sys.path.insert(0, str(SOURCE_ROOT))

from core.navigation import destinations_for_mode  # noqa: E402
from core.navigation.models import (  # noqa: E402
    FedoraVariant,
    NavigationContext,
    NavigationDecision,
    NavigationMode,
)
from core.navigation.policy import NavigationPolicy  # noqa: E402
from core.plugins.components import discover_builtin_components  # noqa: E402
from core.plugins.spec import BUILTIN_PLUGIN_SPECS  # noqa: E402
from core.workflows import CORE_WORKFLOWS  # noqa: E402


def verify(source_root: Path = SOURCE_ROOT) -> dict[str, object]:
    """Return a no-probe component smoke result for release evidence."""
    errors: list[str] = []
    components = discover_builtin_components(source_root=source_root)
    if components != frozenset({"core"}):
        errors.append(f"expected core-only availability, got {sorted(components)}")

    context = NavigationContext(installed_components=components)
    destinations = destinations_for_mode(NavigationMode.STANDARD)
    if len(destinations) != 6:
        errors.append("exactly six Standard destinations are required")
    for destination in destinations:
        result = NavigationPolicy.evaluate(destination.default_route_id, context)
        if result.decision is NavigationDecision.UNAVAILABLE:
            errors.append(
                f"destination {destination.id} has unavailable default route"
            )

    if len(CORE_WORKFLOWS) != 5:
        errors.append("exactly five core workflows are required")
    for workflow in CORE_WORKFLOWS:
        result = NavigationPolicy.evaluate(workflow.preferred_route_id, context)
        if result.decision is NavigationDecision.UNAVAILABLE:
            errors.append(f"workflow {workflow.id} is unavailable in core")

    action_center_variants: dict[str, str] = {}
    for variant, capabilities in (
        (FedoraVariant.TRADITIONAL, frozenset({"dnf"})),
        (FedoraVariant.ATOMIC, frozenset({"rpm-ostree"})),
    ):
        result = NavigationPolicy.evaluate(
            "maintenance:action-center",
            NavigationContext(
                installed_components=components,
                fedora_variant=variant,
                capabilities=capabilities,
            ),
        )
        action_center_variants[variant.value] = result.decision.value
        if result.decision is not NavigationDecision.VISIBLE:
            errors.append(f"Action Center is not visible for {variant.value}")

    specialist_modules = {
        spec.module for spec in BUILTIN_PLUGIN_SPECS if spec.component == "specialist"
    }
    imported_specialist = sorted(specialist_modules.intersection(sys.modules))
    if imported_specialist:
        errors.append("specialist UI imported: " + ", ".join(imported_specialist))

    return {
        "schema_version": 1,
        "status": "passed" if not errors else "failed",
        "components": sorted(components),
        "standard_destinations": [destination.id for destination in destinations],
        "core_workflows": [workflow.id for workflow in CORE_WORKFLOWS],
        "action_center_variants": action_center_variants,
        "imported_specialist_modules": imported_specialist,
        "host_probes": 0,
        "mutations": 0,
        "errors": errors,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    payload = verify()
    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print(f"Core component verification: {payload['status']}")
        for error in payload["errors"]:
            print(f"- {error}")
    return 0 if payload["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
