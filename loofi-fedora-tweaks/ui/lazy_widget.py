"""
Lazy loading widget for deferred tab initialization.
Part of v7.1 performance optimization.
"""

import logging
from typing import Callable

from PyQt6.QtWidgets import QVBoxLayout, QWidget

from ui.shared_states import LoadingState, UnavailableState

logger = logging.getLogger(__name__)


class LazyWidget(QWidget):
    """
    A placeholder widget that defers loading of the actual widget
    until the tab is first shown. This reduces startup time by
    avoiding import and initialization of all tabs at once.
    """

    def __init__(self, loader_fn: Callable[[], QWidget], loading_text: str = "Loading..."):
        """
        Initialize the lazy widget.

        Args:
            loader_fn: A callable that returns the actual widget when invoked.
                       This function should handle the import and instantiation.
            loading_text: Text to show while loading (briefly visible).
        """
        super().__init__()
        self.loader_fn = loader_fn
        self.real_widget: QWidget | None = None
        self.load_error: str | None = None
        self._loaded = False

        # Minimal placeholder layout
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(0)

        # Loading indicator (shown briefly)
        self._loading_state = LoadingState(loading_text)
        self._loading_label = self._loading_state.message_label
        self._loading_label.setObjectName("loadingLabel")
        self._layout.addWidget(self._loading_state)

    def ensure_loaded(self) -> QWidget | None:
        """Load and return the real widget without waiting for a show event."""
        if not self._loaded:
            self._loaded = True

            # Remove loading placeholder
            self._loading_state.hide()
            self._layout.removeWidget(self._loading_state)
            self._loading_state.deleteLater()

            # Load and add the real widget
            try:
                self.real_widget = self.loader_fn()
                self._layout.addWidget(self.real_widget)
            except Exception as e:
                # Show error if loading fails
                logger.exception("Lazy page load failed")
                self.load_error = str(e)
                error_state = UnavailableState(
                    self.tr("Page unavailable"),
                    self.tr("This page could not be loaded.\n\n%1").replace(
                        "%1", self.load_error
                    ),
                )
                error_label = error_state.message_label
                error_label.setObjectName("errorLabel")
                self._layout.addWidget(error_state)
        return self.real_widget

    def showEvent(self, event):
        """Load the real widget when first shown."""
        self.ensure_loaded()

        super().showEvent(event)

    def get_real_widget(self) -> QWidget | None:
        """Return the real widget if loaded, None otherwise."""
        return self.real_widget
