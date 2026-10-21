"""Bounded native setup qualification retains failures as independent evidence."""
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from e2e.guest import runner
from e2e.vm import FedoraE2E


class SetupRunnerTests(unittest.TestCase):
    @patch("e2e.vm.FedoraE2E._guest_exec", return_value=(0, "", ""))
    def test_parent_deadline_includes_each_native_phase_after_desktop_tests(self, execute):
        vm = FedoraE2E(Path("/unused"))
        for phase, seconds in (("normal", 45 * 60 + 120),
                               ("before-reboot", 45 * 60 + 900 + 600 + 120),
                               ("after-reboot", 45 * 60 + 300 + 120)):
            with self.subTest(phase=phase):
                self.assertEqual(vm._run_guest_tests(phase), 0)
                self.assertEqual(execute.call_args.kwargs["timeout"], seconds)
                self.assertEqual(execute.call_args.args[1][-1], phase)

    @patch("e2e.guest.runner.subprocess.run")
    def test_setup_runs_only_the_fixed_script_with_a_deadline(self, run):
        run.return_value = subprocess.CompletedProcess([], 7)
        with tempfile.TemporaryDirectory() as directory:
            original = runner.WORK
            self.addCleanup(setattr, runner, "WORK", original)
            runner.WORK = Path(directory)
            self.assertEqual(runner._run_setup_fixture(), 7)
            self.assertEqual(run.call_args.args[0], ["/usr/bin/python3", str(runner.WORK / "e2e/tests/setup_transaction_fixture.py")])
            self.assertEqual(run.call_args.kwargs["timeout"], 900)
            self.assertEqual((runner.WORK / "setup-transactions.log").stat().st_mode & 0o777, 0o600)

    @patch("e2e.guest.runner.subprocess.run")
    def test_fixture_timeout_or_launch_failure_is_recorded_as_failure(self, run):
        for error in (subprocess.TimeoutExpired("private command", 900), OSError("private launch detail")):
            with self.subTest(error=type(error).__name__), tempfile.TemporaryDirectory() as directory:
                original = runner.WORK
                runner.WORK = Path(directory)
                try:
                    run.side_effect = error
                    self.assertEqual(runner._run_setup_fixture(), 1)
                    text = (runner.WORK / "setup-transactions.log").read_text()
                    self.assertIn(type(error).__name__, text)
                    self.assertNotIn("private", text)
                finally:
                    runner.WORK = original
