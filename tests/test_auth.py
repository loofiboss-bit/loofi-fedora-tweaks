"""Tests for utils/auth.py — AuthManager JWT and API key operations."""

import sys
import os
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'loofi-fedora-tweaks'))

# Pre-mock optional dependencies that may not be installed in test environments
# Create real exception classes for assertRaises compatibility


class _MockHTTPException(Exception):
    def __init__(self, status_code=500, detail=None):
        self.status_code = status_code
        self.detail = detail
        super().__init__(detail)


class _MockInvalidTokenError(Exception):
    pass


_fastapi_mock = MagicMock()
_fastapi_mock.HTTPException = _MockHTTPException
_fastapi_mock.Depends = lambda x: x
_fastapi_mock.status = MagicMock(HTTP_401_UNAUTHORIZED=401)

_jwt_mock = MagicMock()
_jwt_mock.InvalidTokenError = _MockInvalidTokenError

for _mod in [
    'bcrypt',
    'PyQt6', 'PyQt6.QtCore', 'PyQt6.QtWidgets', 'PyQt6.QtGui',
    'PyQt6.QtNetwork', 'PyQt6.QtSvg', 'PyQt6.QtSvgWidgets',
]:
    if _mod not in sys.modules:
        sys.modules[_mod] = MagicMock()

if 'fastapi' not in sys.modules:
    sys.modules['fastapi'] = _fastapi_mock
else:
    sys.modules['fastapi'].HTTPException = _MockHTTPException
    sys.modules['fastapi'].Depends = lambda x: x
    sys.modules['fastapi'].status.HTTP_401_UNAUTHORIZED = 401
if 'fastapi.security' not in sys.modules:
    sys.modules['fastapi.security'] = MagicMock()
if 'jwt' not in sys.modules:
    sys.modules['jwt'] = _jwt_mock

from utils.auth import AuthManager  # noqa: E402


class TestAuthManagerHashKey(unittest.TestCase):
    """Tests for _hash_key bcrypt operations."""

    @patch('utils.auth.bcrypt')
    def test_hash_key_returns_string(self, mock_bcrypt):
        mock_bcrypt.gensalt.return_value = b'$2b$12$salt'
        mock_bcrypt.hashpw.return_value = b'$2b$12$hashedkey'
        result = AuthManager._hash_key("test-api-key")
        self.assertIsInstance(result, str)
        mock_bcrypt.hashpw.assert_called_once()

    @patch('utils.auth.bcrypt')
    def test_hash_key_encodes_utf8(self, mock_bcrypt):
        mock_bcrypt.gensalt.return_value = b'$2b$12$salt'
        mock_bcrypt.hashpw.return_value = b'$2b$12$hash'
        AuthManager._hash_key("my-key")
        call_args = mock_bcrypt.hashpw.call_args
        self.assertEqual(call_args[0][0], b"my-key")


class TestAuthManagerEnsureSecret(unittest.TestCase):
    """Tests for _ensure_secret method."""

    def test_generates_secret_when_missing(self):
        data = {}
        result = AuthManager._ensure_secret(data)
        self.assertIn("jwt_secret", result)
        self.assertGreater(len(result["jwt_secret"]), 0)

    def test_preserves_existing_secret(self):
        data = {"jwt_secret": "existing-secret-value"}
        result = AuthManager._ensure_secret(data)
        self.assertEqual(result["jwt_secret"], "existing-secret-value")

    def test_replaces_empty_string_secret(self):
        data = {"jwt_secret": ""}
        result = AuthManager._ensure_secret(data)
        self.assertNotEqual(result["jwt_secret"], "")


class TestAuthManagerLoadSave(unittest.TestCase):
    """Tests for _load_auth_data and _save_auth_data."""

    def _configure_auth_path(self, mock_cm, exists=False, mode=0o600):
        auth_path = MagicMock(spec=Path)
        auth_path.exists.return_value = exists
        auth_path.stat.return_value = MagicMock(st_mode=mode)
        mock_cm.CONFIG_DIR = MagicMock()
        mock_cm.CONFIG_DIR.__truediv__ = MagicMock(return_value=auth_path)
        return auth_path

    @patch('utils.auth.ConfigManager')
    def test_load_auth_data_creates_dirs(self, mock_cm):
        self._configure_auth_path(mock_cm, exists=False)
        mock_cm.load_json_file.return_value = None
        mock_cm.load_config.return_value = {}
        AuthManager._load_auth_data()
        mock_cm.ensure_dirs.assert_called_once()

    @patch('utils.auth.ConfigManager')
    def test_load_auth_data_returns_dict(self, mock_cm):
        auth_path = self._configure_auth_path(mock_cm, exists=True)
        mock_cm.load_json_file.return_value = {"jwt_secret": "test-secret"}
        result = AuthManager._load_auth_data()
        self.assertIsInstance(result, dict)
        self.assertEqual(result["jwt_secret"], "test-secret")
        mock_cm.load_json_file.assert_called_once_with(auth_path)

    @patch('utils.auth.ConfigManager')
    def test_load_auth_data_handles_none_config(self, mock_cm):
        self._configure_auth_path(mock_cm, exists=False)
        mock_cm.load_json_file.return_value = None
        mock_cm.load_config.return_value = None
        result = AuthManager._load_auth_data()
        self.assertIsInstance(result, dict)
        self.assertIn("jwt_secret", result)

    @patch('utils.auth.ConfigManager')
    def test_load_auth_data_migrates_legacy_config(self, mock_cm):
        auth_path = self._configure_auth_path(mock_cm, exists=False)
        mock_cm.load_json_file.return_value = None
        mock_cm.load_config.side_effect = [
            {"api_auth": {"jwt_secret": "legacy-secret", "api_key_hash": "legacy-hash"}},
            {"api_auth": {"jwt_secret": "legacy-secret", "api_key_hash": "legacy-hash"}},
        ]
        mock_cm.save_json_file.return_value = True

        result = AuthManager._load_auth_data()

        self.assertEqual(result["jwt_secret"], "legacy-secret")
        self.assertEqual(result["api_key_hash"], "legacy-hash")
        mock_cm.save_json_file.assert_called_once_with(
            auth_path,
            {
                "schema_version": AuthManager._SCHEMA_VERSION,
                "jwt_secret": "legacy-secret",
                "api_key_hash": "legacy-hash",
            },
            permissions=AuthManager._PRIVATE_FILE_MODE,
        )
        mock_cm.save_config.assert_called_once_with({})

    @patch('utils.auth.os.name', 'posix')
    @patch('utils.auth.ConfigManager')
    def test_load_auth_data_rejects_world_readable_auth_file(self, mock_cm):
        self._configure_auth_path(mock_cm, exists=True, mode=0o644)
        mock_cm.load_json_file.return_value = {"jwt_secret": "test-secret"}

        with self.assertRaises(PermissionError):
            AuthManager._load_auth_data()

    @patch('utils.auth.ConfigManager')
    def test_save_auth_data_writes_private_json(self, mock_cm):
        auth_path = self._configure_auth_path(mock_cm, exists=False)
        mock_cm.load_config.return_value = {"api_auth": {"jwt_secret": "old-secret"}, "other": True}
        mock_cm.save_json_file.return_value = True
        data = {"jwt_secret": "s", "api_key_hash": "h"}
        AuthManager._save_auth_data(data)
        mock_cm.save_json_file.assert_called_once_with(
            auth_path,
            {
                "schema_version": AuthManager._SCHEMA_VERSION,
                "jwt_secret": "s",
                "api_key_hash": "h",
            },
            permissions=AuthManager._PRIVATE_FILE_MODE,
        )
        mock_cm.save_config.assert_called_once_with({"other": True})

    @patch('utils.auth.ConfigManager')
    def test_save_auth_data_handles_write_error(self, mock_cm):
        self._configure_auth_path(mock_cm, exists=False)
        mock_cm.save_json_file.return_value = False

        with self.assertRaises(OSError):
            AuthManager._save_auth_data({"jwt_secret": "s"})


class TestAuthManagerGenerateApiKey(unittest.TestCase):
    """Tests for generate_api_key."""

    @patch.object(AuthManager, '_save_auth_data')
    @patch.object(AuthManager, '_load_auth_data')
    @patch('utils.auth.bcrypt')
    def test_generate_api_key_returns_string(self, mock_bcrypt, mock_load, mock_save):
        mock_load.return_value = {"jwt_secret": "test"}
        mock_bcrypt.gensalt.return_value = b'$2b$12$salt'
        mock_bcrypt.hashpw.return_value = b'$2b$12$hash'
        key = AuthManager.generate_api_key()
        self.assertIsInstance(key, str)
        self.assertGreater(len(key), 20)

    @patch.object(AuthManager, '_save_auth_data')
    @patch.object(AuthManager, '_load_auth_data')
    @patch('utils.auth.bcrypt')
    def test_generate_api_key_saves_hash(self, mock_bcrypt, mock_load, mock_save):
        mock_load.return_value = {"jwt_secret": "test"}
        mock_bcrypt.gensalt.return_value = b'$2b$12$salt'
        mock_bcrypt.hashpw.return_value = b'$2b$12$hashed'
        AuthManager.generate_api_key()
        mock_save.assert_called_once()
        saved_data = mock_save.call_args[0][0]
        self.assertIn("api_key_hash", saved_data)


class TestAuthManagerIssueToken(unittest.TestCase):
    """Tests for issue_token JWT generation."""

    @patch.object(AuthManager, '_load_auth_data')
    @patch('utils.auth.bcrypt')
    @patch('utils.auth.jwt')
    def test_issue_token_success(self, mock_jwt, mock_bcrypt, mock_load):
        mock_load.return_value = {
            "jwt_secret": "secret123",
            "api_key_hash": "$2b$12$validhash",
        }
        mock_bcrypt.checkpw.return_value = True
        mock_jwt.encode.return_value = "jwt.token.value"
        token = AuthManager.issue_token("valid-key")
        self.assertEqual(token, "jwt.token.value")
        mock_jwt.encode.assert_called_once()

    @patch.object(AuthManager, '_load_auth_data')
    @patch('utils.auth.bcrypt')
    def test_issue_token_invalid_key_raises_401(self, mock_bcrypt, mock_load):
        mock_load.return_value = {
            "jwt_secret": "secret123",
            "api_key_hash": "$2b$12$validhash",
        }
        mock_bcrypt.checkpw.return_value = False
        with self.assertRaises(Exception) as ctx:
            AuthManager.issue_token("wrong-key")
        self.assertEqual(getattr(ctx.exception, "status_code", None), 401)

    @patch.object(AuthManager, '_load_auth_data')
    def test_issue_token_no_stored_hash_raises_401(self, mock_load):
        mock_load.return_value = {"jwt_secret": "secret123"}
        with self.assertRaises(Exception) as ctx:
            AuthManager.issue_token("any-key")
        self.assertEqual(getattr(ctx.exception, "status_code", None), 401)


class TestAuthManagerVerifyToken(unittest.TestCase):
    """Tests for verify_token JWT verification."""

    @patch.object(AuthManager, '_load_auth_data')
    @patch('utils.auth.jwt')
    def test_verify_token_success(self, mock_jwt, mock_load):
        mock_load.return_value = {"jwt_secret": "secret"}
        mock_jwt.decode.return_value = {"sub": "loofi-api"}
        # Should not raise
        AuthManager.verify_token("valid-token")
        mock_jwt.decode.assert_called_once()

    @patch.object(AuthManager, '_load_auth_data')
    @patch('utils.auth.jwt')
    def test_verify_token_expired_raises_401(self, mock_jwt, mock_load):
        mock_load.return_value = {"jwt_secret": "secret"}
        mock_jwt.decode.side_effect = _MockInvalidTokenError("expired")
        mock_jwt.InvalidTokenError = _MockInvalidTokenError
        with self.assertRaises(Exception) as ctx:
            AuthManager.verify_token("expired-token")
        self.assertEqual(getattr(ctx.exception, "status_code", None), 401)

    @patch.object(AuthManager, '_load_auth_data')
    @patch('utils.auth.jwt')
    def test_verify_token_malformed_raises_401(self, mock_jwt, mock_load):
        mock_load.return_value = {"jwt_secret": "secret"}
        mock_jwt.InvalidTokenError = _MockInvalidTokenError
        mock_jwt.decode.side_effect = ValueError("bad format")
        with self.assertRaises(Exception) as ctx:
            AuthManager.verify_token("garbage")
        self.assertEqual(getattr(ctx.exception, "status_code", None), 401)


class TestAuthManagerVerifyBearerToken(unittest.TestCase):
    """Tests for verify_bearer_token FastAPI dependency."""

    @patch.object(AuthManager, 'verify_token')
    def test_verify_bearer_success(self, mock_verify):
        creds = MagicMock()
        creds.scheme = "Bearer"
        creds.credentials = "valid-jwt"
        result = AuthManager.verify_bearer_token(creds)
        self.assertEqual(result, "valid-jwt")
        mock_verify.assert_called_once_with("valid-jwt")

    def test_verify_bearer_missing_creds_raises_401(self):
        with self.assertRaises(Exception) as ctx:
            AuthManager.verify_bearer_token(None)
        self.assertEqual(getattr(ctx.exception, "status_code", None), 401)

    def test_verify_bearer_wrong_scheme_raises_401(self):
        creds = MagicMock()
        creds.scheme = "Basic"
        with self.assertRaises(Exception) as ctx:
            AuthManager.verify_bearer_token(creds)
        self.assertEqual(getattr(ctx.exception, "status_code", None), 401)


class TestAuthManagerAuthPath(unittest.TestCase):
    """Tests for _auth_path configuration."""

    @patch('utils.auth.ConfigManager')
    def test_auth_path_uses_config_dir(self, mock_cm):
        mock_cm.CONFIG_DIR = MagicMock()
        expected = MagicMock()
        mock_cm.CONFIG_DIR.__truediv__ = MagicMock(return_value=expected)
        path = AuthManager._auth_path()
        self.assertIsNotNone(path)


class TestAuthManagerBootstrapPending(unittest.TestCase):
    """Tests for bootstrap_pending helper."""

    @patch.object(AuthManager, '_load_auth_data')
    def test_bootstrap_pending_true_without_hash(self, mock_load):
        mock_load.return_value = {"jwt_secret": "secret"}

        self.assertTrue(AuthManager.bootstrap_pending())

    @patch.object(AuthManager, '_load_auth_data')
    def test_bootstrap_pending_false_with_hash(self, mock_load):
        mock_load.return_value = {"jwt_secret": "secret", "api_key_hash": "hash"}

        self.assertFalse(AuthManager.bootstrap_pending())


if __name__ == "__main__":
    unittest.main()
