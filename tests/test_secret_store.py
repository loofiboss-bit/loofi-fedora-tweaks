"""Provider-neutral SecretStore CRUD and fallback contracts."""

from __future__ import annotations

import sys
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from core.secrets import SecretStore


class BackendLockedError(Exception):
    """Test-only error that is intentionally not tied to one provider."""


class PasswordDeleteError(Exception):
    """Test stand-in for keyring's provider-neutral missing-secret error."""


class LockedPriorityBackend:
    """Backend whose availability probe fails as a locked provider might."""

    @property
    def priority(self) -> float:
        raise BackendLockedError("locked")


class TestSecretStoreProviderContract(unittest.TestCase):
    def setUp(self) -> None:
        SecretStore._session.clear()

    def tearDown(self) -> None:
        SecretStore._session.clear()

    @patch.object(SecretStore, "_keyring")
    def test_persistent_crud_uses_backend_without_session_shadow(self, keyring_factory) -> None:
        values: dict[tuple[str, str], str] = {}
        keyring = MagicMock()
        keyring.errors = SimpleNamespace(PasswordDeleteError=PasswordDeleteError)
        keyring.set_password.side_effect = lambda service, account, value: values.__setitem__(
            (service, account),
            value,
        )
        keyring.get_password.side_effect = lambda service, account: values.get((service, account))
        keyring.delete_password.side_effect = lambda service, account: values.pop((service, account))
        keyring_factory.return_value = keyring

        written = SecretStore.set("account", "secret")

        self.assertTrue(written.success)
        self.assertTrue(written.persistent)
        self.assertEqual(SecretStore.get("account"), "secret")
        self.assertNotIn("account", SecretStore._session)
        self.assertTrue(SecretStore.delete("account"))
        self.assertIsNone(SecretStore.get("account"))

    @patch.object(SecretStore, "_keyring", return_value=None)
    def test_unavailable_backend_uses_session_crud(self, _keyring) -> None:
        written = SecretStore.set("account", "session-secret")

        self.assertTrue(written.success)
        self.assertFalse(written.persistent)
        self.assertEqual(SecretStore.get("account"), "session-secret")
        self.assertTrue(SecretStore.delete("account"))
        self.assertIsNone(SecretStore.get("account"))

    @patch.object(SecretStore, "_keyring")
    def test_locked_backend_read_and_write_fall_back_to_session(self, keyring_factory) -> None:
        keyring = MagicMock()
        keyring.get_password.side_effect = BackendLockedError("locked")
        keyring.set_password.side_effect = BackendLockedError("locked")
        keyring_factory.return_value = keyring
        SecretStore._session["existing"] = "existing-session"

        self.assertEqual(SecretStore.get("existing"), "existing-session")
        written = SecretStore.set("new", "new-session")

        self.assertTrue(written.success)
        self.assertFalse(written.persistent)
        self.assertEqual(SecretStore._session["new"], "new-session")

    @patch.object(SecretStore, "_keyring")
    def test_locked_delete_is_truthful_and_clears_session_copy(self, keyring_factory) -> None:
        keyring = MagicMock()
        keyring.errors = SimpleNamespace(PasswordDeleteError=PasswordDeleteError)
        keyring.delete_password.side_effect = BackendLockedError("locked")
        keyring_factory.return_value = keyring
        SecretStore._session["account"] = "session-secret"

        self.assertFalse(SecretStore.delete("account"))
        self.assertNotIn("account", SecretStore._session)

    @patch.object(SecretStore, "_keyring")
    def test_missing_persistent_secret_is_successful_delete(self, keyring_factory) -> None:
        keyring = MagicMock()
        keyring.errors = SimpleNamespace(PasswordDeleteError=PasswordDeleteError)
        keyring.delete_password.side_effect = PasswordDeleteError("missing")
        keyring_factory.return_value = keyring

        self.assertTrue(SecretStore.delete("missing"))

    @patch.object(SecretStore, "_keyring")
    def test_readback_mismatch_fails_closed_without_session_shadow(self, keyring_factory) -> None:
        keyring = MagicMock()
        keyring.get_password.return_value = "different-secret"
        keyring_factory.return_value = keyring

        written = SecretStore.set("account", "new-secret")

        self.assertFalse(written.success)
        self.assertFalse(written.persistent)
        self.assertNotIn("account", SecretStore._session)

    @patch.object(SecretStore, "_keyring")
    def test_empty_account_never_reaches_backend(self, keyring_factory) -> None:
        keyring = MagicMock()
        keyring_factory.return_value = keyring

        self.assertIsNone(SecretStore.get(""))
        self.assertIsNone(SecretStore.get_persistent(""))
        self.assertFalse(SecretStore.delete(""))
        self.assertFalse(SecretStore.set("", "secret").success)
        keyring.get_password.assert_not_called()
        keyring.set_password.assert_not_called()
        keyring.delete_password.assert_not_called()

    @patch.dict("sys.modules", {"keyring": MagicMock()})
    def test_backend_initialization_error_is_unavailable(self) -> None:
        keyring = sys.modules["keyring"]
        keyring.get_keyring.return_value = LockedPriorityBackend()

        self.assertFalse(SecretStore.persistent_available())


if __name__ == "__main__":
    unittest.main()
