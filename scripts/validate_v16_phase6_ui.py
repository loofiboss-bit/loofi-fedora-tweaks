#!/usr/bin/env python3
"""Validate v16 Phase 6 Advanced UI consolidation without host probes."""

from __future__ import annotations

import argparse
import ast
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "loofi-fedora-tweaks"
if str(SOURCE) not in sys.path:
    sys.path.insert(0, str(SOURCE))

from core.navigation import (  # noqa: E402
    all_routes,
    placement_for_route,
    sections_for_destination,
    validate_destinations,
)


ADVANCED_PAGE_FILES = (
    "performance_tab.py",
    "gaming_tab.py",
    "development_tab.py",
    "profiles_tab.py",
    "extensions_tab.py",
    "community_tab.py",
    "mesh_tab.py",
    "ai_enhanced_tab.py",
    "agents_tab.py",
    "automation_tab.py",
    "teleport_tab.py",
    "virtualization_tab.py",
)

ROUTED_PAGE_FILES = (
    "development_tab.py",
    "community_tab.py",
    "mesh_tab.py",
    "ai_enhanced_tab.py",
    "agents_tab.py",
    "automation_tab.py",
    "virtualization_tab.py",
)

LEGACY_THEME_FILES = ("modern.qss", "light.qss", "highcontrast.qss")


def _constructor_count(path: Path, name: str) -> int:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    return sum(
        1
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == name
    )


def _method_call_count(path: Path, name: str) -> int:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    return sum(
        1
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == name
    )


def validate() -> list[str]:
    """Return static contract errors without importing PyQt or probing the host."""
    errors = list(validate_destinations())
    ui_root = SOURCE / "ui"

    routes = all_routes()
    advanced_routes = [
        route
        for route in routes
        if (placement := placement_for_route(route.id)) is not None
        and placement.destination_id == "advanced"
    ]
    advanced_sections = sections_for_destination("advanced")
    if len(routes) != 81:
        errors.append("the stable route inventory changed")
    if len(advanced_routes) != 33:
        errors.append("the Advanced route inventory changed")
    if len(advanced_sections) != 26:
        errors.append("Advanced must expose 26 shell-owned route sections")

    stale_version = re.compile(r"Part of v\d|v\d+(?:\.\d+)* compatibility|SUB-TAB \(v\d")
    for filename in ADVANCED_PAGE_FILES:
        source = (ui_root / filename).read_text(encoding="utf-8")
        if "PageScaffold(" not in source:
            errors.append(f"Advanced page is not scaffolded: {filename}")
        if stale_version.search(source):
            errors.append(f"stale version comment remains: {filename}")

    for filename in ROUTED_PAGE_FILES:
        source = (ui_root / filename).read_text(encoding="utf-8")
        if "QStackedWidget" not in source or "def activate_route" not in source:
            errors.append(f"route stack contract missing: {filename}")

    qtab_count = sum(
        _constructor_count(ui_root / filename, "QTabWidget")
        for filename in ADVANCED_PAGE_FILES
    )
    local_tab_count = sum(
        _method_call_count(ui_root / filename, "addTab")
        for filename in ADVANCED_PAGE_FILES
    )
    if qtab_count != 0 or local_tab_count != 0:
        errors.append("Advanced pages must use shell-owned sections without nested tabs")

    assets_root = SOURCE / "assets"
    for filename in LEGACY_THEME_FILES:
        if (assets_root / filename).exists():
            errors.append(f"legacy theme file remains: {filename}")
    if "QLabel#sectionTitle" in (assets_root / "base.qss").read_text(encoding="utf-8"):
        errors.append("dead sectionTitle selector remains")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    errors = validate()
    payload = {
        "phase": 6,
        "advanced_pages": len(ADVANCED_PAGE_FILES),
        "advanced_routes": 33,
        "advanced_sections": 26,
        "application_navigation_qtabwidgets": 0,
        "local_qtabwidgets": 0,
        "local_tab_views": 0,
        "host_probes": 0,
        "mutations": 0,
        "status": "passed" if not errors else "failed",
        "errors": errors,
    }
    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print(f"v16 Phase 6 UI validation: {payload['status']}")
        for error in errors:
            print(f"- {error}")
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
