"""Canonical System Check presentation and UI compatibility contracts."""

from __future__ import annotations

import sqlite3
import tempfile
import unittest
from pathlib import Path

from PyQt6.QtWidgets import QApplication, QLabel, QWidget

from core.navigation import resolve
from core.observability.fingerprints import ProblemFingerprint
from core.observability.snapshot import HealthSnapshot
from core.observability.timeline import HealthTimelineStore
from core.system_check.models import FindingEvidence, SystemCheckResult, SystemFinding
from core.system_check.presentation import (
    FindingView,
    HistoryView,
    MetricView,
    SystemCheckPageState,
    SystemCheckPresentationService,
)
from ui.components import LocalViewSwitcher, SectionNavigator
from ui.system_check_tab import SystemCheckTab


def _legacy_snapshot(timestamp: float, fingerprint: str) -> HealthSnapshot:
    problem = ProblemFingerprint(
        fingerprint,
        "failed-service",
        "Failed service",
        "A service needs review.",
        "failed-services",
    )
    return HealthSnapshot(
        timestamp=timestamp,
        app_version="18.0.0",
        app_codename="Haven",
        fedora_target="44",
        atomic=False,
        daily_maintenance={"cards": []},
        action_center_summary={"candidate_count": 0},
        problem_fingerprints=[problem],
    )


def _system_check_snapshot(timestamp: float) -> HealthSnapshot:
    finding = SystemFinding.build(
        finding_id="package-state",
        category="packages",
        severity="attention",
        title="Package state needs review",
        summary="A saved package signal needs review.",
        evidence=FindingEvidence.from_mapping(
            "package-state",
            {"status": "attention"},
            collected_at=timestamp,
        ),
        applicable_variants=frozenset({"traditional", "atomic"}),
        freshness_state="fresh",
        route_id="maintenance:updates",
    )
    result = SystemCheckResult(
        "check-1",
        "system-check-quick-v1",
        "completed",
        False,
        timestamp - 1,
        timestamp,
        findings=(finding,),
    )
    return HealthSnapshot.from_system_check(result)


class TestSystemCheckPresentation(unittest.TestCase):
    def test_both_existing_stores_are_visible_without_metric_mutation(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            snapshot_store = HealthTimelineStore(root / "health.json")
            snapshot_store.save([
                _legacy_snapshot(10.0, "legacy-finding"),
                _system_check_snapshot(20.0),
            ])
            metric_path = root / "metrics.db"
            with sqlite3.connect(metric_path) as connection:
                connection.execute(
                    """
                    CREATE TABLE metrics (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        timestamp TEXT NOT NULL,
                        metric_type TEXT NOT NULL,
                        value REAL NOT NULL,
                        unit TEXT DEFAULT '',
                        metadata TEXT DEFAULT ''
                    )
                    """
                )
                connection.executemany(
                    "INSERT INTO metrics (timestamp, metric_type, value, unit) VALUES (?, ?, ?, ?)",
                    [
                        ("2026-07-24T10:00:00", "ram_usage", 40.0, "%"),
                        ("2026-07-24T11:00:00", "ram_usage", 60.0, "%"),
                    ],
                )

            state = SystemCheckPresentationService(
                snapshot_store=snapshot_store,
                metric_path=metric_path,
            ).load()

            self.assertEqual(state.latest_check_id, "check-1")
            self.assertEqual(len(state.findings), 1)
            self.assertEqual(
                [item.source for item in state.history],
                ["system-check", "health-snapshot"],
            )
            self.assertEqual(state.history[0].new_count, 1)
            self.assertEqual(state.history[0].resolved_count, 1)
            self.assertEqual(state.metrics[0].metric_type, "ram_usage")
            self.assertEqual(state.metrics[0].average, 50.0)

    def test_missing_metric_store_is_not_created(self):
        with tempfile.TemporaryDirectory() as directory:
            metric_path = Path(directory) / "missing" / "metrics.db"
            state = SystemCheckPresentationService(
                snapshot_store=HealthTimelineStore(Path(directory) / "missing.json"),
                metric_path=metric_path,
            ).load()

            self.assertEqual(state.metrics, ())
            self.assertEqual(state.metric_error, "")
            self.assertFalse(metric_path.exists())


class _PresentationFixture:
    def __init__(self, state: SystemCheckPageState):
        self.state = state
        self.calls: list[int] = []

    def load(self, *, history_limit: int = 30) -> SystemCheckPageState:
        self.calls.append(history_limit)
        return self.state


class TestSystemCheckTab(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        state = SystemCheckPageState(
            latest_check_id="check-1",
            latest_state="completed",
            latest_completed_at=20.0,
            atomic=False,
            findings=(
                FindingView(
                    "package-state",
                    "fingerprint-1",
                    "packages",
                    "attention",
                    "Package state needs review",
                    "Review the saved signal.",
                    "fresh",
                    "maintenance:updates",
                    "",
                    (),
                ),
            ),
            history=(
                HistoryView(20.0, "system-check", "completed", "check-1", 1, 1, 0, 0),
                HistoryView(10.0, "health-snapshot", "recorded", "", 1, 1, 0, 0),
            ),
            metrics=(
                MetricView("ram_usage", 40.0, 60.0, 50.0, 2, "%", "2026-07-24T11:00:00"),
            ),
            unavailable_sources=(),
            snapshot_error="",
            metric_error="",
        )
        self.service = _PresentationFixture(state)
        self.tab = SystemCheckTab(presentation_service=self.service)
        self.addCleanup(self.tab.deleteLater)

    def test_one_page_has_three_views_and_no_record_snapshot_action(self):
        self.assertIsInstance(self.tab.view_switcher, LocalViewSwitcher)
        self.assertEqual(
            self.tab.view_switcher.view_ids(),
            ("overview", "findings", "history"),
        )
        self.assertEqual(self.tab.findChildren(SectionNavigator), [])
        self.assertEqual(len(self.tab.findChildren(QWidget, "systemCheckFinding")), 1)
        labels = " ".join(label.text() for label in self.tab.findChildren(QLabel))
        self.assertIn("A finding is an explained issue", labels)
        self.assertIn("Updates", labels)
        self.assertNotIn("maintenance:updates", labels)
        self.assertNotIn("Record Snapshot", labels)
        self.assertFalse(self.tab.metric_disclosure.toggle_button.isChecked())
        self.assertFalse(self.tab.metric_disclosure.details.isVisible())

    def test_stable_routes_preselect_the_canonical_view(self):
        self.assertTrue(self.tab.activate_route(resolve("health")))
        self.assertEqual(self.tab.view_switcher.active_view_id(), "overview")
        self.assertTrue(self.tab.activate_route(resolve("maintenance:health-timeline")))
        self.assertEqual(self.tab.view_switcher.active_view_id(), "history")


if __name__ == "__main__":
    unittest.main()
