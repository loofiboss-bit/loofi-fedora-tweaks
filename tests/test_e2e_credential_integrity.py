"""Credential integrity checks must fail before guest execution."""

import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from e2e.vm import FedoraE2E, PASSWORD_ITERATIONS, VMError, _credential_digest


class TestCredentialIntegrity(unittest.TestCase):
    def setUp(self):
        self.vm = FedoraE2E(Path("/tmp/loofi-e2e-contract"))
        self.vm.password_path = Mock()
        self.vm.password_path.read_text.return_value = "test-guest-password\n"
        self.salt = "01" * 16
        self.vm._state = {
            "password_salt": self.salt,
            "password_verifier": _credential_digest("test-guest-password", self.salt),
        }

    def test_salted_password_kdf_is_deterministic_and_uses_bounded_work(self):
        self.assertEqual(PASSWORD_ITERATIONS, 600_000)
        self.assertEqual(self.vm._state["password_verifier"], _credential_digest("test-guest-password", self.salt))
        self.assertNotEqual(self.vm._state["password_verifier"], _credential_digest("test-guest-password", "02" * 16))

    @patch("e2e.vm.console_execute", return_value=(0, "ok", ""))
    @patch.object(FedoraE2E, "_assert_owned_domain")
    def test_valid_marker_allows_guest_execution(self, ownership, console):
        self.assertEqual(self.vm._guest_exec("/usr/bin/true", []), (0, "ok", ""))
        ownership.assert_called_once()
        console.assert_called_once()

    @patch("e2e.vm.console_execute")
    @patch.object(FedoraE2E, "_assert_owned_domain")
    def test_changed_private_password_is_rejected_before_guest_execution(self, ownership, console):
        self.vm.password_path.read_text.return_value = "changed-private-password\n"
        with self.assertRaisesRegex(VMError, "does not match"):
            self.vm._guest_exec("/usr/bin/true", [])
        console.assert_not_called()

    @patch("e2e.vm.console_execute")
    @patch.object(FedoraE2E, "_assert_owned_domain")
    def test_invalid_or_missing_metadata_is_rejected(self, ownership, console):
        for state in ({}, {"password_salt": "zz" * 16, "password_verifier": "00" * 32},
                      {"password_salt": self.salt, "password_verifier": None}):
            with self.subTest(state=state):
                self.vm._state = state
                with self.assertRaisesRegex(VMError, "missing or invalid"):
                    self.vm._guest_exec("/usr/bin/true", [])
        console.assert_not_called()


if __name__ == "__main__":
    unittest.main()
