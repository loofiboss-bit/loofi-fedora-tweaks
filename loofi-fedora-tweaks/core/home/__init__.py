"""PyQt-free composition contracts for the canonical Home surface."""

from __future__ import annotations

from typing import Any

from .models import (
    AttentionItem,
    HomeStatus,
    HomeSummary,
    HomeTask,
    RecentChange,
    Recommendation,
)
from .recommendations import recommendation_priority, select_primary_recommendation

__all__ = [
    "AttentionItem",
    "HomeService",
    "HomeStatus",
    "HomeSummary",
    "HomeTask",
    "RecentChange",
    "Recommendation",
    "recommendation_priority",
    "select_primary_recommendation",
]


def __getattr__(name: str) -> Any:
    """Keep persisted-data providers off the GUI import/startup path."""
    if name == "HomeService":
        from .service import HomeService

        return HomeService
    raise AttributeError(name)
