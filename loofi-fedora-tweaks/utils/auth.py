"""Authentication utilities for Loofi Web API."""

import logging
import os
import secrets
import time
from pathlib import Path
from typing import Optional

import bcrypt
import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from utils.config_manager import ConfigManager

logger = logging.getLogger(__name__)


class AuthManager:
    """Manage API auth credentials and JWT verification."""

    _ALGORITHM = "HS256"
    _CONFIG_KEY = "api_auth"
    _CONFIG_FILE = "api_auth.json"
    _SCHEMA_VERSION = 1
    _TOKEN_LIFETIME_SECONDS = 3600
    _PRIVATE_FILE_MODE = 0o600

    security = HTTPBearer(auto_error=False)

    @classmethod
    def _auth_path(cls) -> Path:
        return ConfigManager.CONFIG_DIR / cls._CONFIG_FILE

    @classmethod
    def _ensure_secret(cls, data: dict) -> dict:
        if not data.get("jwt_secret"):
            data["jwt_secret"] = secrets.token_hex(32)
        return data

    @classmethod
    def _normalize_auth_data(cls, data: object) -> dict:
        if not isinstance(data, dict):
            raise ValueError("Stored API auth data is invalid")

        normalized: dict[str, str | int] = {"schema_version": cls._SCHEMA_VERSION}

        jwt_secret = data.get("jwt_secret")
        if jwt_secret is not None:
            if not isinstance(jwt_secret, str) or not jwt_secret.strip():
                raise ValueError("Stored API auth secret is invalid")
            normalized["jwt_secret"] = jwt_secret

        api_key_hash = data.get("api_key_hash")
        if api_key_hash is not None:
            if not isinstance(api_key_hash, str) or not api_key_hash.strip():
                raise ValueError("Stored API key hash is invalid")
            normalized["api_key_hash"] = api_key_hash

        return cls._ensure_secret(normalized)

    @classmethod
    def _validate_auth_permissions(cls, path: Path) -> None:
        if os.name == "nt" or not path.exists():
            return

        try:
            mode = path.stat().st_mode & 0o777
        except OSError as e:
            raise RuntimeError("Failed to inspect API auth storage permissions") from e

        if mode & 0o077:
            raise PermissionError("API auth storage must use owner-only permissions")

    @classmethod
    def _load_legacy_auth_data(cls) -> Optional[dict]:
        config = ConfigManager.load_config() or {}
        legacy_data = config.get(cls._CONFIG_KEY)
        if legacy_data is None:
            return None

        return cls._normalize_auth_data(legacy_data)

    @classmethod
    def _load_auth_data(cls) -> dict:
        ConfigManager.ensure_dirs()
        auth_path = cls._auth_path()
        stored_data = ConfigManager.load_json_file(auth_path)

        if stored_data is not None:
            cls._validate_auth_permissions(auth_path)
            return cls._normalize_auth_data(stored_data)

        if auth_path.exists():
            raise ValueError("Stored API auth data is invalid")

        legacy_data = cls._load_legacy_auth_data()
        if legacy_data is not None:
            cls._save_auth_data(legacy_data)
            return legacy_data

        return cls._ensure_secret({"schema_version": cls._SCHEMA_VERSION})

    @classmethod
    def _save_auth_data(cls, data: dict) -> None:
        ConfigManager.ensure_dirs()
        normalized = cls._normalize_auth_data(data)
        auth_path = cls._auth_path()

        if not ConfigManager.save_json_file(
            auth_path,
            normalized,
            permissions=cls._PRIVATE_FILE_MODE,
        ):
            raise OSError("Failed to persist API auth data")

        config = ConfigManager.load_config() or {}
        if config.pop(cls._CONFIG_KEY, None) is not None:
            ConfigManager.save_config(config)

    @classmethod
    def _hash_key(cls, api_key: str) -> str:
        result = bcrypt.hashpw(api_key.encode("utf-8"), bcrypt.gensalt())  # type: ignore[no-any-return]
        return str(result.decode("utf-8"))

    @classmethod
    def generate_api_key(cls) -> str:
        """Generate and store a new API key."""
        api_key = secrets.token_urlsafe(32)
        data = cls._load_auth_data()
        data["api_key_hash"] = cls._hash_key(api_key)
        data = cls._ensure_secret(data)
        cls._save_auth_data(data)
        return api_key

    @classmethod
    def issue_token(cls, api_key: str) -> str:
        """Issue a JWT for a valid API key."""
        data = cls._load_auth_data()
        stored_hash = data.get("api_key_hash")
        if not stored_hash or not bcrypt.checkpw(
            api_key.encode("utf-8"), stored_hash.encode("utf-8")
        ):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid API key"
            )
        payload = {
            "sub": "loofi-api",
            "exp": int(time.time()) + cls._TOKEN_LIFETIME_SECONDS,
        }
        return str(jwt.encode(payload, data["jwt_secret"], algorithm=cls._ALGORITHM))

    @classmethod
    def bootstrap_pending(cls) -> bool:
        """Return True when no API key has been provisioned yet."""
        data = cls._load_auth_data()
        return not bool(data.get("api_key_hash"))

    @classmethod
    def verify_token(cls, token: str) -> None:
        data = cls._load_auth_data()
        try:
            jwt.decode(token, data["jwt_secret"], algorithms=[cls._ALGORITHM])
        except (jwt.InvalidTokenError, KeyError, ValueError) as e:
            logger.debug("JWT token verification failed: %s", e)
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token"
            )

    @classmethod
    def verify_bearer_token(
        cls,
        credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    ) -> str:
        if not credentials or credentials.scheme.lower() != "bearer":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing bearer token"
            )
        cls.verify_token(credentials.credentials)
        return str(credentials.credentials)
