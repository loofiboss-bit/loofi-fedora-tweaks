"""Authentication utilities for Loofi Web API."""

import logging
import secrets
from typing import Optional

import bcrypt
import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from utils.config_manager import ConfigManager
from core.secrets import SecretStore

logger = logging.getLogger(__name__)


class AuthManager:
    """Manage API auth credentials and JWT verification."""

    _ALGORITHM = "HS256"
    _CONFIG_KEY = "api_auth"
    _TOKEN_LIFETIME_SECONDS = 3600
    _JWT_ACCOUNT = "web-api-jwt-secret"

    security = HTTPBearer(auto_error=False)

    @classmethod
    def _ensure_secret(cls, data: dict) -> dict:
        legacy = str(data.get("jwt_secret", ""))
        if legacy:
            persistent = SecretStore.get_persistent(cls._JWT_ACCOUNT)
            if not persistent:
                result = SecretStore.set(cls._JWT_ACCOUNT, legacy)
                persistent = (
                    SecretStore.get_persistent(cls._JWT_ACCOUNT)
                    if result.success and result.persistent
                    else None
                )
            if persistent:
                data.pop("jwt_secret", None)
        if not SecretStore.get(cls._JWT_ACCOUNT):
            SecretStore.set(cls._JWT_ACCOUNT, secrets.token_hex(32))
        return data

    @classmethod
    def _jwt_secret(cls) -> str:
        value = SecretStore.get(cls._JWT_ACCOUNT)
        if value:
            return value
        result = SecretStore.set(cls._JWT_ACCOUNT, secrets.token_hex(32))
        value = SecretStore.get(cls._JWT_ACCOUNT)
        if not result.success or not value:
            raise RuntimeError("Web API secret storage is unavailable.")
        return value

    @classmethod
    def _load_auth_data(cls) -> dict:
        ConfigManager.ensure_dirs()
        config = ConfigManager.load_config() or {}
        raw = config.get(cls._CONFIG_KEY, {})
        data = dict(raw) if isinstance(raw, dict) else {}
        had_legacy_secret = bool(data.get("jwt_secret"))
        data = cls._ensure_secret(data)
        if had_legacy_secret and "jwt_secret" not in data:
            config[cls._CONFIG_KEY] = data
            ConfigManager.save_config(config)
        return data

    @classmethod
    def _save_auth_data(cls, data: dict) -> None:
        ConfigManager.ensure_dirs()
        config = ConfigManager.load_config() or {}
        config[cls._CONFIG_KEY] = data
        ConfigManager.save_config(config)

    @classmethod
    def _hash_key(cls, api_key: str) -> str:
        result = bcrypt.hashpw(api_key.encode("utf-8"), bcrypt.gensalt())  # type: ignore[no-any-return]
        return str(result.decode("utf-8"))

    @classmethod
    def generate_api_key(cls) -> str:
        """Rotate and return a new API key exactly once."""
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
            "exp": int(__import__("time").time()) + cls._TOKEN_LIFETIME_SECONDS,
        }
        return str(jwt.encode(payload, cls._jwt_secret(), algorithm=cls._ALGORITHM))

    @classmethod
    def verify_token(cls, token: str) -> None:
        try:
            jwt.decode(token, cls._jwt_secret(), algorithms=[cls._ALGORITHM])
        except (jwt.InvalidTokenError, KeyError, ValueError) as e:
            logger.debug("JWT token verification failed: %s", e)
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token"
            )

    @classmethod
    def revoke_api_key(cls) -> None:
        """Revoke API-key authentication and invalidate issued JWTs."""
        data = cls._load_auth_data()
        data.pop("api_key_hash", None)
        SecretStore.delete(cls._JWT_ACCOUNT)
        SecretStore.set(cls._JWT_ACCOUNT, secrets.token_hex(32))
        cls._save_auth_data(data)

    @classmethod
    def has_api_key(cls) -> bool:
        return bool(cls._load_auth_data().get("api_key_hash"))

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
