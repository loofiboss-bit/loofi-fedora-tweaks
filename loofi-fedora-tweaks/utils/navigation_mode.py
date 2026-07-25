"""Compatibility persistence for the v20 unified navigation surface."""

from core.navigation.migrations import navigation_mode_from_value
from core.navigation.models import NavigationMode
from utils.log import get_logger
from utils.settings import SettingsManager

logger = get_logger(__name__)


class NavigationModeManager:
    """Normalize legacy mode callers to the unified Specialist Tools surface."""

    @staticmethod
    def get_mode() -> NavigationMode:
        """Return the v20 unified navigation surface.

        Persisted values remain readable for migration compatibility, but no
        longer hide product areas.
        """
        return NavigationMode.ADVANCED

    @staticmethod
    def set_mode(mode: NavigationMode) -> None:
        """Keep the compatibility API while normalizing to unified navigation."""
        navigation_mode_from_value(mode)
        mgr = SettingsManager.instance()
        mgr.set("navigation_mode", NavigationMode.ADVANCED.value)
        mgr.save()
        logger.info("Navigation mode normalized to %s", NavigationMode.ADVANCED.value)
