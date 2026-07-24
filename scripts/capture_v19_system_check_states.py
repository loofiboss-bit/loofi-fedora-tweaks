#!/usr/bin/env python3
"""Capture deterministic v19 Home and System Check state evidence."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Sequence

ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT / "loofi-fedora-tweaks"
IMAGE_ROOT = ROOT / "docs" / "images" / "v19" / "phase6"
REPORT_PATH = ROOT / "docs" / "reports" / "V19_PHASE6_STATE_SCREENSHOTS.json"
sys.path.insert(0, str(SOURCE))

from PyQt6.QtWidgets import QApplication, QHBoxLayout, QLabel, QVBoxLayout, QWidget  # noqa: E402

from core.home import (  # noqa: E402
    HomeStatus,
    HomeSummary,
    HomeTask,
    Recommendation,
)
from core.system_check.comparison import (  # noqa: E402
    FindingOutcome,
    SystemCheckComparison,
)
from core.system_check.presentation import (  # noqa: E402
    FindingView,
    HistoryView,
    MaintenanceOutcomeView,
    SystemCheckPageState,
)
from ui.atlas_dashboard_tab import AtlasDashboardTab  # noqa: E402
from ui.design.theme_manager import ThemeManager  # noqa: E402
from ui.system_check_tab import SystemCheckTab  # noqa: E402

STATES = (
    "empty",
    "healthy",
    "partial",
    "actionable",
    "awaiting-reboot",
    "resolved",
)
CAPTURED_AT = datetime(2026, 7, 25, 10, 0, tzinfo=timezone.utc)


@dataclass(frozen=True)
class StateFixture:
    name: str
    home: HomeSummary
    system_check: SystemCheckPageState
    section: str


class _HomeService:
    def __init__(self, summary: HomeSummary):
        self._summary = summary

    def summary(self) -> HomeSummary:
        return self._summary


class _PresentationService:
    def __init__(self, state: SystemCheckPageState):
        self._state = state

    def load(self, *, history_limit: int = 30) -> SystemCheckPageState:
        return self._state


def _tasks() -> tuple[HomeTask, ...]:
    return (
        HomeTask("updates", "Update the system", "Review available Fedora updates.", "maintenance:updates", "updates"),
        HomeTask("apps", "Install an application", "Find Fedora and Flatpak apps.", "software:apps", "software"),
        HomeTask("performance", "Check performance", "Inspect current resource use.", "performance", "performance"),
        HomeTask("recovery", "Protect or recover", "Review recovery options.", "backup", "recovery"),
    )


def _statuses(
    health: str,
    *,
    updates: str = "unknown",
    storage: str = "unknown",
    recovery: str = "unknown",
) -> tuple[HomeStatus, ...]:
    values = (
        ("health", "System health", health, "health"),
        ("updates", "Updates", updates, "maintenance:updates"),
        ("storage", "Storage", storage, "maintenance:cleanup"),
        ("recovery", "Recovery protection", recovery, "backup"),
    )
    return tuple(
        HomeStatus(
            identifier,  # type: ignore[arg-type]
            title,
            state,  # type: ignore[arg-type]
            (
                "No saved status is available."
                if state == "unknown"
                else f"{title} is {state}."
            ),
            route,
        )
        for identifier, title, state, route in values
    )


def _home(
    *,
    overall: str,
    data_state: str,
    summary: str,
    recommendation: Recommendation,
    health: str,
    freshness: str,
    last_state: str | None = "completed",
    updates: str = "unknown",
    storage: str = "unknown",
    recovery: str = "unknown",
    source_errors: tuple[str, ...] = (),
) -> HomeSummary:
    return HomeSummary(
        overall_state=overall,  # type: ignore[arg-type]
        data_state=data_state,  # type: ignore[arg-type]
        summary=summary,
        generated_at=CAPTURED_AT,
        primary_recommendation=recommendation,
        attention_items=(),
        common_tasks=_tasks(),
        recent_change=None,
        source_errors=source_errors,
        status_items=_statuses(
            health,
            updates=updates,
            storage=storage,
            recovery=recovery,
        ),
        last_checked_at=None if data_state == "empty" else CAPTURED_AT,
        freshness_state=freshness,  # type: ignore[arg-type]
        last_check_state=last_state,  # type: ignore[arg-type]
    )


def _finding(
    *,
    finding_id: str,
    title: str,
    summary: str,
    action_id: str = "",
    manual_guidance: str = "",
    manual_reason_code: str = "",
) -> FindingView:
    return FindingView(
        finding_id,
        hashlib.sha256(finding_id.encode("utf-8")).hexdigest(),
        "maintenance",
        "attention",
        title,
        summary,
        "fresh",
        "maintenance:action-center" if action_id else "maintenance:updates",
        action_id,
        ("system",),
        manual_guidance,
        manual_reason_code,
        hashlib.sha256(summary.encode("utf-8")).hexdigest(),
    )


def _page(
    state: str,
    *,
    findings: tuple[FindingView, ...] = (),
    unavailable: tuple[str, ...] = (),
    comparison: SystemCheckComparison | None = None,
    outcomes: tuple[MaintenanceOutcomeView, ...] = (),
) -> SystemCheckPageState:
    completed = state != "unavailable"
    return SystemCheckPageState(
        latest_check_id=f"check-{state}" if completed else "",
        latest_state=state,
        latest_completed_at=CAPTURED_AT.timestamp() if completed else None,
        atomic=False if completed else None,
        findings=findings,
        history=(
            HistoryView(
                CAPTURED_AT.timestamp(),
                "system-check",
                state,
                f"check-{state}",
                len(findings),
                len(findings),
                0,
                0,
            ),
        ) if completed else (),
        metrics=(),
        unavailable_sources=unavailable,
        snapshot_error="",
        metric_error="",
        comparison=comparison,
        maintenance_outcomes=outcomes,
    )


def build_fixtures() -> tuple[StateFixture, ...]:
    actionable = _finding(
        finding_id="failed-service",
        title="Failed service",
        summary="demo.service needs review.",
        action_id="restart-failed-service",
    )
    awaiting = _finding(
        finding_id="pending-atomic-deployment",
        title="Reboot required",
        summary="An Atomic deployment is staged and waiting for an explicit reboot.",
        manual_guidance="Reboot when ready, then run System Check again.",
        manual_reason_code="pending-atomic-deployment",
    )
    original_fingerprint = hashlib.sha256(b"failed-service").hexdigest()
    comparison = SystemCheckComparison(
        "check-before",
        "check-completed",
        CAPTURED_AT.timestamp() - 3600,
        CAPTURED_AT.timestamp(),
        "system-check-quick-v1",
        False,
        True,
        "compatible",
        (
            FindingOutcome(
                "failed-service",
                original_fingerprint,
                "",
                "Failed service",
                "resolved",
                "finding_absent_after_compatible_check",
                ("systemd-unit:demo.service",),
            ),
        ),
    )
    resolved_outcome = MaintenanceOutcomeView(
        "run-verified",
        "plan-reviewed",
        "restart-failed-service",
        "check-before",
        original_fingerprint,
        "succeeded",
        "resolved",
        "finding_absent_after_compatible_check",
        False,
        ("systemd-unit:demo.service",),
        CAPTURED_AT.timestamp(),
    )

    return (
        StateFixture(
            "empty",
            _home(
                overall="attention",
                data_state="empty",
                summary="No saved status exists yet. Run a local System Check to create the first snapshot.",
                recommendation=Recommendation("first", "first_health_review", "Review system health", "Start the local read-only check.", "health"),
                health="unknown",
                freshness="unavailable",
                last_state=None,
            ),
            _page("unavailable"),
            "overview",
        ),
        StateFixture(
            "healthy",
            _home(
                overall="good",
                data_state="fresh",
                summary="The latest completed System Check has no current finding.",
                recommendation=Recommendation("healthy", "no_action", "No action needed", "Review details whenever useful.", "health", "info"),
                health="good",
                freshness="fresh",
                updates="good",
                storage="good",
                recovery="good",
            ),
            _page("completed"),
            "overview",
        ),
        StateFixture(
            "partial",
            _home(
                overall="attention",
                data_state="error",
                summary="The latest check completed partially. Available results remain visible.",
                recommendation=Recommendation("partial", "source_error", "Review unavailable source", "Retry explicitly when ready.", "health"),
                health="attention",
                freshness="fresh",
                last_state="partial",
                source_errors=("maintenance",),
            ),
            _page("partial", unavailable=("maintenance",)),
            "overview",
        ),
        StateFixture(
            "actionable",
            _home(
                overall="attention",
                data_state="fresh",
                summary="One current finding has a reviewed Action Center mapping.",
                recommendation=Recommendation("action", "system_check_finding", "Review failed service", "Open the exact audited action.", "health"),
                health="attention",
                freshness="fresh",
            ),
            _page("completed", findings=(actionable,)),
            "findings",
        ),
        StateFixture(
            "awaiting-reboot",
            _home(
                overall="attention",
                data_state="fresh",
                summary="A staged Atomic deployment is waiting for a user-controlled reboot.",
                recommendation=Recommendation("reboot", "pending_reboot", "Reboot when ready", "No automatic reboot will occur.", "health"),
                health="attention",
                freshness="fresh",
            ),
            _page("completed", findings=(awaiting,)),
            "findings",
        ),
        StateFixture(
            "resolved",
            _home(
                overall="good",
                data_state="fresh",
                summary="A later compatible check no longer contains the original finding.",
                recommendation=Recommendation("resolved", "no_action", "Finding resolved", "Action verification and finding resolution are recorded separately.", "health", "info"),
                health="good",
                freshness="fresh",
            ),
            _page(
                "completed",
                comparison=comparison,
                outcomes=(resolved_outcome,),
            ),
            "history",
        ),
    )


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def capture() -> dict[str, Any]:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    application = QApplication.instance() or QApplication(["loofi-v19-state-capture"])
    ThemeManager().apply(application, "system")
    IMAGE_ROOT.mkdir(parents=True, exist_ok=True)
    records: list[dict[str, Any]] = []

    for fixture in build_fixtures():
        surface = QWidget()
        surface.setAccessibleName(f"v19 {fixture.name} state evidence")
        root = QVBoxLayout(surface)
        heading = QLabel(f"Steward state evidence: {fixture.name.replace('-', ' ').title()}")
        heading.setObjectName("evidenceHeading")
        root.addWidget(heading)
        columns = QHBoxLayout()
        home = AtlasDashboardTab(home_service=_HomeService(fixture.home))
        system_check = SystemCheckTab(
            presentation_service=_PresentationService(fixture.system_check)
        )
        system_check.select_section(fixture.section)
        columns.addWidget(home, 1)
        columns.addWidget(system_check, 1)
        root.addLayout(columns, 1)
        surface.resize(1600, 900)
        surface.show()
        for _ in range(8):
            application.processEvents()
        image_path = IMAGE_ROOT / f"{fixture.name}.png"
        if not surface.grab().save(str(image_path), "PNG"):
            raise RuntimeError(f"Could not save {image_path}")
        records.append(
            {
                "state": fixture.name,
                "home_real_widget": True,
                "system_check_real_widget": True,
                "system_check_section": fixture.section,
                "width": surface.width(),
                "height": surface.height(),
                "sha256": _sha256(image_path),
                "path": str(image_path.relative_to(ROOT)),
            }
        )
        surface.close()
        surface.deleteLater()
        application.processEvents()

    payload = {
        "schema_version": 1,
        "release": "v19 Steward working tree (metadata v18.0.0 Haven)",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "backend": application.platformName(),
        "fixture_timestamp": CAPTURED_AT.isoformat(),
        "states": records,
        "status": "passed" if {item["state"] for item in records} == set(STATES) else "failed",
    }
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return payload


def validate() -> list[str]:
    errors: list[str] = []
    if not REPORT_PATH.exists():
        return ["state screenshot manifest is missing"]
    try:
        payload = json.loads(REPORT_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return [f"state screenshot manifest is unreadable: {exc}"]
    records = payload.get("states", [])
    if not isinstance(records, list):
        return ["state screenshot records are not a list"]
    if {record.get("state") for record in records if isinstance(record, dict)} != set(STATES):
        errors.append("state screenshot manifest does not cover all six required states")
    for record in records:
        if not isinstance(record, dict):
            errors.append("state screenshot record is malformed")
            continue
        path = ROOT / str(record.get("path", ""))
        if not path.is_file():
            errors.append(f"state screenshot is missing: {path}")
        elif _sha256(path) != record.get("sha256"):
            errors.append(f"state screenshot checksum changed: {path}")
        if (
            not isinstance(record.get("width"), int)
            or not 1200 <= record["width"] <= 2000
            or not isinstance(record.get("height"), int)
            or not 650 <= record["height"] <= 1200
        ):
            errors.append(f"state screenshot dimensions changed: {path}")
        if not record.get("home_real_widget") or not record.get("system_check_real_widget"):
            errors.append(f"state screenshot does not use both real widgets: {path}")
    return errors


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    errors = validate() if args.check else ([] if capture()["status"] == "passed" else ["capture failed"])
    if errors:
        for error in errors:
            print(f"[v19-state-screenshots] ERROR: {error}")
        return 1
    print("[v19-state-screenshots] OK: empty, healthy, partial, actionable, awaiting-reboot, and resolved")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
