"""Persisted finding resolution and System Check UI handoff contracts."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

from PyQt6.QtWidgets import QApplication, QPushButton

from core.observability.snapshot import HealthSnapshot
from core.observability.timeline import HealthTimelineStore
from core.system_check.handoff import FindingActionHandoff, FindingHandoffError
from core.system_check.models import FindingEvidence, SystemCheckResult, SystemFinding
from core.system_check.presentation import (
    FindingView,
    SystemCheckPageState,
    SystemCheckPresentationService,
)
from ui.system_check_tab import SystemCheckTab
from ui.main_window import MainWindow
from ui.maintenance_action_center import _ActionCenterSubTab


def _finding(
    *,
    service: str = "demo.service",
    freshness: str = "fresh",
) -> SystemFinding:
    return SystemFinding.build(
        finding_id="failed-service",
        category="services",
        severity="attention",
        title="Failed service",
        summary=f"{service} needs review.",
        evidence=FindingEvidence.from_mapping(
            "failed-services",
            {"service": service, "state": "failed"},
            collected_at=10.0,
        ),
        applicable_variants=frozenset({"traditional", "atomic"}),
        freshness_state=freshness,  # type: ignore[arg-type]
        affected_resources=(f"systemd-unit:{service}",),
        action_id="restart-failed-service",
        action_parameters={"service": service},
    )


def _snapshot(
    check_id: str,
    finding: SystemFinding,
    *,
    completed_at: float,
) -> HealthSnapshot:
    return HealthSnapshot.from_system_check(
        SystemCheckResult(
            check_id,
            "system-check-quick-v1",
            "completed",
            False,
            completed_at - 1,
            completed_at,
            findings=(finding,),
        )
    )


class TestFindingActionHandoff(unittest.TestCase):
    def test_latest_fresh_finding_resolves_exact_mapping_and_context(self):
        with tempfile.TemporaryDirectory() as directory:
            finding = _finding()
            store = HealthTimelineStore(Path(directory) / "health.json")
            store.save([_snapshot("check-1", finding, completed_at=20.0)])

            review = FindingActionHandoff(snapshot_store=store).resolve(
                check_result_id="check-1",
                finding_fingerprint=finding.fingerprint,
                origin_route="health",
            )

            self.assertEqual(review.action_id, "restart-failed-service")
            self.assertEqual(review.parameters_dict(), {"service": "demo.service"})
            self.assertEqual(review.context.check_result_id, "check-1")
            self.assertEqual(
                review.context.affected_resources,
                ("systemd-unit:demo.service",),
            )
            self.assertEqual(len(review.context.evidence_digest), 64)

    def test_old_check_and_stale_evidence_fail_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            old = _finding(service="old.service")
            latest = _finding(service="latest.service")
            store = HealthTimelineStore(Path(directory) / "health.json")
            store.save([
                _snapshot("check-old", old, completed_at=10.0),
                _snapshot("check-latest", latest, completed_at=20.0),
            ])

            with self.assertRaises(FindingHandoffError) as stale_check:
                FindingActionHandoff(snapshot_store=store).resolve(
                    check_result_id="check-old",
                    finding_fingerprint=old.fingerprint,
                    origin_route="health",
                )
            self.assertEqual(stale_check.exception.reason_code, "stale_finding_context")

            stale = _finding(freshness="stale")
            store.save([_snapshot("check-stale", stale, completed_at=30.0)])
            with self.assertRaises(FindingHandoffError) as stale_evidence:
                FindingActionHandoff(snapshot_store=store).resolve(
                    check_result_id="check-stale",
                    finding_fingerprint=stale.fingerprint,
                    origin_route="health",
                )
            self.assertEqual(stale_evidence.exception.reason_code, "stale_finding_context")

    def test_tampered_evidence_cannot_resolve_an_action(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "health.json"
            finding = _finding()
            snapshot = _snapshot("check-1", finding, completed_at=20.0)
            encoded = snapshot.to_dict(privacy_safe=False)
            encoded["daily_maintenance"]["system_check"]["findings"][0]["evidence"]["facts"]["state"] = "active"
            path.write_text(
                json.dumps({"schema_version": 1, "snapshots": [encoded]}),
                encoding="utf-8",
            )

            with self.assertRaises(FindingHandoffError) as rejected:
                FindingActionHandoff(
                    snapshot_store=HealthTimelineStore(path)
                ).resolve(
                    check_result_id="check-1",
                    finding_fingerprint=finding.fingerprint,
                    origin_route="health",
                )

            self.assertEqual(rejected.exception.reason_code, "invalid_finding_context")

    def test_manual_only_finding_cannot_create_an_action_review(self):
        with tempfile.TemporaryDirectory() as directory:
            manual = SystemFinding.build(
                finding_id="recovery-protection",
                category="recovery",
                severity="attention",
                title="Recovery protection needs review",
                summary="No supported recovery backend is available.",
                evidence=FindingEvidence.from_mapping(
                    "recovery",
                    {"available": False},
                    collected_at=10.0,
                ),
                applicable_variants=frozenset({"traditional", "atomic"}),
                freshness_state="fresh",
                affected_resources=("recovery",),
                manual_guidance="Configure a supported recovery backend.",
                manual_reason_code="recovery-backend-unavailable",
            )
            store = HealthTimelineStore(Path(directory) / "health.json")
            store.save([_snapshot("check-manual", manual, completed_at=20.0)])

            with self.assertRaises(FindingHandoffError) as rejected:
                FindingActionHandoff(snapshot_store=store).resolve(
                    check_result_id="check-manual",
                    finding_fingerprint=manual.fingerprint,
                    origin_route="health",
                )

            self.assertEqual(
                rejected.exception.reason_code,
                "finding_mapping_rejected",
            )


class TestFindingActionUi(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_only_valid_fresh_mapping_gets_review_button_and_identifiers(self):
        with tempfile.TemporaryDirectory() as directory:
            finding = _finding()
            store = HealthTimelineStore(Path(directory) / "health.json")
            store.save([_snapshot("check-1", finding, completed_at=20.0)])
            service = SystemCheckPresentationService(
                snapshot_store=store,
                metric_path=Path(directory) / "missing.db",
            )
            tab = SystemCheckTab(presentation_service=service)
            self.addCleanup(tab.deleteLater)
            emitted: list[tuple[str, dict[str, str]]] = []
            tab.findingActionReviewRequested.connect(
                lambda action_id, context: emitted.append(
                    (action_id, dict(context))
                )
            )

            buttons = tab.findChildren(QPushButton, "systemCheckReviewAction")
            self.assertEqual(len(buttons), 1)
            buttons[0].click()

            self.assertEqual(emitted[0][0], "restart-failed-service")
            self.assertEqual(emitted[0][1]["check_result_id"], "check-1")
            self.assertEqual(
                emitted[0][1]["finding_fingerprint"],
                finding.fingerprint,
            )
            self.assertNotIn("command", str(emitted[0]))

    def test_manual_finding_has_guidance_and_no_review_button(self):
        state = SystemCheckPageState(
            latest_check_id="check-manual",
            latest_state="completed",
            latest_completed_at=20.0,
            atomic=False,
            findings=(
                FindingView(
                    "manual",
                    "a" * 64,
                    "recovery",
                    "attention",
                    "Manual review",
                    "Review recovery protection.",
                    "fresh",
                    "snapshots",
                    "",
                    ("recovery",),
                    "Create a recovery point manually.",
                    "manual-recovery-required",
                ),
            ),
            history=(),
            metrics=(),
            unavailable_sources=(),
            snapshot_error="",
            metric_error="",
        )

        class Fixture:
            def load(self, *, history_limit=30):
                return state

        tab = SystemCheckTab(presentation_service=Fixture())
        self.addCleanup(tab.deleteLater)

        self.assertEqual(
            tab.findChildren(QPushButton, "systemCheckReviewAction"),
            [],
        )
        self.assertIn(
            "manual-recovery-required",
            " ".join(label.text() for label in tab.findChildren(type(tab.last_checked_label))),
        )

    def test_shell_and_action_center_forward_identifiers_not_parameters(self):
        shell = SimpleNamespace(
            switch_to_route=MagicMock(return_value=True),
            _preselect_action_center=MagicMock(return_value=True),
        )
        context = {
            "check_result_id": "check-1",
            "finding_fingerprint": "a" * 64,
            "origin_route": "health",
        }

        MainWindow._open_system_check_action_request(
            shell,
            "restart-failed-service",
            context,
        )

        shell._preselect_action_center.assert_called_once_with(
            "restart-failed-service",
            finding_context=context,
        )

        orchestrator = MagicMock()
        orchestrator.plan_from_finding.return_value = object()
        item = SimpleNamespace(id="restart-failed-service")
        action_center = SimpleNamespace(
            _selected_item=lambda: item,
            _ACTION_ID_ADAPTERS={},
            _requested_parameters={"service": "untrusted.service"},
            _requested_finding_context=context,
            _orchestrator_instance=lambda: orchestrator,
            _target_key="44",
            _start_operation=lambda operation, on_success, _title: on_success(operation()),
            _accept_plan=MagicMock(),
            tr=lambda text: text,
        )

        _ActionCenterSubTab._plan_selected(action_center)

        orchestrator.plan_from_finding.assert_called_once_with(
            check_result_id="check-1",
            finding_fingerprint="a" * 64,
            origin_route="health",
            expected_action_id="restart-failed-service",
            target="44",
        )
        orchestrator.plan.assert_not_called()


if __name__ == "__main__":
    unittest.main()
