"""Canonical v15 Home surface built from the read-only HomeSummary contract."""

from __future__ import annotations

from collections.abc import Callable
from typing import Protocol

from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QLayout,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from core.home import AttentionItem, HomeSummary, HomeTask, Recommendation
from core.plugins.metadata import PluginMetadata

from .base_tab import BaseTab
from .layout_primitives import AdaptiveGrid, make_page_title


class _NavigationCard(QFrame):
    """Compact navigation-only card; it never owns domain actions."""

    def __init__(
        self,
        title: str,
        description: str,
        route_id: str,
        callback: Callable[[str], None],
        *,
        object_name: str,
        button_text: str,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.route_id = route_id
        self.setObjectName(object_name)
        self.setProperty("routeId", route_id)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(8)

        title_label = QLabel(title)
        title_label.setObjectName("homeCardTitle")
        title_label.setWordWrap(True)
        layout.addWidget(title_label)

        description_label = QLabel(description)
        description_label.setObjectName("homeCardDescription")
        description_label.setWordWrap(True)
        layout.addWidget(description_label)
        layout.addStretch()

        self.open_button = QPushButton(button_text)
        self.open_button.setAccessibleName(button_text)
        self.open_button.setProperty("routeId", route_id)
        if route_id == "maintenance:action-center":
            self.open_button.setObjectName("homeActionCenterLink")
        self.open_button.clicked.connect(lambda _checked=False: callback(route_id))
        layout.addWidget(self.open_button)


class _HomeSummaryProvider(Protocol):
    def summary(self) -> HomeSummary:
        ...


class AtlasDashboardTab(BaseTab):
    """One bounded, read-only Home with navigation to maintained workflows."""

    _METADATA = PluginMetadata(
        id="atlas_dashboard",
        name="Home",
        description="System status, the next useful action, and common Fedora tasks.",
        category="System",
        icon="home",
        badge="recommended",
        order=0,
    )

    def metadata(self) -> PluginMetadata:
        return self._METADATA

    def create_widget(self) -> QWidget:
        return self

    def set_context(self, context: dict) -> None:
        self.main_window = context.get("main_window")

    def __init__(
        self,
        main_window=None,
        *,
        home_service: _HomeSummaryProvider | None = None,
    ) -> None:
        super().__init__()
        self.main_window = main_window
        self.home_service = home_service
        self._setup_ui()
        if self.home_service is not None:
            self.refresh_summary()
        else:
            self.state_card.setProperty("overallState", "unknown")
            self.state_card.setProperty("dataState", "empty")
            self.state_label.setText(self.tr("Loading saved system status…"))
            QTimer.singleShot(0, self._load_saved_summary)

    def _setup_ui(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        outer.addWidget(scroll)

        container = QWidget()
        self._content = QVBoxLayout(container)
        self._content.setContentsMargins(32, 28, 32, 28)
        self._content.setSpacing(18)
        scroll.setWidget(container)

        self._content.addWidget(make_page_title(self.tr("Home")))
        subheader = QLabel(self.tr("A concise view of what needs attention and where to go next."))
        subheader.setObjectName("homeSubheader")
        subheader.setWordWrap(True)
        self._content.addWidget(subheader)

        self.state_card = QFrame()
        self.state_card.setObjectName("homeState")
        state_layout = QVBoxLayout(self.state_card)
        state_layout.setContentsMargins(18, 16, 18, 16)
        self.state_label = QLabel()
        self.state_label.setObjectName("homeStateLabel")
        self.state_label.setWordWrap(True)
        state_layout.addWidget(self.state_label)
        self._content.addWidget(self.state_card)

        self.primary_container = QVBoxLayout()
        self.attention_container = QVBoxLayout()
        self.tasks_container = QVBoxLayout()
        self.recent_container = QVBoxLayout()
        self._content.addLayout(self.primary_container)
        self._content.addLayout(self.attention_container)
        self._content.addLayout(self.tasks_container)
        self._content.addLayout(self.recent_container)
        self._content.addStretch()

    def refresh_summary(self) -> None:
        """Re-read saved status explicitly; Home has no polling timer."""
        if self.home_service is None:
            return
        summary = self.home_service.summary()
        self.state_card.setProperty("overallState", summary.overall_state)
        self.state_card.setProperty("dataState", summary.data_state)
        self.state_label.setText(self.tr(summary.summary))

        self._clear_layout(self.primary_container)
        self._clear_layout(self.attention_container)
        self._clear_layout(self.tasks_container)
        self._clear_layout(self.recent_container)

        if summary.primary_recommendation is not None:
            self._add_primary(summary.primary_recommendation)
        if summary.attention_items:
            self.attention_container.addWidget(self._section_label(self.tr("Also needs attention")))
            for item in summary.attention_items:
                self.attention_container.addWidget(self._attention_card(item))

        self.tasks_container.addWidget(self._section_label(self.tr("Common tasks")))
        task_grid = AdaptiveGrid(min_column_width=260)
        task_grid.setObjectName("homeTaskGrid")
        for task in summary.common_tasks:
            task_grid.add_card(self._task_card(task))
        self.tasks_container.addWidget(task_grid)

        if summary.recent_change is not None:
            self.recent_container.addWidget(self._section_label(self.tr("Recent activity")))
            recent = QFrame()
            recent.setObjectName("homeRecentChange")
            layout = QHBoxLayout(recent)
            description = QLabel(self.tr(summary.recent_change.description))
            description.setWordWrap(True)
            layout.addWidget(description, 1)
            if summary.recent_change.undo_available:
                undo_hint = QLabel(self.tr("Undo is available from the activity bar."))
                undo_hint.setObjectName("homeUndoHint")
                undo_hint.setWordWrap(True)
                layout.addWidget(undo_hint)
            self.recent_container.addWidget(recent)

    def _load_saved_summary(self) -> None:
        """Load local persisted sources after the first Home frame can render."""
        if self.home_service is None:
            from core.home.service import HomeService

            self.home_service = HomeService()
        self.refresh_summary()

    def _add_primary(self, recommendation: Recommendation) -> None:
        self.primary_container.addWidget(self._section_label(self.tr("Recommended next step")))
        card = _NavigationCard(
            self.tr(recommendation.title),
            self.tr(recommendation.summary),
            recommendation.route_id,
            self._open_route,
            object_name="homePrimaryRecommendation",
            button_text=self.tr("Review"),
        )
        card.setProperty("recommendationKind", recommendation.kind)
        card.setProperty("severity", recommendation.severity)
        self.primary_container.addWidget(card)

    def _attention_card(self, item: AttentionItem) -> _NavigationCard:
        card = _NavigationCard(
            self.tr(item.title),
            self.tr(item.summary),
            item.route_id,
            self._open_route,
            object_name="homeAttentionItem",
            button_text=self.tr("Open"),
        )
        card.setProperty("severity", item.severity)
        return card

    def _task_card(self, task: HomeTask) -> _NavigationCard:
        return _NavigationCard(
            self.tr(task.title),
            self.tr(task.description),
            task.route_id,
            self._open_route,
            object_name="homeTask",
            button_text=self.tr("Open"),
        )

    @staticmethod
    def _section_label(text: str) -> QLabel:
        label = QLabel(text)
        label.setObjectName("homeSectionTitle")
        return label

    @staticmethod
    def _clear_layout(layout: QLayout) -> None:
        while layout.count():
            item = layout.takeAt(0)
            if item is None:
                continue
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
            child_layout = item.layout()
            if child_layout is not None:
                AtlasDashboardTab._clear_layout(child_layout)

    def _open_route(self, route_id: str) -> None:
        main_window = self.main_window
        if main_window is None:
            main_window = self.window() if hasattr(self, "window") else None
        switch = getattr(main_window, "switch_to_route", None)
        if callable(switch):
            switch(route_id)
