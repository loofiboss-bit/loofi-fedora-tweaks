#!/usr/bin/env python3
"""Validate Resolve Phase 3 supporting surfaces and accessibility."""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Sequence, cast


ROOT = Path(__file__).resolve().parents[1]
LEGACY_VALIDATOR = ROOT / "scripts" / "validate_v16_phase7_ui.py"
DEFAULT_REPORT = ROOT / "docs" / "reports" / "V21_PHASE3_UI_AUTOMATED.json"

THEMES = ("system", "dark", "light", "highcontrast")
VIEWPORTS = ((860, 560), (900, 720), (1366, 768), (1920, 1080))
FONT_SCALES = (100, 125, 150, 200)
DIRECTIONS = ("ltr", "rtl")
ROUTES = ("settings", "development")


@dataclass(frozen=True)
class Phase3Case:
    """One supporting-surface matrix cell."""

    theme: str
    navigation_mode: str
    viewport: tuple[int, int]
    scale_percent: int
    locale_fixture: str
    route_id: str
    direction: str

    @property
    def case_id(self) -> str:
        width, height = self.viewport
        return (
            f"{self.theme}__{width}x{height}__scale-{self.scale_percent:03d}"
            f"__{self.direction}__{self.route_id}"
        )


def build_matrix() -> tuple[Phase3Case, ...]:
    """Return the complete theme, geometry, scale, direction, and route product."""
    return tuple(
        Phase3Case(
            theme=theme,
            navigation_mode=(
                "advanced" if route_id == "development" else "standard"
            ),
            viewport=viewport,
            scale_percent=scale,
            locale_fixture="en",
            route_id=route_id,
            direction=direction,
        )
        for theme in THEMES
        for viewport in VIEWPORTS
        for scale in FONT_SCALES
        for direction in DIRECTIONS
        for route_id in ROUTES
    )


def _load_legacy_validator() -> Any:
    spec = importlib.util.spec_from_file_location(
        "v21_phase3_legacy_validator",
        LEGACY_VALIDATOR,
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("Unable to load the shared UI validation harness")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def validate_static_contract() -> list[str]:
    """Return matrix and inherited shell-contract errors."""
    errors: list[str] = []
    matrix = build_matrix()
    if len(matrix) != 256:
        errors.append("Phase 3 matrix must contain 256 cells")
    if {case.theme for case in matrix} != set(THEMES):
        errors.append("Phase 3 matrix does not cover every theme")
    if {case.viewport for case in matrix} != set(VIEWPORTS):
        errors.append("Phase 3 matrix does not cover every required viewport")
    if {case.scale_percent for case in matrix} != set(FONT_SCALES):
        errors.append("Phase 3 matrix does not cover every required text scale")
    if {case.direction for case in matrix} != set(DIRECTIONS):
        errors.append("Phase 3 matrix does not cover both layout directions")
    if {case.route_id for case in matrix} != set(ROUTES):
        errors.append("Phase 3 matrix does not cover both supporting surfaces")
    errors.extend(_load_legacy_validator().validate_static_contract())
    return list(dict.fromkeys(errors))


def _supporting_surface_issues(
    application: Any,
    window: Any,
    case: Phase3Case,
) -> list[str]:
    from PyQt6.QtCore import Qt
    from ui.components.settings import SettingRow

    expected_direction = (
        Qt.LayoutDirection.RightToLeft
        if case.direction == "rtl"
        else Qt.LayoutDirection.LeftToRight
    )
    issues: list[str] = []
    if application.layoutDirection() is not expected_direction:
        issues.append("application layout direction did not apply")

    if case.route_id == "development":
        navigator = window.destination_host.navigator
        if not navigator.filtering_enabled():
            issues.append("Specialist Tools local filtering is not enabled")
        if not navigator.filter_input.accessibleName():
            issues.append("Specialist Tools filter has no accessible name")
        if len(navigator.available_groups()) < 6:
            issues.append("Specialist Tools are not grouped")
        original_ids = navigator.section_ids()
        navigator.filter_input.setText("virtual")
        application.processEvents()
        if not navigator.visible_section_ids():
            issues.append("Specialist Tools local filter returned no matching route")
        if navigator.section_ids() != original_ids:
            issues.append("Specialist Tools filter changed canonical route identity")
        navigator.filter_input.clear()
        application.processEvents()
        for index in range(navigator.selector.count()):
            if not navigator.selector.itemText(index):
                issues.append("Specialist Tools selector has an empty route label")
            if not navigator.selector.itemData(index, Qt.ItemDataRole.ToolTipRole):
                issues.append("Specialist Tools selector has a missing tooltip")
    else:
        entry = window._sidebar_index.get("settings")
        widget = window._real_widget_for_entry(entry) if entry is not None else None
        rows = widget.findChildren(SettingRow) if widget is not None else []
        if len(rows) < 8:
            issues.append("Settings does not use consistent rows")
        for row in rows:
            if not row.accessibleName() or not row.accessibleDescription():
                issues.append("Settings row accessibility metadata is incomplete")
        theme_row = next(
            (
                row
                for row in rows
                if row.accessibleName() == "Theme"
            ),
            None,
        )
        follow_system_control = getattr(widget, "follow_system_cb", None)
        original_follow_system = bool(
            follow_system_control
            and follow_system_control.isChecked()
        )
        if follow_system_control is not None:
            follow_system_control.setChecked(True)
            application.processEvents()
        if theme_row is None or not theme_row.feedback_label.text().startswith(
            "Unavailable —"
        ):
            issues.append("Settings theme dependency feedback is missing")
        if follow_system_control is not None:
            follow_system_control.setChecked(original_follow_system)
            application.processEvents()
    return list(dict.fromkeys(issues))


def run_validation(*, backend: str, report_path: Path) -> dict[str, Any]:
    """Run the safe real-window matrix through the established harness."""
    os.environ["QT_QPA_PLATFORM"] = backend
    legacy = _load_legacy_validator()
    static_errors = validate_static_contract()
    original_apply = legacy._apply_case

    def apply_case(application, window, case, base_point_size):
        from PyQt6.QtCore import Qt

        application.setLayoutDirection(
            Qt.LayoutDirection.RightToLeft
            if case.direction == "rtl"
            else Qt.LayoutDirection.LeftToRight
        )
        issues = original_apply(
            application,
            window,
            case,
            base_point_size,
        )
        issues.extend(_supporting_surface_issues(application, window, case))
        return list(dict.fromkeys(issues))

    legacy.build_automated_matrix = build_matrix
    legacy.validate_static_contract = lambda: list(static_errors)
    legacy._apply_case = apply_case
    payload = cast(dict[str, Any], legacy.run_validation(
        scope="automated",
        backend=backend,
        report_path=report_path,
        capture_catalog=False,
        compositor_scale=None,
    ))
    payload["release"] = "v21.0.0 Resolve"
    payload["phase"] = 3
    payload["matrix_contract"] = {
        "themes": list(THEMES),
        "viewports": [list(viewport) for viewport in VIEWPORTS],
        "font_scales": list(FONT_SCALES),
        "directions": list(DIRECTIONS),
        "routes": list(ROUTES),
        "complete_cells": len(build_matrix()),
        "executed_cells": len(payload.get("cases", ())),
        "real_main_window": True,
    }
    report_path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return payload


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--backend",
        choices=("offscreen", "wayland", "xcb"),
        default="offscreen",
    )
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--contract-only", action="store_true")
    parser.add_argument("--json", action="store_true")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    if args.contract_only:
        errors = validate_static_contract()
        payload = {
            "release": "v21.0.0 Resolve",
            "phase": 3,
            "matrix_cells": len(build_matrix()),
            "status": "passed" if not errors else "failed",
            "errors": errors,
        }
    else:
        payload = run_validation(backend=args.backend, report_path=args.report)
    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print(
            f"V21 Phase 3 UI validation: {payload['status']} "
            f"({len(cast(Sequence[object], payload.get('errors', ())))} issue(s))"
        )
        if not args.contract_only:
            print(f"Report: {args.report}")
    return 0 if payload["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
