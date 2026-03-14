"""Safe Mode guard for mutating API execution."""

import logging
from typing import Optional

from utils.settings import SettingsManager

logger = logging.getLogger(__name__)


class SafeModeManager:
    """Manage persisted Safe Mode state and mutation guard decisions."""

    _SETTING_KEY = "safe_mode_enabled"
    _READ_ONLY_COMMANDS = frozenset(
        {
            "hostnamectl",
            "uname",
            "lsblk",
            "df",
            "free",
            "uptime",
            "sensors",
            "lspci",
            "lsusb",
            "ip",
            "ss",
            "journalctl",
            "rpm",
        }
    )

    @classmethod
    def is_enabled(cls, settings_manager: Optional[SettingsManager] = None) -> bool:
        """Return the persisted Safe Mode state, defaulting to enabled."""
        manager = settings_manager or SettingsManager.instance()
        try:
            return bool(manager.get(cls._SETTING_KEY))
        except KeyError:
            logger.warning("Safe Mode setting missing; defaulting to enabled")
            return True

    @classmethod
    def set_enabled(
        cls,
        enabled: bool,
        settings_manager: Optional[SettingsManager] = None,
    ) -> None:
        """Persist Safe Mode state."""
        manager = settings_manager or SettingsManager.instance()
        manager.set(cls._SETTING_KEY, bool(enabled))
        manager.save()

    @classmethod
    def is_mutating_command(cls, command: str, pkexec: bool = False) -> bool:
        """Return True when a command should be treated as mutating."""
        if pkexec:
            return True
        return command not in cls._READ_ONLY_COMMANDS

    @classmethod
    def mutation_refusal_message(cls, command: str) -> str:
        """Return the standardized refusal message for blocked mutations."""
        return (
            "Safe Mode is enabled and blocks mutating API execution for "
            f"'{command}'. Disable Safe Mode in settings to run write actions."
        )

    @classmethod
    def allow_api_execution(
        cls,
        command: str,
        *,
        preview: bool,
        pkexec: bool = False,
        settings_manager: Optional[SettingsManager] = None,
    ) -> bool:
        """Return True when the API request is allowed to execute."""
        if preview:
            return True

        if not cls.is_mutating_command(command, pkexec=pkexec):
            return True

        return not cls.is_enabled(settings_manager=settings_manager)
