"""
Quick Actions Config — v31.0 Smart UX
Configurable quick actions grid for the Dashboard tab.
"""

import json
import logging
import os
from typing import Dict, List

from core.navigation.migrations import migrate_quick_action, migrate_quick_actions

logger = logging.getLogger(__name__)

_CONFIG_DIR = os.path.expanduser("~/.config/loofi-fedora-tweaks")
_ACTIONS_FILE = os.path.join(_CONFIG_DIR, "quick_actions.json")


class QuickActionsConfig:
    """Manages configurable quick actions for the Dashboard."""

    @staticmethod
    def default_actions() -> List[Dict[str, str]]:
        """
        Return the default quick actions.

        Returns:
            List of action dictionaries with id, label, icon, color, route_id.
        """
        return [
            {
                "id": "clean_cache",
                "label": "Clean Cache",
                "icon": "cleanup",
                "color": "#e8b84d",
                "route_id": "maintenance:cleanup",
            },
            {
                "id": "update_all",
                "label": "Update All",
                "icon": "update",
                "color": "#39c5cf",
                "route_id": "maintenance:updates",
            },
            {
                "id": "power_profile",
                "label": "Power Profile",
                "icon": "hardware-performance",
                "color": "#3dd68c",
                "route_id": "hardware",
            },
            {
                "id": "gaming_mode",
                "label": "Gaming Mode",
                "icon": "cpu-performance",
                "color": "#e8556d",
                "route_id": "gaming",
            },
        ]

    @staticmethod
    def _normalize_action(action: Dict[str, str]) -> Dict[str, str]:
        """Return an action using route_id, migrating legacy target_tab values."""
        return migrate_quick_action(action)

    @classmethod
    def get_actions(cls) -> List[Dict[str, str]]:
        """
        Load configured quick actions from disk.
        Falls back to defaults if no config exists.

        Returns:
            List of action dictionaries.
        """
        try:
            if os.path.isfile(_ACTIONS_FILE):
                with open(_ACTIONS_FILE, "r") as f:
                    data = json.load(f)
                if isinstance(data, list) and len(data) > 0:
                    normalized = migrate_quick_actions(data)
                    if normalized != data:
                        cls.set_actions(normalized)
                    return normalized
        except (OSError, json.JSONDecodeError) as e:
            logger.warning("Failed to load quick actions config: %s", e)
        return cls.default_actions()

    @classmethod
    def set_actions(cls, actions: List[Dict[str, str]]) -> None:
        """
        Save quick actions configuration to disk.

        Args:
            actions: List of action dictionaries to save.
        """
        try:
            os.makedirs(_CONFIG_DIR, exist_ok=True)
            with open(_ACTIONS_FILE, "w") as f:
                normalized = [cls._normalize_action(item) for item in actions]
                json.dump(normalized, f, indent=2)
        except (OSError, json.JSONDecodeError) as e:
            logger.warning("Failed to save quick actions config: %s", e)

    @classmethod
    def reset_to_defaults(cls) -> List[Dict[str, str]]:
        """
        Reset quick actions to defaults and save.

        Returns:
            The default actions list.
        """
        defaults = cls.default_actions()
        cls.set_actions(defaults)
        return defaults

    @staticmethod
    def validate_action(action: dict) -> bool:
        """
        Validate that an action dict has all required fields.

        Args:
            action: Action dictionary to validate.

        Returns:
            True if valid, False otherwise.
        """
        normalized = QuickActionsConfig._normalize_action(action)
        required = {"id", "label", "icon", "color", "route_id"}
        return required.issubset(normalized.keys())
