"""Installed package smoke tests use bounded, isolated inspection only."""

from __future__ import annotations

import importlib.util
import io
import json
import os
import subprocess
import unittest
from pathlib import Path
from unittest.mock import patch

SPEC = importlib.util.spec_from_file_location("package_smoke", Path(__file__).resolve().parents[1] / "scripts/package_smoke.py")
assert SPEC is not None and SPEC.loader is not None
smoke = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(smoke)


def _info():
    return {"version": "fixture", "codename": "Fixture", "system_type": "Traditional", "package_manager": "dnf5", "power_profile": "unknown"}


def _doctor(healthy=False):
    return {
        "fedora_version": 44, "support_status": "supported", "deployment_backend": "dnf5",
        "desktop": "unknown", "session_type": "unknown", "reboot_pending": None,
        "reboot_status": "unknown", "platform_ok": True, "profile_error": False,
        "polkit_active": healthy, "critical": {"pkexec": healthy, "systemctl": True, "dnf5": True},
        "optional": {"flatpak": False, "fwupdmgr": False, "timeshift": False, "snapper": False},
        "all_critical_ok": healthy,
    }


def _responses(healthy=False):
    return [subprocess.CompletedProcess([], 0, json.dumps(_info()), ""), subprocess.CompletedProcess([], 0 if healthy else 1, json.dumps(_doctor(healthy)), "")]


class TestPackageSmoke(unittest.TestCase):
    def test_valid_info_and_unavailable_doctor_are_accepted(self):
        self.assertEqual(smoke.validate_payload("info", json.dumps(_info()), 0), _info())
        self.assertEqual(smoke.validate_payload("doctor", json.dumps(_doctor()), 1), _doctor())
        self.assertEqual(smoke.validate_payload("doctor", json.dumps(_doctor(True)), 0), _doctor(True))

    def test_atomic_info_requires_nullable_pending_deployment(self):
        payload = _info()
        payload["system_type"] = "Atomic"
        for pending in (True, False, None):
            with self.subTest(pending=pending):
                payload["pending_deployment"] = pending
                self.assertEqual(smoke.validate_payload("info", json.dumps(payload), 0), payload)
        del payload["pending_deployment"]
        with self.assertRaises(ValueError):
            smoke.validate_payload("info", json.dumps(payload), 0)

    def test_invalid_json_non_objects_and_non_finite_numbers_are_rejected(self):
        for text in ("", "traceback", "[]", "null", "true", "{}\n{}", '{"a":NaN}', '{"a":[Infinity]}', '{"a":1e999}'):
            with self.subTest(text=text), self.assertRaises(ValueError):
                smoke.validate_payload("info", text, 0)

    def test_schema_changes_and_boolean_type_confusion_are_rejected(self):
        cases = []
        info = _info()
        del info["package_manager"]
        cases.append(("info", info, 0))
        info = _info()
        info["extra"] = True
        cases.append(("info", info, 0))
        info = _info()
        info["version"] = 1
        cases.append(("info", info, 0))
        for key, value in (("all_critical_ok", 0), ("fedora_version", True), ("critical", []), ("optional", {"tool": 1}), ("reboot_pending", 1), ("desktop", None)):
            doctor = _doctor()
            doctor[key] = value
            cases.append(("doctor", doctor, 1))
        for command, payload, status in cases:
            with self.subTest(command=command, payload=payload), self.assertRaises(ValueError):
                smoke.validate_payload(command, json.dumps(payload), status)

    def test_nonzero_info_and_inconsistent_doctor_exit_are_rejected(self):
        for command, payload, status in (
            ("info", _info(), 1), ("doctor", _doctor(), 0),
            ("doctor", _doctor(), 2), ("doctor", _doctor(True), 1),
        ):
            with self.subTest(command=command, status=status), self.assertRaises(ValueError):
                smoke.validate_payload(command, json.dumps(payload), status)

    @patch.dict(smoke.os.environ, {"PYTHONPATH": "/checkout/source", "PYTHONHOME": "/fixture/python", "DBUS_SESSION_BUS_ADDRESS": "fixture"})
    @patch.object(smoke.shutil, "which", return_value="/usr/bin/loofi-fedora-tweaks")
    @patch.object(smoke.subprocess, "run")
    def test_installed_launcher_global_flags_and_xdg_are_isolated(self, run, _which):
        captured_roots = []
        original_home = os.environ.get("HOME")

        def inspect_command(arguments, **kwargs):
            root = kwargs["cwd"]
            captured_roots.append(root)
            self.assertTrue(root.is_dir())
            self.assertEqual(arguments, ["/usr/bin/loofi-fedora-tweaks", "--cli", "--json", "--timeout", "15", arguments[-1]])
            self.assertEqual(kwargs["timeout"], 15)
            self.assertFalse(kwargs["check"])
            self.assertTrue(kwargs["capture_output"])
            self.assertTrue(kwargs["text"])
            environment = kwargs["env"]
            self.assertEqual(environment.get("HOME"), original_home)
            self.assertNotIn("PYTHONPATH", environment)
            self.assertNotIn("PYTHONHOME", environment)
            self.assertNotIn("DBUS_SESSION_BUS_ADDRESS", environment)
            self.assertEqual(environment["PYTHONNOUSERSITE"], "1")
            for variable in ("XDG_CONFIG_HOME", "XDG_DATA_HOME", "XDG_CACHE_HOME", "XDG_STATE_HOME", "XDG_RUNTIME_DIR"):
                path = Path(environment[variable])
                self.assertEqual(path.parent, root)
                self.assertEqual(path.stat().st_mode & 0o777, 0o700)
            return _responses()[0 if arguments[-1] == "info" else 1]

        run.side_effect = inspect_command
        results = smoke.run_smoke("loofi-fedora-tweaks", 15)

        self.assertEqual(tuple(results), ("info", "doctor"))
        self.assertEqual(run.call_count, 2)
        self.assertEqual(captured_roots[0], captured_roots[1])
        self.assertFalse(captured_roots[0].exists())
        self.assertEqual(os.environ["PYTHONPATH"], "/checkout/source")

    @patch.object(smoke.shutil, "which", return_value=None)
    @patch.object(smoke.subprocess, "run")
    def test_missing_launcher_and_invalid_timeout_do_not_spawn(self, run, _which):
        with self.assertRaises(ValueError):
            smoke.run_smoke("missing")
        with self.assertRaises(ValueError):
            smoke.run_smoke("installed", 0)
        run.assert_not_called()

    @patch.object(smoke.shutil, "which", return_value="/usr/bin/loofi-fedora-tweaks")
    @patch.object(smoke.subprocess, "run")
    def test_timeout_and_spawn_failure_clean_up_isolated_state(self, run, _which):
        for error in (subprocess.TimeoutExpired("fixture", 1), FileNotFoundError("fixture")):
            with self.subTest(error=error):
                run.side_effect = error
                with self.assertRaises(ValueError):
                    smoke.run_smoke("installed")
                self.assertFalse(run.call_args.kwargs["cwd"].exists())

    @patch.object(smoke.sys, "stdout", new_callable=io.StringIO)
    @patch.object(smoke.shutil, "which", return_value="/usr/bin/loofi-fedora-tweaks")
    @patch.object(smoke.subprocess, "run", side_effect=_responses())
    def test_main_accepts_expected_unavailable_doctor_and_passes_arguments(self, run, which, stdout):
        self.assertEqual(smoke.main(["--launcher", "/usr/bin/loofi-fedora-tweaks", "--timeout", "12"]), 0)
        which.assert_called_once_with("/usr/bin/loofi-fedora-tweaks")
        self.assertEqual(run.call_args.kwargs["timeout"], 12)
        self.assertIn("doctor unavailable", stdout.getvalue())

    @patch.object(smoke.sys, "stderr", new_callable=io.StringIO)
    @patch.object(smoke.tempfile, "TemporaryDirectory", side_effect=PermissionError("fixture"))
    @patch.object(smoke.shutil, "which", return_value="/usr/bin/loofi-fedora-tweaks")
    def test_main_reports_temporary_directory_failure(self, _which, directory, stderr):
        self.assertEqual(smoke.main([]), 1)
        directory.assert_called_once_with(prefix="loofi-package-smoke-")
        self.assertIn("[package-smoke] ERROR", stderr.getvalue())


if __name__ == "__main__":
    unittest.main()
