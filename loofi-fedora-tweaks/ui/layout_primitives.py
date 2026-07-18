"""Compatibility imports for the canonical :mod:`ui.components` library."""

from ui.components import (
    ActionBar,
    Card,
    ClickableCard,
    ContentColumn,
    PageHeader,
    PageScaffold,
)
from ui.components.layout import AdaptiveGrid, LayoutMetrics, make_page_title

ActionRow = ActionBar
Section = Card
RouteCard = ClickableCard

__all__ = [
    "ActionRow",
    "AdaptiveGrid",
    "ContentColumn",
    "LayoutMetrics",
    "PageHeader",
    "PageScaffold",
    "RouteCard",
    "Section",
    "make_page_title",
]
