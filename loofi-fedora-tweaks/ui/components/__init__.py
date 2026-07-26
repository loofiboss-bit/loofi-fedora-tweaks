"""Canonical shared component library for the v16 presentation layer."""

from ui.components.actions import (
    ActionBar,
    DangerButton,
    GhostButton,
    PrimaryButton,
    SecondaryButton,
)
from ui.components.cards import Card, ClickableCard, DefinitionList, DefinitionRow
from ui.components.feedback import (
    ActionProgress,
    DetailsDisclosure,
    EmptyState,
    InlineNotice,
    LoadingState,
    StatusBadge,
    UnavailableState,
)
from ui.components.layout import (
    ContentColumn,
    PageHeader,
    PageScaffold,
)
from ui.components.navigation import (
    LocalViewItem,
    LocalViewSwitcher,
    SectionItem,
    SectionNavigator,
)

__all__ = [
    "ActionBar",
    "ActionProgress",
    "Card",
    "ClickableCard",
    "ContentColumn",
    "DangerButton",
    "DefinitionList",
    "DefinitionRow",
    "DetailsDisclosure",
    "EmptyState",
    "GhostButton",
    "InlineNotice",
    "LoadingState",
    "LocalViewItem",
    "LocalViewSwitcher",
    "PageHeader",
    "PageScaffold",
    "PrimaryButton",
    "SecondaryButton",
    "SectionItem",
    "SectionNavigator",
    "StatusBadge",
    "UnavailableState",
]
