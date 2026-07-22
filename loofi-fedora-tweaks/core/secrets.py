"""Secret Service backed credential storage with session-only fallback."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import ClassVar

from core.state.atomic_io import durable_unlink

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class SecretWriteResult:
    success: bool
    persistent: bool
    message: str


class SecretStore:
    """Store credentials in the desktop keyring, never a plaintext fallback."""

    SERVICE: ClassVar[str] = "loofi-fedora-tweaks"
    _session: ClassVar[dict[str, str]] = {}

    @classmethod
    def _keyring(cls):
        try:
            import keyring  # type: ignore[import-not-found]

            backend = keyring.get_keyring()
            if float(getattr(backend, "priority", 0)) <= 0:
                return None
            return keyring
        except (ImportError, RuntimeError, TypeError, ValueError):
            return None

    @classmethod
    def persistent_available(cls) -> bool:
        return cls._keyring() is not None

    @classmethod
    def get_persistent(cls, account: str) -> str | None:
        """Read only from Secret Service, never from the session fallback."""
        keyring = cls._keyring()
        if keyring is not None:
            try:
                value = keyring.get_password(cls.SERVICE, account)
                if value:
                    return str(value)
            except (RuntimeError, OSError, ValueError) as exc:
                logger.debug("Secret Service read failed for %s: %s", account, exc)
        return None

    @classmethod
    def get(cls, account: str) -> str | None:
        persistent = cls.get_persistent(account)
        if persistent:
            return persistent
        return cls._session.get(account)

    @classmethod
    def set(cls, account: str, secret: str) -> SecretWriteResult:
        value = str(secret)
        if not account or not value:
            return SecretWriteResult(False, False, "Secret account and value are required.")
        keyring = cls._keyring()
        if keyring is not None:
            try:
                keyring.set_password(cls.SERVICE, account, value)
                if keyring.get_password(cls.SERVICE, account) == value:
                    cls._session.pop(account, None)
                    return SecretWriteResult(True, True, "Stored in Secret Service.")
                return SecretWriteResult(False, False, "Secret Service readback failed.")
            except (RuntimeError, OSError, ValueError) as exc:
                logger.debug("Secret Service write failed for %s: %s", account, exc)
        cls._session[account] = value
        return SecretWriteResult(True, False, "Secret Service is unavailable; stored for this session only.")

    @classmethod
    def delete(cls, account: str) -> bool:
        cls._session.pop(account, None)
        keyring = cls._keyring()
        if keyring is None:
            return True
        try:
            keyring.delete_password(cls.SERVICE, account)
        except keyring.errors.PasswordDeleteError:
            pass
        except (RuntimeError, OSError, ValueError) as exc:
            logger.debug("Secret Service delete failed for %s: %s", account, exc)
            return False
        return True

    @classmethod
    def migrate_plaintext(cls, account: str, path: Path) -> SecretWriteResult | None:
        """Migrate once; remove plaintext only after persistent readback."""
        if not path.exists():
            return None
        try:
            value = path.read_text(encoding="utf-8").strip()
        except OSError as exc:
            return SecretWriteResult(False, False, f"Could not read legacy credential: {exc}")
        if not value:
            return SecretWriteResult(False, False, "Legacy credential is empty.")
        result = cls.set(account, value)
        if result.success and result.persistent and cls.get_persistent(account) == value:
            try:
                durable_unlink(path)
            except OSError as exc:
                return SecretWriteResult(False, True, f"Credential migrated but legacy removal failed: {exc}")
        return result
