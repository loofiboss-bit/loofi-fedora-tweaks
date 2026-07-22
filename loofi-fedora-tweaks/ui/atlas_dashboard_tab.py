"""Canonical Home presentation built from the read-only HomeSummary contract."""

from __future__ import annotations

from typing import Protocol

from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import QHBoxLayout, QLabel, QLayout, QVBoxLayout, QWidget

from core.home import AttentionItem, HomeStatus, HomeSummary, HomeTask, Recommendation
from core.plugins.metadata import PluginMetadata
from core.product_catalog import plugin_metadata_for_module

from .base_tab import BaseTab
from .components import (
    ActionBar,
    Card,
    ClickableCard,
    DetailsDisclosure,
    GhostButton,
    PageScaffold,
    PrimaryButton,
    StatusBadge,
)
from .components.layout import AdaptiveGrid
from .icon_pack import get_qicon


class _HomeSummaryProvider(Protocol):
    def summary(self) -> HomeSummary:
        ...


class AtlasDashboardTab(BaseTab):
    """One bounded, read-only Home with navigation to maintained workflows."""

    _METADATA = plugin_metadata_for_module(__name__)

    _STATUS_ORDER = (
        ("health", "System health"),
        ("updates", "Updates"),
        ("storage", "Storage"),
        ("recovery", "Recovery protection"),
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

        self.scaffold = PageScaffold(
            self.tr("Home"),
            self.tr("Current status, the next useful action, and common Fedora tasks."),
        )
        outer.addWidget(self.scaffold)

        self.state_card = Card(self.tr("System status"))
        self.state_card.setObjectName("homeState")
        self.state_label = QLabel()
        self.state_label.setObjectName("homeStateLabel")
        self.state_label.setWordWrap(True)
        self.state_card.add_widget(self.state_label)

        status_grid = AdaptiveGrid(
            min_column_width=190,
            column_breakpoints=((0, 1), (360, 2), (760, 4)),
        )
        status_grid.setObjectName("homeStatusGrid")
        self.status_badges: dict[str, StatusBadge] = {}
        for key, label in self._STATUS_ORDER:
            badge = StatusBadge(
                self.tr("%1: Status unavailable").replace("%1", self.tr(label)),
                kind="neutral",
            )
            badge.setProperty("statusCategory", key)
            self.status_badges[key] = badge
            status_grid.add_card(badge)
        self.state_card.add_widget(status_grid)
        self.scaffold.add_widget(self.state_card)

        self.primary_container = QVBoxLayout()
        self.attention_container = QVBoxLayout()
        self.tasks_container = QVBoxLayout()
        self.recent_container = QVBoxLayout()
        self.scaffold.add_layout(self.primary_container)
        self.scaffold.add_layout(self.attention_container)
        self.scaffold.add_layout(self.tasks_container)
        self.scaffold.add_layout(self.recent_container)
        self.scaffold.content_layout.addStretch()

    def refresh_summary(self) -> None:
        """Re-read saved status explicitly; Home has no polling timer."""
        if self.home_service is None:
            return
        summary = self.home_service.summary()
        self.state_card.setProperty("overallState", summary.overall_state)
        self.state_card.setProperty("dataState", summary.data_state)
        self.state_label.setText(self.tr(summary.summary))
        self._update_status_badges(summary)

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
        task_grid = AdaptiveGrid(min_column_width=250)
        task_grid.setObjectName("homeTaskGrid")
        for task in summary.common_tasks[:6]:
            task_grid.add_card(self._task_card(task))
        self.tasks_container.addWidget(task_grid)

        if summary.recent_change is not None:
            self.recent_container.addWidget(self._section_label(self.tr("Recent activity")))
            recent = Card()
            recent.setObjectName("homeRecentChange")
            details = self.tr(summary.recent_change.description)
            if summary.recent_change.undo_available:
                details = "%s\n%s" % (
                    details,
                    self.tr("Undo is available from the activity bar."),
                )
            disclosure = DetailsDisclosure(
                details,
                summary=self.tr("Show recent activity"),
            )
            disclosure.setAccessibleName(self.tr("Recent activity"))
            disclosure.details.setAccessibleName(self.tr("Recent activity details"))
            recent.add_widget(disclosure)
            self.recent_container.addWidget(recent)

    def _load_saved_summary(self) -> None:
        """Load local persisted sources after the first Home frame can render."""
        if self.home_service is None:
            from core.home.service import HomeService

            self.home_service = HomeService()
        self.refresh_summary()

    def _add_primary(self, recommendation: Recommendation) -> None:
        self.primary_container.addWidget(self._section_label(self.tr("Recommended next step")))
        card = Card(self.tr(recommendation.title), self.tr(recommendation.summary))
        card.setObjectName("homePrimaryRecommendation")
        card.setProperty("recommendationKind", recommendation.kind)
        card.setProperty("severity", recommendation.severity)
        card.add_widget(self._severity_badge(recommendation.severity))
        actions = ActionBar()
        button = PrimaryButton(
            self.tr("Review"),
            description=self.tr(recommendation.summary),
        )
        button.setAccessibleName(
            self.tr("Review %1").replace("%1", self.tr(recommendation.title))
        )
        self._connect_route_button(button, recommendation.route_id)
        actions.add_action(button, primary=True)
        card.add_widget(actions)
        self.primary_container.addWidget(card)

    def _attention_card(self, item: AttentionItem) -> Card:
        card = Card(self.tr(item.title), self.tr(item.summary))
        card.setObjectName("homeAttentionItem")
        card.setProperty("severity", item.severity)
        card.add_widget(self._severity_badge(item.severity))
        actions = ActionBar()
        button = GhostButton(self.tr("Open"), description=self.tr(item.summary))
        button.setAccessibleName(
            self.tr("Open %1").replace("%1", self.tr(item.title))
        )
        self._connect_route_button(button, item.route_id)
        actions.add_action(button, primary=True)
        card.add_widget(actions)
        return card

    def _task_card(self, task: HomeTask) -> ClickableCard:
        card = ClickableCard(
            self.tr(task.title),
            self.tr(task.description),
            task.route_id,
        )
        card.setObjectName("homeTask")
        card.setAccessibleDescription(
            self.tr("Open %1. %2")
            .replace("%1", self.tr(task.title))
            .replace("%2", self.tr(task.description))
        )
        card.body.removeWidget(card.title_label)
        card.body.removeWidget(card.description_label)
        heading = QHBoxLayout()
        heading.setContentsMargins(0, 0, 0, 0)
        heading.setSpacing(12)
        icon_label = QLabel()
        icon_label.setObjectName("homeTaskIcon")
        icon_label.setPixmap(get_qicon(task.icon_id, size=24).pixmap(24, 24))
        icon_label.setAccessibleName("")
        heading.addWidget(icon_label)
        copy = QVBoxLayout()
        copy.setContentsMargins(0, 0, 0, 0)
        copy.setSpacing(4)
        copy.addWidget(card.title_label)
        copy.addWidget(card.description_label)
        heading.addLayout(copy, 1)
        card.body.addLayout(heading)
        affordance = QLabel(self.tr("Open"))
        affordance.setObjectName("homeTaskAffordance")
        affordance.setAccessibleName(self.tr("Open %1").replace("%1", self.tr(task.title)))
        card.add_widget(affordance)
        card.activated.connect(self._open_route)
        return card

    def _connect_route_button(self, button, route_id: str) -> None:
        button.setProperty("routeId", route_id)
        if route_id == "maintenance:action-center":
            button.setObjectName("homeActionCenterLink")
        button.clicked.connect(lambda _checked=False: self._open_route(route_id))

    def _update_status_badges(self, summary: HomeSummary) -> None:
        status_by_id: dict[str, HomeStatus] = {
            item.id: item for item in summary.status_items
        }
        for key, label in self._STATUS_ORDER:
            status = status_by_id.get(key)
            if status is None:
                status = HomeStatus(
                    key,  # type: ignore[arg-type]
                    label,
                    "unknown",
                    "No saved status is available for this area.",
                    "",
                )
            presentation = {
                "good": (self.tr("No saved issue"), "success"),
                "attention": (self.tr("Attention"), "warning"),
                "critical": (self.tr("Needs review"), "error"),
                "unknown": (self.tr("Status unavailable"), "neutral"),
            }
            state, kind = presentation[status.state]
            description = self.tr(status.summary)
            text = self.tr("%1: %2").replace("%1", self.tr(label)).replace("%2", state)
            self.status_badges[key].set_status(text, kind=kind, description=description)

    def _severity_badge(self, severity: str) -> StatusBadge:
        labels = {
            "critical": (self.tr("Critical"), "error"),
            "attention": (self.tr("Attention"), "warning"),
            "info": (self.tr("Information"), "info"),
        }
        text, kind = labels.get(severity, (self.tr("Information"), "info"))
        return StatusBadge(text, kind=kind)

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
