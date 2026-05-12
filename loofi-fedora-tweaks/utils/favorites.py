"""
Favorites Manager — v31.0 Smart UX
Persists favorite/pinned tabs to JSON config.
"""

import json
import logging
import os
from typing import Iterable, List

logger = logging.getLogger(__name__)

_CONFIG_DIR = os.path.expanduser("~/.config/loofi-fedora-tweaks")
_FAVORITES_FILE = os.path.join(_CONFIG_DIR, "favorites.json")
_FAVORITES_VERSION = 2


class FavoritesManager:
    """Manages favorite/pinned tabs with JSON persistence."""

    @staticmethod
    def _stable_id(value: str) -> str:
        """Normalize a favorite value to the canonical route/plugin ID when known."""
        try:
            from core.navigation import resolve
        except ImportError:
            return value
        route = resolve(value)
        return route.id if route else ""

    @classmethod
    def _normalize_current_id(cls, value: str) -> str:
        """Return a stable ID for current favorite writes."""
        return cls._stable_id(str(value)) or str(value)

    @classmethod
    def _migrate_legacy(cls, values: Iterable[str]) -> List[str]:
        """Migrate legacy display-name-derived favorites into stable v2 IDs."""
        migrated: List[str] = []
        for value in values:
            stable_id = cls._stable_id(str(value))
            if not stable_id:
                logger.warning("Dropping stale legacy favorite: %s", value)
                continue
            if stable_id not in migrated:
                migrated.append(stable_id)
        return migrated

    @classmethod
    def _load(cls) -> List[str]:
        """Load favorites list from disk."""
        try:
            if os.path.isfile(_FAVORITES_FILE):
                with open(_FAVORITES_FILE, "r") as f:
                    data = json.load(f)
                if isinstance(data, list):
                    migrated = cls._migrate_legacy(data)
                    if migrated != data:
                        cls._save(migrated)
                    return migrated
                if isinstance(data, dict):
                    version = data.get("version")
                    favorites = data.get("favorites")
                    if version == _FAVORITES_VERSION and isinstance(favorites, list):
                        normalized: List[str] = []
                        for item in favorites:
                            stable_id = cls._stable_id(str(item)) or str(item)
                            if stable_id not in normalized:
                                normalized.append(stable_id)
                        if normalized != favorites:
                            cls._save(normalized)
                        return normalized
        except (OSError, json.JSONDecodeError) as e:
            logger.warning("Failed to load favorites: %s", e)
        return []

    @staticmethod
    def _save(favorites: List[str]) -> None:
        """Save favorites list to disk."""
        try:
            os.makedirs(_CONFIG_DIR, exist_ok=True)
            with open(_FAVORITES_FILE, "w") as f:
                json.dump({"version": _FAVORITES_VERSION, "favorites": favorites}, f, indent=2)
        except (OSError, json.JSONDecodeError) as e:
            logger.warning("Failed to save favorites: %s", e)

    @classmethod
    def get_favorites(cls) -> List[str]:
        """
        Get list of favorite tab IDs.

        Returns:
            List of tab ID strings.
        """
        return cls._load()

    @classmethod
    def add_favorite(cls, tab_id: str) -> None:
        """
        Add a tab to favorites.

        Args:
            tab_id: Plugin/tab ID to add.
        """
        favorites = cls._load()
        stable_id = cls._normalize_current_id(tab_id)
        if stable_id not in favorites:
            favorites.append(stable_id)
            cls._save(favorites)

    @classmethod
    def remove_favorite(cls, tab_id: str) -> None:
        """
        Remove a tab from favorites.

        Args:
            tab_id: Plugin/tab ID to remove.
        """
        favorites = cls._load()
        stable_id = cls._normalize_current_id(tab_id)
        if stable_id in favorites:
            favorites.remove(stable_id)
            cls._save(favorites)

    @classmethod
    def is_favorite(cls, tab_id: str) -> bool:
        """
        Check if a tab is in favorites.

        Args:
            tab_id: Plugin/tab ID to check.

        Returns:
            True if the tab is a favorite.
        """
        stable_id = cls._normalize_current_id(tab_id)
        return stable_id in cls._load()

    @classmethod
    def toggle_favorite(cls, tab_id: str) -> bool:
        """
        Toggle a tab's favorite status.

        Args:
            tab_id: Plugin/tab ID to toggle.

        Returns:
            True if tab is now a favorite, False if removed.
        """
        favorites = cls._load()
        stable_id = cls._normalize_current_id(tab_id)
        if stable_id in favorites:
            favorites.remove(stable_id)
            cls._save(favorites)
            return False
        else:
            favorites.append(stable_id)
            cls._save(favorites)
            return True
