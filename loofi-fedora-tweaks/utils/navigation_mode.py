"""Persistence for the canonical v15 Standard/Advanced UI mode."""

from core.navigation.migrations import navigation_mode_from_value
from core.navigation.models import NavigationMode
from utils.log import get_logger
from utils.settings import SettingsManager

logger = get_logger(__name__)


class NavigationModeManager:
    """Read and write the sole post-migration navigation-mode source."""

    @staticmethod
    def get_mode() -> NavigationMode:
        mgr = SettingsManager.instance()
        raw = mgr.get("navigation_mode", NavigationMode.STANDARD.value)
        return navigation_mode_from_value(raw)

    @staticmethod
    def set_mode(mode: NavigationMode) -> None:
        canonical = navigation_mode_from_value(mode)
        mgr = SettingsManager.instance()
        mgr.set("navigation_mode", canonical.value)
        mgr.save()
        logger.info("Navigation mode set to %s", canonical.value)
