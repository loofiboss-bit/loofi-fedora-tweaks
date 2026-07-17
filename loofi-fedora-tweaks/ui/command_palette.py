"""Compatibility adapter for the v15 global-search surface.

New code should use :mod:`ui.global_search`.  This module intentionally owns no
registry, filtering, activation, or execution behavior of its own.
"""

from collections.abc import Callable

from core.navigation import GlobalSearchModel, SearchResult
from PyQt6.QtWidgets import QWidget

from ui.global_search import GlobalSearchDialog


class CommandPalette(GlobalSearchDialog):
    """Legacy constructor backed by the single global-search implementation."""

    def __init__(
        self,
        on_action: Callable[[str], None],
        parent: QWidget | None = None,
    ) -> None:
        def navigate(result: SearchResult) -> None:
            on_action(result.route_id)

        super().__init__(GlobalSearchModel(), navigate, parent=parent)
