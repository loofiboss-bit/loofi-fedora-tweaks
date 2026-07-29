"""UI contract tests for the single Compass Troubleshoot surface."""

from __future__ import annotations

import unittest
from types import SimpleNamespace

from PyQt6.QtCore import QObject, Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QFont
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QApplication

from core.troubleshooting.adapters import adapt_structured_source
from core.troubleshooting.composition import compose_session
from core.troubleshooting.lifecycle import new_session, start_session
from core.troubleshooting.models import NextStep, TroubleshootingFinding
from ui.components import (
    DetailsDisclosure,
    LocalViewSwitcher,
    PageScaffold,
    PrimaryButton,
)
from ui.design.theme_manager import ThemeManager
from ui.troubleshoot_widget import TroubleshootWidget


class _History:
    def __init__(self, session=None, reason_code=""):
        self.session = session
        self.reason_code = reason_code
        self.calls = 0

    def latest(self):
        self.calls += 1
        return self.session, self.reason_code


class _Worker(QObject):
    source_progress = pyqtSignal(object)
    finished = pyqtSignal(object)
    error = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self.started = False
        self.cancelled = False
        self.running = False

    def start(self):
        self.started = True
        self.running = True

    def cancel(self):
        self.cancelled = True

    def isRunning(self):
        return self.running

    def wait(self, _milliseconds):
        return True


def _session():
    finding = TroubleshootingFinding.build(
        finding_type="network-disconnected",
        category="network",
        severity="attention",
        title="No active network connection was found",
        summary="NetworkManager did not report an active connection.",
        evidence_explanation="Bounded source-owned metadata supports this finding.",
        source_id="network-state",
        collected_at=2.0,
        freshness="fresh",
        evidence_quality="confirmed",
        applicable_variants=frozenset({"traditional"}),
        affected_resources=("network-manager",),
        evidence={"active_connection": False},
        next_step=NextStep.navigation(
            "network",
            {"section": "connections"},
            reason_code="review-network-state",
        ),
    )
    running = start_session(
        new_session(
            "network_problem",
            "traditional",
            started_at=1.0,
            session_id="12345678-1234-5678-9234-567812345678",
        ),
        started_at=1.0,
    )
    sources = (
        adapt_structured_source(
            profile_id="network_problem",
            variant="traditional",
            source_id="network-state",
            state="completed",
            started_at=1.0,
            completed_at=2.0,
            facts={"active_connection": False},
            findings=(finding,),
        ),
        adapt_structured_source(
            profile_id="network_problem",
            variant="traditional",
            source_id="dns-state",
            state="empty",
            started_at=1.0,
            completed_at=2.0,
        ),
        adapt_structured_source(
            profile_id="network_problem",
            variant="traditional",
            source_id="change-journal",
            state="empty",
            started_at=1.0,
            completed_at=2.0,
        ),
    )
    return compose_session(running, sources, completed_at=3.0)


class TestTroubleshootWidget(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_page_uses_one_scaffold_one_switcher_and_one_primary_action(self):
        factory_calls = []
        widget = TroubleshootWidget(
            worker_factory=lambda *args: factory_calls.append(args),
            history=_History(),
        )
        self.addCleanup(widget.deleteLater)

        self.assertEqual(len(widget.findChildren(PageScaffold)), 1)
        self.assertEqual(len(widget.findChildren(LocalViewSwitcher)), 1)
        self.assertEqual(len(widget.findChildren(PrimaryButton)), 1)
        self.assertEqual(widget.profile_selector.count(), 6)
        self.assertEqual(widget.profile_label.text(), "Problem profile")
        self.assertEqual(widget.profile_label.buddy(), widget.profile_selector)
        self.assertEqual(factory_calls, [])
        self.assertEqual(widget.findChildren(DetailsDisclosure)[0].toggle_button.isChecked(), False)

    def test_explicit_start_constructs_worker_and_cancel_is_cooperative(self):
        worker = _Worker()
        calls = []

        def factory(profile_id, parameters, parent):
            calls.append((profile_id, parameters, parent))
            return worker

        widget = TroubleshootWidget(
            worker_factory=factory,
            history=_History(),
        )
        self.addCleanup(widget.deleteLater)

        widget.start_session()

        self.assertEqual(calls, [("system_slow", {}, widget)])
        self.assertTrue(worker.started)
        self.assertTrue(widget.progress.isVisible() or not widget.isVisible())

        widget.cancel_session()

        self.assertTrue(worker.cancelled)

    def test_application_profile_requires_bounded_identifier_before_worker(self):
        calls = []
        widget = TroubleshootWidget(
            worker_factory=lambda *args: calls.append(args),
            history=_History(),
        )
        self.addCleanup(widget.deleteLater)
        widget.profile_selector.setCurrentIndex(
            widget.profile_selector.findData("application_failed")
        )

        widget.start_session()

        self.assertEqual(calls, [])
        self.assertFalse(widget.start_notice.isHidden())

    def test_rendered_finding_emits_inert_route_and_preselection(self):
        session = _session()
        widget = TroubleshootWidget(history=_History(session))
        self.addCleanup(widget.deleteLater)
        requests = []
        widget.routeRequested.connect(
            lambda route_id, metadata: requests.append((route_id, metadata))
        )

        widget._select_view("results")
        widget.next_step_button.click()

        self.assertEqual(
            requests,
            [("network", {"section": "connections"})],
        )
        self.assertIn("Source:", widget.finding_summary.text())
        self.assertFalse(widget.evidence_disclosure.toggle_button.isChecked())

    def test_keyboard_focus_rtl_and_reduced_motion_keep_actions_reachable(self):
        session = _session()
        widget = TroubleshootWidget(history=_History(session))
        self.addCleanup(widget.deleteLater)
        requests = []
        widget.routeRequested.connect(
            lambda route_id, metadata: requests.append((route_id, metadata))
        )
        widget.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
        widget.show()
        self.app.processEvents()

        widget.next_step_button.setFocus()
        QTest.keyClick(widget.next_step_button, Qt.Key.Key_Space)

        self.assertTrue(widget.next_step_button.hasFocus())
        self.assertEqual(requests, [("network", {"section": "connections"})])
        self.assertEqual(widget.findChildren(QTimer), [])
        self.assertEqual(
            widget.layoutDirection(),
            Qt.LayoutDirection.RightToLeft,
        )

    def test_geometry_theme_and_scale_matrix_keeps_primary_action_inside_page(self):
        original_font = self.app.font()
        theme_manager = ThemeManager()
        try:
            for theme in ThemeManager.SUPPORTED_THEMES:
                self.assertTrue(theme_manager.apply(self.app, theme))
                for width in (900, 1180, 1366):
                    for scale in (100, 150, 200):
                        with self.subTest(theme=theme, width=width, scale=scale):
                            font = QFont(original_font)
                            font.setPointSizeF(
                                original_font.pointSizeF() * scale / 100
                            )
                            self.app.setFont(font)
                            widget = TroubleshootWidget(history=_History())
                            widget.resize(width, 900)
                            widget.show()
                            self.app.processEvents()

                            self.assertTrue(widget.start_button.isVisible())
                            self.assertGreater(widget.start_button.width(), 0)
                            self.assertLessEqual(
                                widget.start_button.mapTo(
                                    widget,
                                    widget.start_button.rect().topRight(),
                                ).x(),
                                widget.width(),
                            )

                            widget.close()
                            widget.deleteLater()
                            self.app.processEvents()
        finally:
            self.app.setFont(original_font)
            theme_manager.apply(self.app, "system")

    def test_finished_session_switches_to_results_without_new_history_surface(self):
        worker = _Worker()
        widget = TroubleshootWidget(
            worker_factory=lambda *_args: worker,
            history=_History(),
        )
        self.addCleanup(widget.deleteLater)
        widget.start_session()
        worker.running = False

        worker.finished.emit(
            SimpleNamespace(
                session=_session(),
                comparison=None,
                persistence_reason_code="",
            )
        )

        self.assertEqual(widget.view_switcher.active_view_id(), "results")
        self.assertEqual(widget.stack.currentIndex(), 1)
        self.assertEqual(widget.finding_list.count(), 1)
        self.assertEqual(widget.start_button.text(), "Check again")


if __name__ == "__main__":
    unittest.main()
