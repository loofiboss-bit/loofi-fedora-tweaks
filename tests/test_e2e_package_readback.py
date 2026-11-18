"""Rootless regressions for guest fixture readback and failed transactions."""
from __future__ import annotations

import importlib.util
from pathlib import Path
import subprocess
import sys
from types import ModuleType, SimpleNamespace
import unittest
from unittest.mock import Mock, mock_open, patch


MODULE_NAME = "loofi_e2e_package_fixture"
HELPERS_MODULE_NAME = "loofi_e2e_helpers"


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


class TestPolkitHelperContract(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        selenium_mod = ModuleType("selenium")
        webdriver_mod = ModuleType("selenium.webdriver")
        common_mod = ModuleType("selenium.webdriver.common")
        by_mod = ModuleType("selenium.webdriver.common.by")
        by_mod.By = SimpleNamespace(XPATH="xpath")
        path = Path(__file__).resolve().parents[1] / "e2e/tests/helpers.py"
        spec = importlib.util.spec_from_file_location(HELPERS_MODULE_NAME, path)
        cls.helpers = importlib.util.module_from_spec(spec)
        sys.modules[HELPERS_MODULE_NAME] = cls.helpers
        with patch.dict(
            sys.modules,
            {
                "selenium": selenium_mod,
                "selenium.webdriver": webdriver_mod,
                "selenium.webdriver.common": common_mod,
                "selenium.webdriver.common.by": by_mod,
            },
        ):
            spec.loader.exec_module(cls.helpers)

    @classmethod
    def tearDownClass(cls) -> None:
        sys.modules.pop(HELPERS_MODULE_NAME, None)

    def test_polkit_helper_waits_for_a_delayed_password_prompt(self) -> None:
        password_field = Mock()
        wait_for_password = Mock(side_effect=[AssertionError("not ready"), AssertionError("not ready"), password_field])
        completion = Mock(return_value=False)
        pyatspi = ModuleType("pyatspi")
        keyboard_event = Mock()
        pyatspi.Registry = SimpleNamespace(generateKeyboardEvent=keyboard_event)
        pyatspi.KEY_SYM = 1

        with (
            patch.object(self.helpers, "wait_for_polkit_password", side_effect=wait_for_password),
            patch.object(self.helpers, "_driver", Mock()),
            patch.object(self.helpers.Accessible, "click"),
            patch.object(self.helpers.Path, "read_text", return_value='{"password":"x"}'),
            patch.object(self.helpers.time, "sleep"),
            patch.dict(
                "os.environ",
                {"LOOFI_E2E_CREDENTIALS_PATH": "/tmp/loofi-e2e-credentials.json", "XDG_SESSION_TYPE": "x11"},
            ),
            patch.dict("sys.modules", {"pyatspi": pyatspi}),
        ):
            self.helpers.authenticate_polkit(completed=completion, timeout=5)

        self.assertEqual(wait_for_password.call_count, 3)
        self.assertEqual(completion.call_count, 2)
        keyboard_event.assert_called_once_with(ord("x"), None, pyatspi.KEY_SYM)

    def test_polkit_helper_accepts_cached_authorization_only_after_readback(self) -> None:
        wait_for_password = Mock(side_effect=AssertionError("prompt is cached"))
        completion = Mock(side_effect=[False, False, True])

        with patch.object(self.helpers, "wait_for_polkit_password", side_effect=wait_for_password):
            self.helpers.authenticate_polkit(completed=completion, timeout=5)

        self.assertEqual(wait_for_password.call_count, 3)
        self.assertEqual(completion.call_count, 3)
