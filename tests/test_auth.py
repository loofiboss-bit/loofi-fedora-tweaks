"""Haven authentication and Secret Service contracts."""

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import MagicMock, patch

from fastapi import HTTPException

from core.secrets import SecretStore
from utils.auth import AuthManager


class TestAuthStorage(unittest.TestCase):
    def setUp(self):
        SecretStore._session.clear()

    def tearDown(self):
        SecretStore._session.clear()

    @patch("utils.auth.SecretStore")
    def test_legacy_jwt_secret_is_migrated_out_of_config(self, secret_store):
        secret_store.get.return_value = None
        secret_store.get_persistent.side_effect = [None, "legacy"]
        secret_store.set.return_value = MagicMock(success=True, persistent=True)
        data = {"jwt_secret": "legacy", "api_key_hash": "hash"}

        result = AuthManager._ensure_secret(data)

        self.assertNotIn("jwt_secret", result)
        secret_store.set.assert_any_call(AuthManager._JWT_ACCOUNT, "legacy")

    @patch("utils.auth.ConfigManager")
    @patch("utils.auth.SecretStore")
    def test_load_rewrites_plaintext_secret_only_as_non_secret_config(self, secret_store, config):
        secret_store.get.return_value = "stored"
        secret_store.get_persistent.return_value = "stored"
        config.load_config.return_value = {
            "api_auth": {"jwt_secret": "legacy", "api_key_hash": "hash"}
        }

        result = AuthManager._load_auth_data()

        self.assertEqual(result, {"api_key_hash": "hash"})
        saved = config.save_config.call_args.args[0]
        self.assertNotIn("jwt_secret", saved["api_auth"])

    @patch("utils.auth.ConfigManager")
    @patch("utils.auth.SecretStore")
    def test_load_keeps_plaintext_until_persistent_readback(self, secret_store, config):
        secret_store.get.return_value = "legacy"
        secret_store.get_persistent.return_value = None
        secret_store.set.return_value = MagicMock(success=True, persistent=False)
        config.load_config.return_value = {
            "api_auth": {"jwt_secret": "legacy", "api_key_hash": "hash"}
        }

        result = AuthManager._load_auth_data()

        self.assertEqual(result["jwt_secret"], "legacy")
        config.save_config.assert_not_called()

    @patch("utils.auth.ConfigManager")
    def test_auth_config_contains_hash_only(self, config):
        config.load_config.return_value = {}

        AuthManager._save_auth_data({"api_key_hash": "hash"})

        self.assertEqual(config.save_config.call_args.args[0]["api_auth"], {"api_key_hash": "hash"})


class TestApiKeyLifecycle(unittest.TestCase):
    @patch.object(AuthManager, "_save_auth_data")
    @patch.object(AuthManager, "_load_auth_data", return_value={})
    @patch.object(AuthManager, "_hash_key", return_value="hashed")
    def test_generate_rotates_api_key_hash(self, _hash, _load, save):
        api_key = AuthManager.generate_api_key()

        self.assertGreater(len(api_key), 20)
        self.assertEqual(save.call_args.args[0]["api_key_hash"], "hashed")

    @patch.object(AuthManager, "_save_auth_data")
    @patch.object(AuthManager, "_load_auth_data", return_value={"api_key_hash": "hashed"})
    @patch("utils.auth.SecretStore")
    def test_revoke_removes_hash_and_rotates_jwt_secret(self, secret_store, _load, save):
        AuthManager.revoke_api_key()

        self.assertNotIn("api_key_hash", save.call_args.args[0])
        secret_store.delete.assert_called_once_with(AuthManager._JWT_ACCOUNT)
        secret_store.set.assert_called_once()

    @patch.object(AuthManager, "_jwt_secret", return_value="jwt-secret")
    @patch.object(AuthManager, "_load_auth_data", return_value={"api_key_hash": "stored"})
    @patch("utils.auth.bcrypt.checkpw", return_value=True)
    @patch("utils.auth.jwt.encode", return_value="token")
    def test_issue_token_uses_secret_store_material(self, encode, _check, _load, _secret):
        self.assertEqual(AuthManager.issue_token("api-key"), "token")
        self.assertEqual(encode.call_args.args[1], "jwt-secret")

    @patch.object(AuthManager, "_load_auth_data", return_value={})
    def test_issue_token_requires_active_api_key(self, _load):
        with self.assertRaises(HTTPException) as context:
            AuthManager.issue_token("api-key")
        self.assertEqual(context.exception.status_code, 401)

    @patch.object(AuthManager, "_jwt_secret", return_value="jwt-secret")
    @patch.object(AuthManager, "_load_auth_data", return_value={})
    @patch("utils.auth.jwt.decode", return_value={"sub": "loofi-api"})
    def test_verify_token_uses_secret_store_material(self, decode, _load, _secret):
        AuthManager.verify_token("token")
        decode.assert_called_once_with("token", "jwt-secret", algorithms=["HS256"])

    def test_missing_bearer_token_is_rejected(self):
        with self.assertRaises(HTTPException) as context:
            AuthManager.verify_bearer_token(None)
        self.assertEqual(context.exception.status_code, 401)


class TestSecretStoreFallback(unittest.TestCase):
    def setUp(self):
        SecretStore._session.clear()

    def tearDown(self):
        SecretStore._session.clear()

    @patch.object(SecretStore, "_keyring", return_value=None)
    def test_missing_secret_service_uses_session_only(self, _keyring):
        result = SecretStore.set("account", "secret")

        self.assertTrue(result.success)
        self.assertFalse(result.persistent)
        self.assertEqual(SecretStore.get("account"), "secret")

    @patch.object(SecretStore, "_keyring")
    def test_verified_keyring_write_is_persistent(self, keyring_factory):
        keyring = MagicMock()
        keyring.get_password.return_value = "secret"
        keyring_factory.return_value = keyring

        result = SecretStore.set("account", "secret")

        self.assertTrue(result.persistent)
        keyring.set_password.assert_called_once_with(SecretStore.SERVICE, "account", "secret")

    @patch.object(SecretStore, "_keyring")
    def test_plaintext_is_removed_only_after_persistent_readback(self, keyring_factory):
        keyring = MagicMock()
        keyring.get_password.return_value = "legacy-secret"
        keyring_factory.return_value = keyring
        with TemporaryDirectory() as directory:
            path = Path(directory) / "token"
            path.write_text("legacy-secret")

            result = SecretStore.migrate_plaintext("account", path)

            self.assertTrue(result and result.persistent)
            self.assertFalse(path.exists())

    @patch.object(SecretStore, "_keyring", return_value=None)
    def test_session_migration_preserves_plaintext_for_recovery(self, _keyring):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "token"
            path.write_text("legacy-secret")

            result = SecretStore.migrate_plaintext("account", path)

            self.assertTrue(result and not result.persistent)
            self.assertTrue(path.exists())


if __name__ == "__main__":
    unittest.main()
