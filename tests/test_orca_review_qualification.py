"""Speech evidence parsing and bounded cleanup of private Orca fixture processes."""
from __future__ import annotations

import importlib.util
from pathlib import Path
import signal
import subprocess
import tempfile
import unittest
from unittest.mock import Mock, call, patch

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("orca_review_qualification", ROOT / "scripts" / "qualify_orca_review.py")
qualification = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(qualification)


class TestOrcaSpeechEvidence(unittest.TestCase):
    def evidence(self, after="checked", before="not checked"):
        before_log = (
            "00:00:01 - SPEECH OUTPUT: 'Exact change scope'\n"
            "00:00:02 - SPEECH OUTPUT: 'Accept that this action has no automatic rollback'\n"
            f"00:00:03 - SPEECH OUTPUT: '{before}'\n"
        ).encode()
        after_log = (f"00:00:04 - SPEECH OUTPUT: '{after}'\n00:00:05 - SPEECH OUTPUT: 'Apply and verify'\n").encode()
        return before_log + after_log, {"before_space_log_offset": len(before_log), "unchecked_before_space": True,
                                        "checked_after_space": True}

    def test_actual_unchecked_and_checked_stages_are_both_required(self):
        log, stage = self.evidence()
        checks, speech = qualification._speech_checks(log, stage)
        self.assertTrue(all(checks.values()))
        self.assertEqual(len(speech), 5)

    def test_not_checked_does_not_count_as_positive_checked_evidence(self):
        for after in ("not checked", "not  checked", "unchecked", "not\tchecked"):
            with self.subTest(after=after):
                log, stage = self.evidence(after=after)
                checks, _speech = qualification._speech_checks(log, stage)
                self.assertTrue(checks["unchecked before Space"])
                self.assertFalse(checks["checked after Space"])

    def test_checked_speech_before_space_cannot_qualify_a_state_change(self):
        log, stage = self.evidence(after="Apply and verify", before="checked")
        checks, _speech = qualification._speech_checks(log, stage)
        self.assertFalse(checks["unchecked before Space"])
        self.assertFalse(checks["checked after Space"])

    def test_widget_observation_cannot_be_replaced_by_speech_only(self):
        log, stage = self.evidence()
        stage["checked_after_space"] = False
        checks, _speech = qualification._speech_checks(log, stage)
        self.assertFalse(checks["checked after Space"])

    def test_invalid_stage_boundaries_are_rejected(self):
        for offset in (-1, 10000, True, "5", None):
            with self.subTest(offset=offset), self.assertRaises(ValueError):
                qualification._speech_checks(b"SPEECH OUTPUT: 'checked'", {"before_space_log_offset": offset})


class TestOrcaProcessLifecycle(unittest.TestCase):
    def test_previous_readiness_and_stage_artifacts_cannot_qualify_a_new_run(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            for name in ("orca-debug.log", "probe-stages.json", "summary.json"):
                (output / name).write_text("old success/readiness evidence", encoding="utf-8")
            preserved = output / "unrelated.txt"
            preserved.write_text("preserve", encoding="utf-8")
            qualification._reset_run_artifacts(output)
            self.assertEqual(list(output.iterdir()), [preserved])

    def test_stubborn_child_is_killed_and_reaped_with_bounded_waits(self):
        process = Mock()
        process.poll.return_value = None
        process.wait.side_effect = [subprocess.TimeoutExpired("fixture", 3), 0]
        qualification._stop_process(process)
        process.terminate.assert_called_once_with()
        process.kill.assert_called_once_with()
        self.assertEqual(process.wait.call_args_list, [call(timeout=3), call(timeout=3)])

    def test_already_exited_child_does_not_get_signalled(self):
        process = Mock()
        process.poll.return_value = 0
        qualification._stop_process(process)
        process.terminate.assert_not_called()
        process.kill.assert_not_called()

    @patch.object(qualification.os, "killpg")
    @patch.object(qualification.subprocess, "Popen")
    def test_whole_wrapper_timeout_cleans_its_owned_process_group(self, popen, killpg):
        process = popen.return_value
        process.pid = 12345
        process.wait.side_effect = [subprocess.TimeoutExpired("private bus", 90), 0, 0]
        with self.assertRaises(subprocess.TimeoutExpired):
            qualification._run_private_session(["private-session"], {"LANG": "en_US.UTF-8"})
        self.assertTrue(popen.call_args.kwargs["start_new_session"])
        self.assertEqual(killpg.call_args_list, [call(12345, signal.SIGTERM), call(12345, signal.SIGKILL)])
        self.assertEqual(process.wait.call_args_list, [call(timeout=90), call(timeout=3), call(timeout=3)])

    @patch.object(qualification.time, "sleep")
    @patch.object(qualification.subprocess, "run")
    @patch.object(qualification.subprocess, "Popen")
    def test_registry_start_failure_also_cleans_already_started_bus(self, popen, run, _sleep):
        bus = Mock()
        bus.poll.return_value = None
        bus.wait.return_value = 0
        popen.side_effect = [bus, OSError("synthetic registry start failure")]
        run.return_value = Mock(returncode=0, stdout="('unix:path=/fixture/private-bus',)")
        with tempfile.TemporaryDirectory() as directory, self.assertRaisesRegex(OSError, "registry start"):
            qualification.worker(Path(directory), "wayland")
        bus.terminate.assert_called_once_with()
        bus.wait.assert_called_once_with(timeout=3)


if __name__ == "__main__":
    unittest.main()
