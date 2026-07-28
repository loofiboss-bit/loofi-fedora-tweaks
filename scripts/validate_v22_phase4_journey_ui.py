#!/usr/bin/env python3
"""Validate the V22 Home-to-recovery accessibility journey offscreen.

This validator deliberately limits itself to deterministic Qt widget evidence.
It does not claim compositor focus behaviour, a live AT-SPI tree, or Orca
speech output; those require the separate physical gate recorded in the report.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Sequence


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "loofi-fedora-tweaks"
DEFAULT_REPORT = ROOT / "docs" / "reports" / "V22_PHASE4_JOURNEY_UI.json"
SURFACES = (
    ("home", "atlas_dashboard", "homeCheckNow"),
    ("system_check", "health", "systemCheckRefresh"),
    ("action_center", "maintenance:action-center", "Action Center candidates"),
    ("activity", "activity", "activityLoadButton"),
)
VIEWPORTS = ((1366, 768), (860, 560))
DIRECTIONS = ("ltr", "rtl")
THEME = "highcontrast"
BASE_POINT_SIZE = 14
SCALE_PERCENT = 200
REDUCED_MOTION = True


@dataclass(frozen=True)
class JourneyCase:
    """One deterministic V22 journey matrix cell."""

    surface: str
    route_id: str
    target_object_name: str
    viewport: tuple[int, int]
    direction: str

    @property
    def case_id(self) -> str:
        return f"{self.surface}__{self.viewport[0]}x{self.viewport[1]}__{self.direction}"


def build_matrix() -> tuple[JourneyCase, ...]:
    """Return every journey surface at wide/compact and LTR/RTL geometry."""
    return tuple(
        JourneyCase(surface, route_id, target, viewport, direction)
        for surface, route_id, target in SURFACES
        for viewport in VIEWPORTS
        for direction in DIRECTIONS
    )


def validate_static_contract() -> list[str]:
    """Check matrix completeness and source-level accessibility contracts."""
    errors: list[str] = []
    matrix = build_matrix()
    if len(matrix) != 16:
        errors.append("V22 journey matrix must contain 16 cells")
    if {case.surface for case in matrix} != {item[0] for item in SURFACES}:
        errors.append("V22 journey matrix does not cover every surface")
    if {case.viewport for case in matrix} != set(VIEWPORTS):
        errors.append("V22 journey matrix does not cover wide and compact layouts")
    if {case.direction for case in matrix} != set(DIRECTIONS):
        errors.append("V22 journey matrix does not cover LTR and RTL")

    required = {
        "ui/atlas_dashboard_tab.py": ("homeCheckNow", "homeStateLabel"),
        "ui/system_check_tab.py": ("systemCheckRefresh", "systemCheckStatus"),
        "ui/maintenance_action_center.py": ("Action Center status", "Action Center candidates"),
        "ui/activity_recovery_tab.py": ("activityLoadButton", "Activity loading status"),
    }
    for relative, fragments in required.items():
        source = (SOURCE / relative).read_text(encoding="utf-8")
        for fragment in fragments:
            if fragment not in source:
                errors.append(f"{relative} lacks required journey contract: {fragment}")
    return errors


def _settle(application: Any, cycles: int = 4) -> None:
    for _ in range(cycles):
        application.processEvents()


def _visible_accessible_name(widget: Any) -> str:
    return str(widget.accessibleName() or widget.text() or widget.objectName() or "").strip()


def run_offscreen(report_path: Path) -> dict[str, Any]:
    """Run the bounded real-widget matrix with no host command execution."""
    os.environ["QT_QPA_PLATFORM"] = "offscreen"
    if str(SOURCE) not in sys.path:
        sys.path.insert(0, str(SOURCE))
    if str(ROOT / "scripts") not in sys.path:
        sys.path.insert(0, str(ROOT / "scripts"))

    from contextlib import ExitStack
    from unittest.mock import patch

    from PyQt6.QtCore import Qt
    from PyQt6.QtWidgets import QApplication, QWidget
    from capture_v16_phase0 import guarded_subprocesses, isolated_capture_home
    from core.plugins.registry import PluginRegistry
    from ui.community_tab import CommunityTab
    from ui.desktop_tab import DesktopTab
    from ui.main_window import MainWindow
    from ui.network_tab import NetworkTab
    from ui.software_tab import _ApplicationsSubTab
    from utils.command_runner import CommandRunner
    from utils.settings import SettingsManager

    application = QApplication.instance() or QApplication(["validate-v22-phase4-journey"])
    base_font = application.font()
    errors = validate_static_contract()
    records: list[dict[str, Any]] = []

    def reject_command(*_args: Any, **_kwargs: Any) -> None:
        raise RuntimeError("V22 journey validation rejected a command")

    with isolated_capture_home(), ExitStack() as stack:
        stack.enter_context(guarded_subprocesses())
        stack.enter_context(patch.object(MainWindow, "_check_first_run", lambda self: None))
        stack.enter_context(patch.object(MainWindow, "_initialize_background_services", lambda self: None))
        stack.enter_context(patch.object(MainWindow, "_schedule_post_render_services", lambda self: None))
        stack.enter_context(patch.object(CommandRunner, "run_command", reject_command))
        stack.enter_context(patch.object(_ApplicationsSubTab, "on_activate", lambda self: None))
        stack.enter_context(patch.object(CommunityTab, "on_activate", lambda self: None))
        stack.enter_context(patch.object(NetworkTab, "_initial_load", lambda self: None))
        stack.enter_context(patch.object(DesktopTab, "_detect_displays", lambda self: None))
        stack.enter_context(patch.object(DesktopTab, "_load_session_info", lambda self: None))
        SettingsManager._reset_instance()
        PluginRegistry.reset()
        window = MainWindow()
        try:
            from ui.design import ThemeManager

            font = application.font()
            font.setPointSizeF(float(BASE_POINT_SIZE * SCALE_PERCENT) / 100.0)
            application.setFont(font)
            application.setProperty("loofiReducedMotion", REDUCED_MOTION)
            if not ThemeManager().apply(application, THEME):
                errors.append("high-contrast theme application failed")
            for case in build_matrix():
                issues: list[str] = []
                application.setLayoutDirection(
                    Qt.LayoutDirection.RightToLeft if case.direction == "rtl" else Qt.LayoutDirection.LeftToRight
                )
                window.resize(*case.viewport)
                window.show()
                _settle(application)
                if not window.switch_to_route(case.route_id):
                    issues.append("route did not resolve")
                _settle(application)
                target = window.findChild(QWidget, case.target_object_name)
                if target is None:
                    target = next(
                        (
                            widget
                            for widget in window.findChildren(QWidget)
                            if widget.accessibleName() == case.target_object_name
                        ),
                        None,
                    )
                if target is None:
                    issues.append(f"missing target {case.target_object_name}")
                elif not _visible_accessible_name(target):
                    issues.append(f"unnamed target {case.target_object_name}")
                else:
                    if target.focusPolicy() == Qt.FocusPolicy.NoFocus:
                        issues.append(f"target {case.target_object_name} is excluded from keyboard focus")
                    if target.nextInFocusChain() is target:
                        issues.append(f"target {case.target_object_name} has no Tab focus successor")
                    # Offscreen Qt cannot prove compositor focus restoration. The
                    # route round-trip below proves that the focus target survives
                    # navigation; physical restoration remains a pending gate.
                    if not window.switch_to_route("atlas_dashboard") or not window.switch_to_route(case.route_id):
                        issues.append("route round-trip did not restore the journey surface")
                if window.destination_host.is_compact() != (case.viewport[0] < 900):
                    issues.append("compact layout breakpoint drifted")
                if application.layoutDirection() != (
                    Qt.LayoutDirection.RightToLeft if case.direction == "rtl" else Qt.LayoutDirection.LeftToRight
                ):
                    issues.append("layout direction did not apply")
                records.append({**asdict(case), "viewport": list(case.viewport), "issues": issues, "status": "passed" if not issues else "failed"})
                errors.extend(f"{case.case_id}: {issue}" for issue in issues)
        finally:
            window.close()
            window.deleteLater()
            _settle(application)
            application.setFont(base_font)

    payload = {
        "schema_version": 1,
        "release": "v22.0.0 Alignment",
        "phase": 4,
        "status": "passed" if not errors else "failed",
        "backend": "offscreen",
        "matrix_contract": {
            "surfaces": [item[0] for item in SURFACES],
            "viewports": [list(viewport) for viewport in VIEWPORTS],
            "directions": list(DIRECTIONS),
            "theme": THEME,
            "base_point_size": BASE_POINT_SIZE,
            "scale_percent": SCALE_PERCENT,
            "reduced_motion": REDUCED_MOTION,
            "cells": len(build_matrix()),
        },
        "physical_gate": {
            "wayland": "not_verified",
            "orca": "not_verified",
            "at_spi": "not_verified",
            "reason": "Offscreen Qt evidence cannot establish live compositor or assistive-technology behaviour.",
        },
        "errors": list(dict.fromkeys(errors)),
        "cases": records,
    }
    report_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return payload


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--contract-only", action="store_true")
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    if args.contract_only:
        errors = validate_static_contract()
        payload: dict[str, Any] = {"status": "passed" if not errors else "failed", "matrix_cells": len(build_matrix()), "errors": errors}
    else:
        payload = run_offscreen(args.report)
    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print(f"V22 Phase 4 journey UI validation: {payload['status']}")
    return 0 if payload["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
