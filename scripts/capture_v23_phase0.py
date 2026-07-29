#!/usr/bin/env python3
"""Capture and validate the Compass Phase 0 wide/compact UI baseline.

The real lazy ``MainWindow`` is rendered with an isolated HOME/XDG profile and
the existing Phase 0 subprocess guard. Raw frames are transient by default;
their hashes and six retained contact sheets form the durable evidence.
"""

from __future__ import annotations

import argparse
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Sequence

import capture_v16_phase0 as capture

ROOT = Path(__file__).resolve().parents[1]
OUTPUT_ROOT = ROOT / "docs" / "images" / "v23" / "phase0"
REPORT_PATH = ROOT / "docs" / "reports" / "V23_PHASE0_SCREENSHOTS.json"
CONTACT_SHEET_DIR = OUTPUT_ROOT / "contact-sheets"

SURFACES = (
    capture.DestinationCapture("home", "atlas_dashboard"),
    capture.DestinationCapture("troubleshoot", "diagnostics"),
    capture.DestinationCapture("system_check", "health"),
    capture.DestinationCapture("activity_recovery", "activity"),
    capture.DestinationCapture("action_center", "maintenance:action-center"),
    capture.DestinationCapture(
        "release_readiness",
        "maintenance:upgrade-assistant",
    ),
)
VIEWPORTS = (
    capture.ViewportScale(1366, 900, 100),
    capture.ViewportScale(860, 720, 100),
)
REPRODUCTION_COMMAND = (
    "PYTHONPATH=loofi-fedora-tweaks QT_QPA_PLATFORM=offscreen "
    "python3 scripts/capture_v23_phase0.py"
)


def _configure_capture() -> None:
    capture.OUTPUT_ROOT = OUTPUT_ROOT
    capture.REPORT_PATH = REPORT_PATH
    capture.RAW_DIR = OUTPUT_ROOT / "raw"
    capture.CONTACT_SHEET_DIR = CONTACT_SHEET_DIR
    capture.DESTINATIONS = SURFACES
    capture.VIEWPORT_SCALE_MATRIX = VIEWPORTS
    capture.BACKEND = "offscreen"
    capture.THEME = "system"


def _git_head() -> str:
    completed = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
        timeout=10,
    )
    return completed.stdout.strip()


def _write_manifest(
    frames: Sequence[dict[str, object]],
    contact_sheets: Sequence[dict[str, object]],
) -> dict[str, Any]:
    from version import __version__, __version_codename__

    payload: dict[str, Any] = {
        "schema_version": 1,
        "release": "v23.0.0 Compass",
        "phase": 0,
        "captured_product_version": __version__,
        "captured_product_codename": __version_codename__,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "git_commit": _git_head(),
        "status": "passed",
        "capture_policy": {
            "real_main_window": True,
            "navigation_mode": "standard",
            "backend": "offscreen",
            "theme": "system",
            "temporary_home_and_xdg": True,
            "background_services_disabled": True,
            "mutating_subprocesses_rejected": True,
            "asynchronous_commands_rejected": True,
            "raw_frames_retained": bool(frames and frames[0]["retained"]),
            "raw_storage": (
                "retained under docs/images/v23/phase0/raw"
                if frames and frames[0]["retained"]
                else "transient; hashes and contact sheets retained"
            ),
            "physical_gate": "not_verified",
        },
        "limitations": [
            "Offscreen Qt does not prove Wayland compositor behavior.",
            "Offscreen Qt does not prove Orca speech or the live AT-SPI tree.",
            "System theme rendering is evidence for this capture environment.",
        ],
        "reproduction_command": REPRODUCTION_COMMAND,
        "surfaces": [
            {
                "surface_id": surface.destination_id,
                "route_id": surface.route_id,
            }
            for surface in SURFACES
        ],
        "viewports": [
            {
                "width": viewport.width,
                "height": viewport.height,
                "font_scale_percent": viewport.scale_percent,
            }
            for viewport in VIEWPORTS
        ],
        "captures": list(frames),
        "contact_sheets": list(contact_sheets),
    }
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return payload


def validate_manifest() -> list[str]:
    errors: list[str] = []
    try:
        payload = json.loads(REPORT_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return [f"unable to read screenshot manifest: {exc}"]

    expected_routes = [surface.route_id for surface in SURFACES]
    actual_routes = [
        str(item.get("route_id", ""))
        for item in payload.get("surfaces", [])
        if isinstance(item, dict)
    ]
    if actual_routes != expected_routes:
        errors.append("screenshot surface routes drifted")
    if payload.get("captured_product_version") != "22.0.0":
        errors.append("Phase 0 screenshot evidence must capture product v22.0.0")
    if payload.get("phase") != 0 or payload.get("status") != "passed":
        errors.append("screenshot manifest is not a passed Phase 0 result")
    frames = payload.get("captures", [])
    if not isinstance(frames, list) or len(frames) != len(SURFACES) * len(VIEWPORTS):
        errors.append("screenshot manifest does not contain the full wide/compact matrix")
    sheets = payload.get("contact_sheets", [])
    if not isinstance(sheets, list) or len(sheets) != len(SURFACES):
        errors.append("screenshot manifest does not contain one sheet per surface")
    else:
        for item in sheets:
            if not isinstance(item, dict):
                errors.append("invalid contact-sheet record")
                continue
            path = ROOT / str(item.get("path", ""))
            if not path.is_file():
                errors.append(f"missing contact sheet: {path}")
                continue
            if capture.sha256_file(path) != item.get("sha256"):
                errors.append(f"contact-sheet digest drifted: {path}")
    return errors


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="validate the retained manifest and contact-sheet digests",
    )
    parser.add_argument(
        "--retain-raw",
        action="store_true",
        help="retain all 12 raw PNG frames",
    )
    parser.add_argument(
        "--settle-seconds",
        type=float,
        default=0.25,
        help="event-loop settling time before each capture",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    _configure_capture()
    if args.check:
        errors = validate_manifest()
        for error in errors:
            print(f"[v23-phase0-screenshots] ERROR: {error}")
        if not errors:
            print("[v23-phase0-screenshots] OK: 12 frames and 6 contact sheets")
        return 1 if errors else 0
    if args.settle_seconds < 0:
        raise ValueError("--settle-seconds must be non-negative")
    with capture.isolated_capture_home():
        frames, contact_sheets = capture.capture_matrix(
            retain_raw=args.retain_raw,
            settle_seconds=args.settle_seconds,
        )
        payload = _write_manifest(frames, contact_sheets)
    print(
        f"captured {len(payload['captures'])} Phase 0 frames and "
        f"{len(payload['contact_sheets'])} contact sheets"
    )
    print(REPORT_PATH.relative_to(ROOT))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
