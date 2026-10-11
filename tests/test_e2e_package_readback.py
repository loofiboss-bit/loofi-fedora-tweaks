"""Rootless regressions for guest fixture readback and failed transactions."""
from __future__ import annotations

import importlib.util
from pathlib import Path
import subprocess
import sys
from types import ModuleType
import unittest
from unittest.mock import Mock, mock_open, patch


MODULE_NAME = "loofi_e2e_package_fixture"


class TestGuestPackageReadback(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        helpers = ModuleType("helpers")
        helpers.authenticate_polkit = Mock()
        path = Path(__file__).resolve().parents[1] / "e2e/tests/test_local_package_fixture.py"
        spec = importlib.util.spec_from_file_location(MODULE_NAME, path)
        cls.module = importlib.util.module_from_spec(spec)
        sys.modules[MODULE_NAME] = cls.module
        with patch.dict(sys.modules, {"helpers": helpers}):
            spec.loader.exec_module(cls.module)

    @classmethod
    def tearDownClass(cls):
        sys.modules.pop(MODULE_NAME, None)

    @patch(MODULE_NAME + ".subprocess.run")
    def test_installed_fixture_requires_exact_identity(self, run):
        run.return_value = subprocess.CompletedProcess([], 0, "unexpected-package 1.0-1", "")
        with self.assertRaises(AssertionError):
            self.module.installed()
        self.assertEqual(run.call_args.kwargs["timeout"], 10)

    @patch(MODULE_NAME + ".subprocess.run")
    def test_only_rpm_absence_is_accepted_as_not_installed(self, run):
        run.return_value = subprocess.CompletedProcess([], 2, "", "broken database")
        with self.assertRaises(AssertionError):
            self.module.installed()

    @patch("builtins.open", new_callable=mock_open)
    @patch(MODULE_NAME + ".authenticate_polkit")
    @patch(MODULE_NAME + ".subprocess.Popen")
    def test_failed_transaction_cannot_be_accepted_as_cached_authorization(self, popen, auth, _open):
        process = popen.return_value
        process.poll.return_value = 1
        process.returncode = 1
        auth.side_effect = lambda *, completed: completed()
        readback = Mock(return_value=True)
        with self.assertRaisesRegex(AssertionError, "fixture transaction failed"):
            self.module.transaction(["install", "/var/tmp/loofi-e2e/loofi-e2e-fixture.rpm"], readback)
        readback.assert_not_called()
        process.terminate.assert_not_called()

    @patch("builtins.open", new_callable=mock_open)
    @patch(MODULE_NAME + ".authenticate_polkit")
    @patch(MODULE_NAME + ".subprocess.Popen")
    def test_success_exit_still_requires_independent_readback(self, popen, auth, _open):
        process = popen.return_value
        process.poll.return_value = 0
        process.returncode = 0
        process.wait.return_value = 0
        with self.assertRaisesRegex(AssertionError, "independent RPM/payload readback"):
            self.module.transaction(["remove", "loofi-e2e-fixture"], Mock(return_value=False))
        command = popen.call_args.args[0]
        self.assertEqual(command[:4], ["pkexec", "/usr/bin/dnf5", "--cacheonly", "--assumeyes"])
        auth.assert_called_once()
