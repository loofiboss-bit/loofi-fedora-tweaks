"""English-only locale contract for the desktop application."""

import logging
import os
from typing import List

logger = logging.getLogger(__name__)

# Translation directory relative to package root
_TRANSLATIONS_DIR = os.path.join(
    os.path.dirname(os.path.dirname(__file__)), "resources", "translations"
)


class I18nManager:
    """Keep legacy callers on the single supported English locale."""

    _current_locale: str = "en"
    _translator = None

    @staticmethod
    def translations_dir() -> str:
        """Return the path to the translations directory."""
        return _TRANSLATIONS_DIR

    @staticmethod
    def available_locales() -> List[str]:
        """Return the only supported application locale."""
        return ["en"]

    @classmethod
    def get_locale(cls) -> str:
        """Return the current locale code."""
        return cls._current_locale

    @classmethod
    def set_locale(cls, app, locale: str) -> bool:
        """Accept English and reject unsupported locale requests."""
        if cls._translator is not None:
            app.removeTranslator(cls._translator)
            cls._translator = None
        cls._current_locale = "en"
        if locale != "en":
            logger.warning("Unsupported application locale requested: %s", locale)
            return False
        return True

    @staticmethod
    def get_preferred_locale() -> str:
        """Return English regardless of stale persisted locale values."""
        return "en"

    @staticmethod
    def save_preferred_locale(locale: str) -> None:
        """Persist the supported English locale for legacy callers."""
        try:
            import json

            config_dir = os.path.expanduser("~/.config/loofi-fedora-tweaks")
            config_path = os.path.join(config_dir, "settings.json")

            settings = {}
            if os.path.isfile(config_path):
                with open(config_path, "r") as f:
                    settings = json.load(f)

            settings["locale"] = "en"
            os.makedirs(config_dir, exist_ok=True)
            with open(config_path, "w") as f:
                json.dump(settings, f, indent=2)
        except (OSError, json.JSONDecodeError) as e:
            logger.warning("Failed to save locale preference: %s", e)
