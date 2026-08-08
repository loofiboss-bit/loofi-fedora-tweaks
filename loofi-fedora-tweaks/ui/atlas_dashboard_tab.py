"""Canonical Home presentation built from the read-only HomeSummary contract."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, Protocol

from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import QHBoxLayout, QLabel, QLayout, QVBoxLayout, QWidget

from core.home import (
    AttentionItem,
    GuidedTask,
    HomeStatus,
    HomeSummary,
    HomeTask,
    OnboardingState,
    OnboardingStore,
    Recommendation,
)
from core.plugins.metadata import PluginMetadata
from core.product_catalog import plugin_metadata_for_module

from .base_tab import BaseTab
from .components import (
    ActionBar,
    ActionProgress,
    Card,
    ClickableCard,
    DetailsDisclosure,
    GhostButton,
    InlineNotice,
    PageScaffold,
    PrimaryButton,
    StatusBadge,
)
from .components.layout import AdaptiveGrid
from .icon_pack import get_qicon
from .home_onboarding import HomeOnboardingCard

_DETACHED_CHECK_WORKERS: set[Any] = set()


class _HomeSummaryProvider(Protocol):
    def summary(self) -> HomeSummary:
        ...


class _OnboardingStateStore(Protocol):
    def load(self) -> OnboardingState:
        ...

    def advance(self, state: OnboardingState) -> OnboardingState:
        ...

    def dismiss(self, state: OnboardingState) -> OnboardingState:
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
    _CHECK_SOURCE_LABELS = {
        "state-integrity": "Application state",
        "maintenance": "Updates, services, and disk",
        "storage-reclaim": "Reclaimable storage",
        "action-center": "Action Center history",
        "pending-reboot": "Pending reboot",
    }

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
        check_worker_factory: Callable[[QWidget], Any] | None = None,
        onboarding_store: _OnboardingStateStore | None = None,
    ) -> None:
        super().__init__()
        self.main_window = main_window
        self.home_service = home_service
        self.check_worker_factory = check_worker_factory
        self.onboarding_store = onboarding_store or OnboardingStore()
        self.onboarding_state = self.onboarding_store.load()
        self._check_worker: Any | None = None
        self._check_cancel_requested = False
        self._closing = False
        self._last_summary: HomeSummary | None = None
        self.check_progress: ActionProgress | None = None
        self.check_source_label: QLabel | None = None
        self.check_elapsed_label: QLabel | None = None
        self.check_unavailable_label: QLabel | None = None
        self.check_notice: InlineNotice | None = None
        self.cancel_check_button: GhostButton | None = None
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

        self.onboarding_card = HomeOnboardingCard()
        self.onboarding_card.set_state(self.onboarding_state)
        self.onboarding_card.advanceRequested.connect(self._advance_onboarding)
        self.onboarding_card.dismissRequested.connect(self._dismiss_onboarding)
        self.scaffold.add_widget(self.onboarding_card)

        self.state_card = Card(self.tr("System status"))
        self.state_card.setObjectName("homeState")
        self.state_label = QLabel()
        self.state_label.setObjectName("homeStateLabel")
        self.state_label.setWordWrap(True)
        self.state_card.add_widget(self.state_label)
        self.freshness_label = QLabel(self.tr("Last checked: Never · Status unavailable"))
        self.freshness_label.setObjectName("homeLastChecked")
        self.freshness_label.setWordWrap(True)
        self.state_card.add_widget(self.freshness_label)

        status_grid = AdaptiveGrid(
            min_column_width=190,
            column_breakpoints=((0, 1), (360, 2), (760, 4)),
        )
        self.status_grid = status_grid
        self.status_grid.setObjectName("homeStatusGrid")
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
        self.status_unavailable = InlineNotice(
            self.tr("Not checked yet"),
            self.tr("Run System Check to create the first saved status."),
            kind="neutral",
        )
        self.status_unavailable.setObjectName("homeStatusUnavailable")
        self.status_unavailable.hide()
        self.state_card.add_widget(self.status_unavailable)

        self.check_actions = ActionBar()
        self.check_now_button = PrimaryButton(
            self.tr("Check now"),
            description=self.tr("Run the local read-only System Check."),
        )
        self.check_now_button.setObjectName("homeCheckNow")
        self.check_now_button.clicked.connect(self.start_system_check)
        self.check_actions.add_action(self.check_now_button, primary=True)
        self.state_card.add_widget(self.check_actions)
        self.scaffold.add_widget(self.state_card)

        self.primary_container = QVBoxLayout()
        self.attention_container = QVBoxLayout()
        self.tasks_container = QVBoxLayout()
        self.recent_container = QVBoxLayout()
        self.active_work_container = QVBoxLayout()
        self.scaffold.add_layout(self.primary_container)
        self.scaffold.add_layout(self.attention_container)
        self.scaffold.add_layout(self.tasks_container)
        self.scaffold.add_layout(self.active_work_container)
        self.scaffold.add_layout(self.recent_container)
        self.scaffold.content_layout.addStretch()

    def _advance_onboarding(self) -> None:
        route_id = self.onboarding_state.current_step.route_id
        try:
            self.onboarding_state = self.onboarding_store.advance(self.onboarding_state)
        except OSError as exc:
            self.onboarding_card.show_error(self.tr(str(exc)))
            return
        self.onboarding_card.set_state(self.onboarding_state)
        if route_id:
            self._open_route(route_id)

    def _dismiss_onboarding(self) -> None:
        try:
            self.onboarding_state = self.onboarding_store.dismiss(self.onboarding_state)
        except OSError as exc:
            self.onboarding_card.show_error(self.tr(str(exc)))
            return
        self.onboarding_card.set_state(self.onboarding_state)

    def refresh_summary(self) -> None:
        """Re-read saved status explicitly; Home has no polling timer."""
        if self.home_service is None:
            return
        summary = self.home_service.summary()
        self._last_summary = summary
        self.state_card.setProperty("overallState", summary.overall_state)
        self.state_card.setProperty("dataState", summary.data_state)
        self.state_label.setText(self.tr(summary.summary))
        self._update_freshness(summary)
        self.check_now_button.setVisible(summary.check_now_available)
        if summary.data_state in {"empty", "error"}:
            self.status_grid.hide()
            if summary.data_state == "empty":
                self.status_unavailable.set_notice(
                    "neutral",
                    self.tr("Not checked yet"),
                    self.tr("Run System Check to create the first saved status."),
                )
            else:
                self.status_unavailable.set_notice(
                    "error",
                    self.tr("Status check failed"),
                    self.tr("Saved status could not be read. Try System Check again."),
                )
            self.status_unavailable.show()
        else:
            self.status_unavailable.hide()
            self.status_grid.show()
            self._update_status_badges(summary)

        self._clear_layout(self.primary_container)
        self._clear_layout(self.attention_container)
        self._clear_layout(self.tasks_container)
        self._clear_layout(self.active_work_container)
        self._clear_layout(self.recent_container)

        if summary.primary_task is not None:
            self._add_guided_task(summary.primary_task, primary=True)
        elif summary.primary_recommendation is not None:
            self._add_primary(summary.primary_recommendation)
        if summary.attention_items:
            self.attention_container.addWidget(self._section_label(self.tr("Also needs attention")))
            attention_grid = AdaptiveGrid(
                min_column_width=250,
                column_breakpoints=((0, 1), (560, 2), (900, 3)),
            )
            attention_grid.setObjectName("homeAttentionGrid")
            for item in summary.attention_items:
                attention_grid.add_card(self._attention_card(item))
            self.attention_container.addWidget(attention_grid)

        self.tasks_container.addWidget(self._section_label(self.tr("Common tasks")))
        task_grid = AdaptiveGrid(min_column_width=250)
        task_grid.setObjectName("homeTaskGrid")
        for task in summary.common_tasks[:5]:
            task_grid.add_card(self._task_card(task))
        self.tasks_container.addWidget(task_grid)

        if summary.active_work is not None:
            self.active_work_container.addWidget(
                self._section_label(self.tr("Active work"))
            )
            self._add_guided_task(
                summary.active_work,
                primary=False,
                target=self.active_work_container,
            )

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

    def _update_freshness(self, summary: HomeSummary) -> None:
        if summary.last_checked_at is None:
            checked = self.tr("Never")
        else:
            checked = summary.last_checked_at.astimezone().strftime("%Y-%m-%d %H:%M")
        freshness = {
            "fresh": self.tr("Fresh"),
            "stale": self.tr("Stale"),
            "unavailable": (
                self.tr("Not checked yet")
                if summary.data_state == "empty"
                else self.tr("Check failed")
            ),
        }[summary.freshness_state]
        self.freshness_label.setText(
            self.tr("Last checked: %1 · %2")
            .replace("%1", checked)
            .replace("%2", freshness)
        )
        self.freshness_label.setAccessibleName(self.tr("System Check freshness"))
        self.freshness_label.setAccessibleDescription(self.freshness_label.text())

    def start_system_check(self) -> None:
        """Start collection only after direct user activation."""
        if self._check_worker is not None and self._check_worker.isRunning():
            return
        self._ensure_check_feedback()
        assert self.check_progress is not None
        assert self.check_source_label is not None
        assert self.check_elapsed_label is not None
        assert self.check_unavailable_label is not None
        assert self.check_notice is not None
        assert self.cancel_check_button is not None
        if self.check_worker_factory is None:
            from core.workers.system_check_worker import SystemCheckWorker

            worker = SystemCheckWorker(parent=self)
        else:
            worker = self.check_worker_factory(self)
        self._check_worker = worker
        self._check_cancel_requested = False
        self.check_notice.setVisible(False)
        self.check_unavailable_label.clear()
        self.check_unavailable_label.setVisible(False)
        self.check_progress.set_busy(self.tr("Starting the local read-only check…"))
        self.check_progress.setVisible(True)
        self.check_source_label.setText(self.tr("Current source: Preparing"))
        self.check_elapsed_label.setText(self.tr("Elapsed: 0.0 seconds"))
        self.check_now_button.set_loading(True, self.tr("Checking…"))
        self.cancel_check_button.setEnabled(True)
        self.cancel_check_button.setVisible(True)
        worker.check_progress.connect(self._on_check_progress)
        worker.finished.connect(self._on_check_finished)
        worker.error.connect(self._on_check_error)
        worker.start()

    def _ensure_check_feedback(self) -> None:
        """Create nonessential operation feedback only after explicit activation."""
        if self.check_progress is not None:
            return
        self.check_progress = ActionProgress(self.tr("Preparing System Check…"))
        self.check_progress.setObjectName("homeSystemCheckProgress")
        self.check_source_label = QLabel(self.tr("Current source: Waiting"))
        self.check_source_label.setObjectName("homeSystemCheckSource")
        self.check_elapsed_label = QLabel(self.tr("Elapsed: 0.0 seconds"))
        self.check_elapsed_label.setObjectName("homeSystemCheckElapsed")
        self.check_unavailable_label = QLabel()
        self.check_unavailable_label.setObjectName("homeSystemCheckUnavailable")
        self.check_unavailable_label.setWordWrap(True)
        self.check_unavailable_label.setVisible(False)
        self.check_progress.details_layout.addWidget(self.check_source_label)
        self.check_progress.details_layout.addWidget(self.check_elapsed_label)
        self.check_progress.details_layout.addWidget(self.check_unavailable_label)
        self.state_card.add_widget(self.check_progress)

        self.check_notice = InlineNotice("", "", kind="neutral")
        self.check_notice.setObjectName("homeSystemCheckNotice")
        self.check_notice.setVisible(False)
        self.state_card.add_widget(self.check_notice)

        self.cancel_check_button = GhostButton(
            self.tr("Cancel"),
            description=self.tr("Cancel the running System Check and keep the previous saved status."),
        )
        self.cancel_check_button.setObjectName("homeCancelSystemCheck")
        self.cancel_check_button.clicked.connect(self.cancel_system_check)
        self.check_actions.add_action(self.cancel_check_button)
        self.cancel_check_button.setVisible(False)

    def cancel_system_check(self) -> None:
        worker = self._check_worker
        if (
            worker is None
            or not worker.isRunning()
            or self.cancel_check_button is None
            or self.check_progress is None
        ):
            return
        self._check_cancel_requested = True
        self.cancel_check_button.setEnabled(False)
        self.check_progress.set_busy(self.tr("Cancelling System Check…"))
        worker.cancel()

    def _on_check_progress(self, progress: Any) -> None:
        if (
            self._closing
            or self.check_progress is None
            or self.check_source_label is None
            or self.check_elapsed_label is None
            or self.check_unavailable_label is None
        ):
            return
        source_id = str(getattr(progress, "source_id", "") or "")
        source = self.tr(self._CHECK_SOURCE_LABELS.get(source_id, source_id or "Finalizing"))
        elapsed = max(0.0, float(getattr(progress, "elapsed_seconds", 0.0) or 0.0))
        percentage = int(getattr(progress, "percentage", 0) or 0)
        stage = str(getattr(progress, "stage", "running"))
        message = {
            "running": self.tr("Checking saved and local system signals…"),
            "completed": self.tr("Source completed."),
            "failed": self.tr("Source unavailable; continuing with partial results."),
            "timed_out": self.tr("Source timed out; continuing with partial results."),
            "cancelling": self.tr("Cancelling System Check…"),
        }.get(stage, self.tr("Checking…"))
        self.check_progress.set_progress(percentage, message)
        self.check_source_label.setText(
            self.tr("Current source: %1").replace("%1", source)
        )
        self.check_elapsed_label.setText(
            self.tr("Elapsed: %1 seconds").replace("%1", f"{elapsed:.1f}")
        )
        unavailable = tuple(getattr(progress, "unavailable_sources", ()) or ())
        if unavailable:
            labels = [
                self.tr(self._CHECK_SOURCE_LABELS.get(str(item), str(item)))
                for item in unavailable
            ]
            self.check_unavailable_label.setText(
                self.tr("Unavailable sources: %1").replace("%1", ", ".join(labels))
            )
            self.check_unavailable_label.setVisible(True)

    def _on_check_finished(self, result: Any) -> None:
        if self._closing:
            return
        state = str(getattr(result, "state", "failed"))
        findings = tuple(getattr(result, "findings", ()) or ())
        errors = tuple(getattr(result, "source_errors", ()) or ())
        if state == "completed":
            kind = "warning" if findings else "success"
            title = self.tr("Check complete")
            message = (
                self.tr("%1 finding(s) need review.").replace("%1", str(len(findings)))
                if findings
                else self.tr("No issue was found by the completed sources.")
            )
        elif state == "partial":
            kind = "warning"
            title = self.tr("Check partially complete")
            sources = ", ".join(
                self.tr(self._CHECK_SOURCE_LABELS.get(str(error.source_id), str(error.source_id)))
                for error in errors
            )
            message = self.tr("Unavailable sources: %1").replace("%1", sources or self.tr("Unknown"))
        elif state == "cancelled":
            kind = "neutral"
            title = self.tr("Check cancelled")
            message = self.tr("The previous saved status was kept.")
        else:
            kind = "error"
            title = self.tr("Check could not finish")
            message = self.tr("The previous saved status was kept. Try again or review diagnostics.")
        self._finish_check_presentation(kind, title, message)
        if state in {"completed", "partial"}:
            self.refresh_summary()

    def _on_check_error(self, _message: str) -> None:
        if self._closing:
            return
        if self._check_cancel_requested:
            self._finish_check_presentation(
                "neutral",
                self.tr("Check cancelled"),
                self.tr("The previous saved status was kept."),
            )
        else:
            self._finish_check_presentation(
                "error",
                self.tr("Check could not finish"),
                self.tr("The previous saved status was kept. Try again or review diagnostics."),
            )

    def _finish_check_presentation(self, kind: str, title: str, message: str) -> None:
        if (
            self.check_progress is None
            or self.cancel_check_button is None
            or self.check_notice is None
        ):
            return
        worker = self._check_worker
        self._check_worker = None
        self._check_cancel_requested = False
        self.check_progress.setVisible(False)
        self.cancel_check_button.setVisible(False)
        self.check_now_button.set_loading(False)
        self.check_notice.set_notice(kind, title, message)
        self.check_notice.setVisible(True)
        if worker is not None:
            worker.wait(1000)
            worker.deleteLater()

    def cleanup(self) -> None:
        """Cancel or detach the bounded worker before Home is destroyed."""
        self._closing = True
        worker = self._check_worker
        if worker is None:
            return
        if worker.isRunning():
            worker.cancel()
            worker.wait(1000)
        if worker.isRunning():
            worker.setParent(None)
            _DETACHED_CHECK_WORKERS.add(worker)

            def release_worker(*_args: Any) -> None:
                worker.wait(1000)
                _DETACHED_CHECK_WORKERS.discard(worker)
                worker.deleteLater()

            worker.finished.connect(release_worker)
            worker.error.connect(release_worker)
        else:
            worker.deleteLater()
        self._check_worker = None

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

    def _add_guided_task(
        self,
        task: GuidedTask,
        *,
        primary: bool,
        target: QVBoxLayout | None = None,
    ) -> None:
        container = target or self.primary_container
        if primary:
            container.addWidget(self._section_label(self.tr("Recommended next step")))
        card = Card(self.tr(task.title), self.tr(task.summary))
        card.setObjectName("homePrimaryTask" if primary else "homeActiveWork")
        card.setProperty("taskSource", task.source)
        card.setProperty("sourceId", task.source_id)
        actions = ActionBar()
        button_type = PrimaryButton if primary else GhostButton
        button = button_type(
            self.tr(task.action_label),
            description=self.tr(task.summary),
        )
        button.setAccessibleName(
            self.tr("%1: %2")
            .replace("%1", self.tr(task.action_label))
            .replace("%2", self.tr(task.title))
        )
        self._connect_route_button(button, task.route_id)
        actions.add_action(button, primary=True)
        card.add_widget(actions)
        container.addWidget(card)

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
