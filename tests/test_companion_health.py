"""Companion read-only metadata and local support draft contracts."""
from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch
import zipfile

from core.export.support_question import SupportQuestionService
from services.hardware.screen_sharing_diagnostics import ScreenSharingDiagnosticProbe, _source_types
from test_troubleshoot_widget import _session, _History
from ui.troubleshoot_widget import TroubleshootWidget
from PyQt6.QtWidgets import QApplication


class TestScreenSharingProbe(unittest.TestCase):
    @patch.dict("os.environ", {"XDG_SESSION_TYPE": "wayland"})
    def test_fixed_bounded_read_vectors_never_capture_or_activate(self):
        runner = Mock(side_effect=[SimpleNamespace(returncode=0, stdout="active\n") for _ in range(3)]
                      + [SimpleNamespace(returncode=0, stdout="u 3\n")])
        result = ScreenSharingDiagnosticProbe(runner=runner, which=lambda name: "/usr/bin/" + name).collect(
            cancellation=SimpleNamespace(is_cancelled=lambda: False))
        self.assertEqual(result.state, "completed")
        self.assertEqual(result.facts["available_source_types"], 3)
        vectors = [call.args[0] for call in runner.call_args_list]
        self.assertIn("--auto-start=no", vectors[-1])
        self.assertEqual(vectors[-1][-1], "AvailableSourceTypes")
        self.assertTrue(all(call.kwargs["timeout"] <= 2 for call in runner.call_args_list))
        self.assertNotIn("CreateSession", str(vectors))
        self.assertNotIn("Start", str(vectors))

    @patch.dict("os.environ", {"XDG_SESSION_TYPE": "wayland"})
    def test_portal_error_or_malformed_metadata_is_unknown(self):
        for response in ("not a signature", "u 8", "u -1"):
            runner = Mock(side_effect=[SimpleNamespace(returncode=0, stdout="active") for _ in range(3)]
                          + [SimpleNamespace(returncode=0, stdout=response)])
            result = ScreenSharingDiagnosticProbe(runner=runner, which=lambda name: name).collect(
                cancellation=SimpleNamespace(is_cancelled=lambda: False))
            self.assertEqual(result.state, "partial")
            self.assertIsNone(result.facts["available_source_types"])
        self.assertEqual(_source_types("u 0"), 0)

    @patch.dict("os.environ", {}, clear=True)
    def test_missing_tools_remain_unavailable_and_cancel_stops_probes(self):
        runner = Mock()
        probe = ScreenSharingDiagnosticProbe(runner=runner, which=lambda name: None)
        result = probe.collect(cancellation=SimpleNamespace(is_cancelled=lambda: False))
        self.assertEqual(result.state, "unavailable")
        result = probe.collect(cancellation=SimpleNamespace(is_cancelled=lambda: True))
        self.assertEqual(result.reason_code, "cancelled")
        runner.assert_not_called()


class TestScreenSharingAdapter(unittest.TestCase):
    @patch("services.hardware.screen_sharing_diagnostics.ScreenSharingDiagnosticProbe")
    def test_inactive_service_is_a_finding_and_zero_sources_are_not_healthy(self, probe):
        from core.troubleshooting.lifecycle import new_session, start_session, CancellationSignal
        from core.troubleshooting.service import DefaultEvidenceCollector
        from services.hardware.diagnostic_probes import HardwareDiagnosticResult

        session = start_session(new_session("screen_sharing_not_working", "traditional", started_at=1.0), started_at=1.0)
        probe.return_value.collect.return_value = HardwareDiagnosticResult({
            "session_type": "wayland", "pipewire_state": "active", "wireplumber_state": "failed",
            "xdg-desktop-portal_state": "active", "available_source_types": 0,
        }, "completed")
        result = DefaultEvidenceCollector(clock=lambda: 2.0).collect(
            "screen-sharing-state", session, started_at=1.0, cancellation=CancellationSignal())
        self.assertEqual(len(result.findings), 2)
        self.assertTrue(all(f.next_step.kind == "manual" for f in result.findings))
        self.assertEqual(result.result.state, "completed")

    @patch("services.hardware.screen_sharing_diagnostics.ScreenSharingDiagnosticProbe")
    def test_unknown_observations_cannot_claim_findings(self, probe):
        from core.troubleshooting.lifecycle import new_session, start_session, CancellationSignal
        from core.troubleshooting.service import DefaultEvidenceCollector
        from services.hardware.diagnostic_probes import HardwareDiagnosticResult

        session = start_session(new_session("screen_sharing_not_working", "atomic", started_at=1.0), started_at=1.0)
        probe.return_value.collect.return_value = HardwareDiagnosticResult({"session_type": None}, "unavailable", "tool-unavailable")
        result = DefaultEvidenceCollector(clock=lambda: 2.0).collect(
            "screen-sharing-state", session, started_at=1.0, cancellation=CancellationSignal())
        self.assertEqual(result.result.state, "unavailable")
        self.assertEqual(result.findings, ())


class TestSupportQuestion(unittest.TestCase):
    def test_exact_saved_session_no_other_collection_and_export_redacts_edits(self):
        inspection = Mock()
        session = _session()
        inspection.require.return_value = session
        service = SupportQuestionService(inspection)
        preview = service.preview(session.session_id, "Sharing fails password=super-secret", "1. Start the app")
        inspection.require.assert_called_once_with(session.session_id)
        self.assertIn(session.session_id, preview)
        self.assertNotIn("super-secret", preview)
        with TemporaryDirectory() as directory:
            for suffix in (".md", ".zip"):
                path = Path(directory) / ("question" + suffix)
                service.export(path, preview + "\ntoken=edited-secret\npassword\nmultiline-secret\n")
                if suffix == ".zip":
                    with zipfile.ZipFile(path) as archive:
                        self.assertEqual(archive.namelist(), ["support-question.md"])
                        text = archive.read("support-question.md").decode()
                else:
                    text = path.read_text()
                self.assertNotIn("edited-secret", text)
                self.assertNotIn("multiline-secret", text)
                self.assertIn("No new collection", text)
        inspection.require.assert_called_once()

    def test_missing_saved_session_and_invalid_drafts_fail_closed(self):
        inspection = Mock()
        inspection.require.side_effect = LookupError("missing")
        service = SupportQuestionService(inspection)
        with self.assertRaises(LookupError):
            service.preview(_session().session_id, "Problem", "")
        with self.assertRaises(ValueError):
            service.preview(_session().session_id, "", "")
        with self.assertRaises(ValueError):
            service.sanitize("x" * 64001)


class TestHealthSavedComparison(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    @patch("ui.native_handoff_card.NativeHandoffCard.refresh_availability")
    def test_explicit_baseline_and_selected_saved_session(self, _refresh):
        before = _session()
        after = replace(before, session_id="22345678-1234-5678-9234-567812345678", completed_at=4.0)
        history = _History(after)
        history.sessions = lambda: (after, before)
        widget = TroubleshootWidget(history=history)
        self.assertEqual(widget.baseline_selector.currentData(), "")
        widget.baseline_selector.setCurrentIndex(1)
        widget._compare_saved()
        self.assertEqual(widget._comparison.before_session_id, before.session_id)
        self.assertEqual(widget._comparison.outcomes[0].state, "unchanged")
        self.assertTrue(widget.support_question_button.isEnabled())
        widget.saved_session_selector.setCurrentIndex(1)
        self.assertEqual(widget._current_session.session_id, before.session_id)
        self.assertFalse(widget.compare_saved_button.isEnabled())
        widget.cleanup()

    @patch("ui.native_handoff_card.NativeHandoffCard.refresh_availability")
    def test_shutdown_retains_running_worker_until_it_stops(self, _refresh):
        from test_troubleshoot_widget import _Worker

        worker = _Worker()
        widget = TroubleshootWidget(history=_History(), worker_factory=lambda *_args: worker)
        stopped = []
        widget.stopped.connect(lambda: stopped.append(True))
        widget.start_session()
        self.assertTrue(widget.busy)
        widget.request_stop()
        self.assertTrue(worker.cancelled)
        self.assertIs(widget._worker, worker)
        self.assertEqual(stopped, [])
        worker.running = False
        widget._check_stopped()
        self.assertFalse(widget.busy)
        self.assertIsNone(widget._worker)
        self.assertEqual(stopped, [True])
        widget.deleteLater()
