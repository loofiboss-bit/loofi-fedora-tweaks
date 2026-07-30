"""Canonical read-only System Check, finding, and health-history page."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Protocol

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from core.plugins.interface import PluginInterface
from core.plugins.metadata import PluginMetadata
from core.product_catalog import plugin_metadata_for_module
from core.system_check.presentation import (
    FindingView,
    HistoryView,
    MaintenanceOutcomeView,
    MetricView,
    SystemCheckPageState,
)
from ui.components import (
    Card,
    DetailsDisclosure,
    EmptyState,
    InlineNotice,
    LocalViewItem,
    LocalViewSwitcher,
    PageScaffold,
    SecondaryButton,
    StatusBadge,
)


class _PresentationService(Protocol):
    def load(self, *, history_limit: int = 30) -> SystemCheckPageState:
        ...


class SystemCheckTab(QWidget, PluginInterface):
    """One Standard-mode presentation over both existing health stores."""

    findingActionReviewRequested = pyqtSignal(str, object)
    _METADATA = plugin_metadata_for_module(__name__)
    _SECTION_INDEX = {"overview": 0, "findings": 1, "history": 2}

    def __init__(
        self,
        *,
        presentation_service: _PresentationService | None = None,
    ) -> None:
        super().__init__()
        if presentation_service is None:
            from core.actions.stores import ActionRunStore
            from core.system_check.presentation import SystemCheckPresentationService

            presentation_service = SystemCheckPresentationService(
                run_store=ActionRunStore()
            )
        self.presentation_service = presentation_service
        self._state: SystemCheckPageState | None = None
        self._origin_route = "health"
        self._setup_ui()
        self.refresh()

    def metadata(self) -> PluginMetadata:
        return self._METADATA

    def create_widget(self) -> QWidget:
        return self

    def _setup_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        self.scaffold = PageScaffold(
            self.tr("System Check"),
            self.tr("Current findings, saved checks, before/after history, and supporting metrics."),
        )
        root.addWidget(self.scaffold)

        explanation = InlineNotice(
            self.tr("Three different kinds of evidence"),
            self.tr(
                "A finding is an explained issue from a completed System Check. "
                "A sampled metric is supporting history, not a finding. "
                "An Action Center run is a separately reviewed and verified system change."
            ),
            kind="info",
        )
        explanation.setObjectName("systemCheckEvidenceExplanation")
        self.scaffold.add_widget(explanation)

        content = QVBoxLayout()
        content.setSpacing(16)
        view_row = QHBoxLayout()
        view_row.setContentsMargins(0, 0, 0, 0)
        view_row.setSpacing(12)
        self.view_label = QLabel(self.tr("View"))
        self.view_label.setObjectName("systemCheckViewLabel")
        self.view_label.setAccessibleName(self.tr("System Check view"))
        view_row.addWidget(self.view_label)
        self.view_switcher = LocalViewSwitcher()
        self.view_switcher.setObjectName("systemCheckViewSwitcher")
        self.view_switcher.set_views(
            [
                LocalViewItem("overview", self.tr("Overview"), self.tr("Latest saved System Check status.")),
                LocalViewItem("findings", self.tr("Findings"), self.tr("Issues from the latest saved check.")),
                LocalViewItem("history", self.tr("History"), self.tr("Before/after state and supporting metrics.")),
            ]
        )
        self.view_switcher.viewActivated.connect(self.select_view)
        view_row.addWidget(self.view_switcher, 1)
        content.addLayout(view_row)

        self.stack = QStackedWidget()
        self.stack.setObjectName("systemCheckViewStack")
        self.stack.addWidget(self._overview_page())
        self.stack.addWidget(self._findings_page())
        self.stack.addWidget(self._history_page())
        content.addWidget(self.stack, 1)
        self.scaffold.add_layout(content, 1)

    def _overview_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        self.status_card = Card(self.tr("Latest saved check"))
        self.status_card.setObjectName("systemCheckOverview")
        self.status_badge = StatusBadge(self.tr("Status unavailable"), kind="neutral")
        self.status_badge.setObjectName("systemCheckStatus")
        self.last_checked_label = QLabel(self.tr("Last checked: Never"))
        self.last_checked_label.setObjectName("systemCheckLastChecked")
        self.last_checked_label.setWordWrap(True)
        self.unavailable_label = QLabel()
        self.unavailable_label.setObjectName("systemCheckUnavailableSources")
        self.unavailable_label.setWordWrap(True)
        self.unavailable_label.hide()
        self.refresh_button = SecondaryButton(
            self.tr("Refresh saved results"),
            description=self.tr("Reread local persisted System Check data without collecting new signals."),
        )
        self.refresh_button.setObjectName("systemCheckRefresh")
        self.refresh_button.clicked.connect(self.refresh)
        self.status_card.add_widget(self.status_badge)
        self.status_card.add_widget(self.last_checked_label)
        self.status_card.add_widget(self.unavailable_label)
        self.status_card.add_widget(self.refresh_button)
        layout.addWidget(self.status_card)

        guidance = InlineNotice(
            self.tr("Checks start explicitly"),
            self.tr("Use Check now on Home to collect a new read-only result. This page never polls or starts a check automatically."),
            kind="neutral",
        )
        guidance.setObjectName("systemCheckExplicitGuidance")
        layout.addWidget(guidance)
        layout.addStretch()
        return page

    def _findings_page(self) -> QWidget:
        page = QWidget()
        self.findings_layout = QVBoxLayout(page)
        self.findings_layout.setContentsMargins(0, 0, 0, 0)
        self.findings_layout.setSpacing(12)
        return page

    def _history_page(self) -> QWidget:
        page = QWidget()
        self.history_layout = QVBoxLayout(page)
        self.history_layout.setContentsMargins(0, 0, 0, 0)
        self.history_layout.setSpacing(12)
        self.metric_disclosure = DetailsDisclosure(
            summary=self.tr("Show supporting metric details")
        )
        self.metric_disclosure.setObjectName("systemCheckMetricDetails")
        self.metric_disclosure.details.setAccessibleName(self.tr("Supporting health metrics"))
        return page

    def refresh(self) -> None:
        """Reread both persisted stores without collection or mutation."""
        self._state = self.presentation_service.load(history_limit=30)
        self._render_overview(self._state)
        self._render_findings(self._state.findings)
        self._render_history(
            self._state.history,
            self._state.metrics,
            getattr(self._state, "comparison", None),
            getattr(self._state, "maintenance_outcomes", ()),
        )

    def _render_overview(self, state: SystemCheckPageState) -> None:
        kinds = {
            "completed": "success" if not state.findings else "warning",
            "partial": "warning",
            "cancelled": "neutral",
            "failed": "error",
            "unavailable": "neutral",
        }
        labels = {
            "completed": self.tr("Completed"),
            "partial": self.tr("Partially completed"),
            "cancelled": self.tr("Cancelled"),
            "failed": self.tr("Failed"),
            "unavailable": self.tr("No saved System Check"),
        }
        label = labels.get(state.latest_state, self.tr("Status unavailable"))
        self.status_badge.set_status(
            label,
            kind=kinds.get(state.latest_state, "neutral"),
            description=self.tr("%1 current finding(s)").replace("%1", str(len(state.findings))),
        )
        if state.latest_completed_at is None:
            checked = self.tr("Never")
        else:
            checked = datetime.fromtimestamp(state.latest_completed_at).astimezone().strftime("%Y-%m-%d %H:%M")
        self.last_checked_label.setText(
            self.tr("Last checked: %1 · Findings: %2")
            .replace("%1", checked)
            .replace("%2", str(len(state.findings)))
        )
        if state.unavailable_sources:
            self.unavailable_label.setText(
                self.tr("Unavailable sources: %1").replace("%1", ", ".join(state.unavailable_sources))
            )
            self.unavailable_label.show()
        else:
            self.unavailable_label.hide()

    def _render_findings(self, findings: tuple[FindingView, ...]) -> None:
        self._clear_layout(self.findings_layout)
        if not findings:
            self.findings_layout.addWidget(
                EmptyState(
                    self.tr("No current findings"),
                    self.tr("No finding is available in the latest saved System Check."),
                )
            )
        for finding in findings:
            card = Card(finding.title, finding.summary)
            card.setObjectName("systemCheckFinding")
            card.setProperty("severity", finding.severity)
            kind = "error" if finding.severity == "critical" else "warning"
            card.add_widget(
                StatusBadge(
                    self.tr("%1 · %2")
                    .replace("%1", finding.severity.title())
                    .replace("%2", finding.freshness_state.title()),
                    kind=kind,
                )
            )
            destination = self._review_destination_label(finding)
            route = QLabel(self.tr("Next review: %1").replace("%1", destination))
            route.setWordWrap(True)
            route.setObjectName("systemCheckFindingDestination")
            card.add_widget(route)
            if finding.manual_guidance:
                reason = (
                    self.tr("Reason: %1").replace(
                        "%1",
                        finding.manual_reason_code or self.tr("manual-review"),
                    )
                )
                guidance = QLabel(
                    self.tr("Manual guidance: %1\n%2")
                    .replace("%1", finding.manual_guidance)
                    .replace("%2", reason)
                )
                guidance.setWordWrap(True)
                guidance.setObjectName("systemCheckManualGuidance")
                card.add_widget(guidance)
            if finding.action_id:
                review_button = SecondaryButton(
                    self.tr("Review safe action"),
                    description=self.tr(
                        "Open the exact audited Action Center action. "
                        "Fresh preflight and explicit confirmation remain required."
                    ),
                )
                review_button.setObjectName("systemCheckReviewAction")
                review_button.clicked.connect(
                    lambda _checked=False, selected=finding: self._request_action_review(
                        selected
                    )
                )
                card.add_widget(review_button)
            self.findings_layout.addWidget(card)
        self.findings_layout.addStretch()

    def _render_history(
        self,
        history: tuple[HistoryView, ...],
        metrics: tuple[MetricView, ...],
        comparison: Any | None,
        maintenance_outcomes: tuple[MaintenanceOutcomeView, ...],
    ) -> None:
        self._clear_layout(self.history_layout, preserve=(self.metric_disclosure,))
        if comparison is not None:
            counts = comparison.to_dict()["counts"]
            card = Card(
                self.tr("Latest before/after comparison"),
                self.tr("System Check %1 compared with %2")
                .replace("%1", comparison.before_check_id)
                .replace("%2", comparison.after_check_id),
            )
            card.setObjectName("systemCheckComparison")
            card.add_widget(
                QLabel(
                    self.tr(
                        "Resolved: %1 · Unchanged: %2 · Worsened: %3 · "
                        "Not comparable: %4"
                    )
                    .replace("%1", str(counts["resolved"]))
                    .replace("%2", str(counts["unchanged"]))
                    .replace("%3", str(counts["worsened"]))
                    .replace("%4", str(counts["not_comparable"]))
                )
            )
            for outcome in comparison.outcomes:
                label = QLabel(
                    self.tr("%1: %2 (%3)")
                    .replace("%1", outcome.title)
                    .replace("%2", outcome.state.replace("_", " ").title())
                    .replace("%3", outcome.reason_code)
                )
                label.setWordWrap(True)
                label.setObjectName("systemCheckFindingOutcome")
                card.add_widget(label)
            self.history_layout.addWidget(card)

        for outcome in maintenance_outcomes:
            card = Card(
                self.tr("Linked maintenance"),
                self.tr("%1 · Run %2")
                .replace("%1", self._action_label(outcome.action_id))
                .replace("%2", outcome.run_id),
            )
            card.setObjectName("systemCheckMaintenanceOutcome")
            facts = QLabel(
                self.tr(
                    "Action Center verification: %1\n"
                    "Finding follow-up: %2\n"
                    "Reason: %3"
                )
                .replace("%1", outcome.verification_state.replace("_", " ").title())
                .replace("%2", outcome.resolution_state.replace("_", " ").title())
                .replace("%3", outcome.resolution_reason_code)
            )
            facts.setWordWrap(True)
            card.add_widget(facts)
            self.history_layout.addWidget(card)

        if not history:
            self.history_layout.addWidget(
                EmptyState(
                    self.tr("No saved history"),
                    self.tr("Existing health snapshots will appear here without migration."),
                )
            )
        for item in history:
            title = (
                self.tr("System Check")
                if item.source == "system-check"
                else self.tr("Legacy health snapshot")
            )
            timestamp = datetime.fromtimestamp(item.timestamp).astimezone().strftime("%Y-%m-%d %H:%M")
            card = Card(
                title,
                self.tr("%1 · %2 finding(s)").replace("%1", timestamp).replace("%2", str(item.finding_count)),
            )
            card.setObjectName("systemCheckHistoryItem")
            changes = QLabel(
                self.tr("New: %1 · Recurring: %2 · Resolved: %3")
                .replace("%1", str(item.new_count))
                .replace("%2", str(item.recurring_count))
                .replace("%3", str(item.resolved_count))
            )
            changes.setObjectName("systemCheckBeforeAfter")
            card.add_widget(changes)
            self.history_layout.addWidget(card)

        metric_lines = [
            self.tr("%1: min %2%5 · max %3%5 · avg %4%5 · %6 sample(s) · latest %7")
            .replace("%1", metric.metric_type)
            .replace("%2", f"{metric.minimum:.2f}")
            .replace("%3", f"{metric.maximum:.2f}")
            .replace("%4", f"{metric.average:.2f}")
            .replace("%5", metric.unit)
            .replace("%6", str(metric.count))
            .replace("%7", metric.last_timestamp)
            for metric in metrics
        ]
        self.metric_disclosure.set_details(
            "\n".join(metric_lines)
            if metric_lines
            else self.tr("No legacy metric samples are available.")
        )
        self.metric_disclosure.toggle_button.setChecked(False)
        self.history_layout.addWidget(self.metric_disclosure)
        self.history_layout.addStretch()

    def select_view(self, view_id: str) -> bool:
        index = self._SECTION_INDEX.get(str(view_id))
        if index is None:
            return False
        self.view_switcher.set_active_view(str(view_id))
        self.stack.setCurrentIndex(index)
        return True

    def activate_route(self, route: Any) -> bool:
        """Preselect the correct canonical view for stable compatibility routes."""
        route_id = str(getattr(route, "id", "") or "")
        if route_id in {"health", "maintenance:health-timeline"}:
            self._origin_route = route_id
        subroute = str(getattr(route, "subroute", "") or "")
        if route_id == "maintenance:health-timeline" or subroute in {"history", "timeline", "health-timeline"}:
            return self.select_view("history")
        if subroute == "findings":
            return self.select_view("findings")
        return self.select_view("overview")

    def _request_action_review(self, finding: FindingView) -> None:
        state = self._state
        if (
            state is None
            or not state.latest_check_id
            or not finding.action_id
            or finding.freshness_state != "fresh"
        ):
            return
        self.findingActionReviewRequested.emit(
            finding.action_id,
            {
                "check_result_id": state.latest_check_id,
                "finding_fingerprint": finding.fingerprint,
                "origin_route": self._origin_route,
            },
        )

    def _review_destination_label(self, finding: FindingView) -> str:
        if finding.route_id:
            from core.product_catalog import catalog_entry

            entry = catalog_entry(finding.route_id)
            if entry is not None:
                return self.tr(entry.route.label)
        if finding.action_id:
            return self._action_label(finding.action_id)
        if finding.manual_guidance:
            return self.tr("Manual guidance")
        return self.tr("Review details")

    def _action_label(self, action_id: str) -> str:
        from core.actions.catalog import ActionCatalog

        definition = ActionCatalog().get(action_id)
        return (
            self.tr(definition.title)
            if definition is not None
            else self.tr("Action Center review")
        )

    def resizeEvent(self, event: Any) -> None:
        compact = self.width() < 900
        self.view_switcher.set_compact(compact)
        super().resizeEvent(event)

    @staticmethod
    def _clear_layout(layout: QVBoxLayout, *, preserve: tuple[QWidget, ...] = ()) -> None:
        kept = set(preserve)
        while layout.count():
            item = layout.takeAt(0)
            if item is None:
                continue
            widget = item.widget()
            if widget is not None and widget not in kept:
                widget.deleteLater()
