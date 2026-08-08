"""Presentation-only Compass troubleshooting journey."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from typing import Any, Protocol

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from core.troubleshooting.models import (
    NextStep,
    TroubleshootingComparison,
    TroubleshootingFinding,
    TroubleshootingSession,
)
from core.troubleshooting.profiles import require_profile
from ui.components import (
    ActionBar,
    ActionProgress,
    Card,
    DetailsDisclosure,
    EmptyState,
    GhostButton,
    InlineNotice,
    LocalViewItem,
    LocalViewSwitcher,
    PageScaffold,
    PrimaryButton,
    SecondaryButton,
    SectionHeader,
    StatusBadge,
)
from ui.troubleshoot_presentation import (
    SESSION_STATUS,
    SOURCE_LABELS,
    STATE_LABELS,
    SYMPTOMS,
)


class _SessionHistory(Protocol):
    def latest(self) -> tuple[TroubleshootingSession | None, str]:
        ...


class _DefaultSessionHistory:
    """Read the existing bounded store without collecting or writing."""

    def latest(self) -> tuple[TroubleshootingSession | None, str]:
        from core.troubleshooting.storage import TroubleshootingSessionStore

        try:
            snapshot = TroubleshootingSessionStore().read()
        except (OSError, RuntimeError, TypeError, ValueError):
            return None, "session-store-unavailable"
        return (
            snapshot.sessions[0] if snapshot.sessions else None,
            snapshot.reason_code,
        )


class TroubleshootWidget(QWidget):
    """One guided surface over the closed Compass profiles."""

    actionCenterRequested = pyqtSignal(str, object)
    routeRequested = pyqtSignal(str, object)

    _SOURCE_LABELS = SOURCE_LABELS
    _STATE_LABELS = STATE_LABELS
    _SYMPTOMS = SYMPTOMS

    def __init__(
        self,
        *,
        worker_factory: Callable[[str, dict[str, Any], QWidget], Any] | None = None,
        history: _SessionHistory | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.worker_factory = worker_factory
        self.history = history or _DefaultSessionHistory()
        self._worker: Any | None = None
        self._closing = False
        self._current_session: TroubleshootingSession | None = None
        self._comparison: TroubleshootingComparison | None = None
        self._selected_finding: TroubleshootingFinding | None = None
        self._setup_ui()
        self._load_latest_session()

    def _setup_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        self.scaffold = PageScaffold(
            self.tr("Troubleshoot"),
            self.tr(
                "Choose what is going wrong, run a read-only check, "
                "and review one safe next step."
            ),
        )
        root.addWidget(self.scaffold)

        self.safety_notice = InlineNotice(
            self.tr("Read-only and explicit"),
            self.tr(
                "Checks start only when you choose Start. Troubleshoot never applies "
                "a change, confirms a plan, or restarts the system."
            ),
            kind="info",
        )
        self.safety_notice.setObjectName("troubleshootSafety")
        self.scaffold.add_widget(self.safety_notice)

        view_row = QHBoxLayout()
        self.view_label = QLabel(self.tr("View"))
        self.view_label.setAccessibleName(self.tr("Troubleshoot view"))
        view_row.addWidget(self.view_label)
        self.view_switcher = LocalViewSwitcher()
        self.view_switcher.setObjectName("troubleshootViewSwitcher")
        self.view_switcher.set_views(
            [
                LocalViewItem(
                    "guided",
                    self.tr("Guided check"),
                    self.tr("Choose a problem and review what will be checked."),
                ),
                LocalViewItem(
                    "results",
                    self.tr("Results"),
                    self.tr("Review the current or latest completed session."),
                ),
            ]
        )
        self.view_switcher.viewActivated.connect(self._select_view)
        view_row.addWidget(self.view_switcher, 1)
        self.scaffold.add_layout(view_row)

        self.stack = QStackedWidget()
        self.stack.setObjectName("troubleshootViewStack")
        self.stack.addWidget(self._guided_page())
        self.stack.addWidget(self._results_page())
        self.scaffold.add_widget(self.stack, 1)

    def _guided_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(16)

        choose = Card(
            self.tr("1. Problem"),
            self.tr("Start from the symptom you can observe."),
        )
        choose.setObjectName("troubleshootProfileCard")
        self.profile_label = QLabel(self.tr("What is going wrong?"))
        self.profile_selector = QComboBox()
        self.profile_selector.setObjectName("troubleshootProfileSelector")
        self.profile_selector.setAccessibleName(self.tr("Troubleshooting symptom"))
        self.profile_label.setBuddy(self.profile_selector)
        choose.add_widget(self.profile_label)
        for symptom_id, label, _profile_id, _limitation in self._SYMPTOMS:
            self.profile_selector.addItem(self.tr(label), symptom_id)
        self.profile_selector.currentIndexChanged.connect(self._profile_changed)
        choose.add_widget(self.profile_selector)
        self.application_input = QLineEdit()
        self.application_input.setObjectName("troubleshootApplicationId")
        self.application_input.setAccessibleName(self.tr("Application command"))
        self.application_input.setPlaceholderText(self.tr("Application command, for example firefox"))
        self.application_input.hide()
        choose.add_widget(self.application_input)
        self.profile_limitation = InlineNotice("", "", kind="warning")
        self.profile_limitation.setObjectName("troubleshootProfileLimitation")
        self.profile_limitation.hide()
        choose.add_widget(self.profile_limitation)
        layout.addWidget(choose)

        checks = Card(
            self.tr("2. Checks"),
            self.tr("Review the system areas included in this read-only check."),
        )
        checks.setObjectName("troubleshootChecksCard")
        self.checks_label = QLabel()
        self.checks_label.setWordWrap(True)
        self.checks_label.setObjectName("troubleshootChecks")
        self.checks_label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByKeyboard
            | Qt.TextInteractionFlag.TextSelectableByMouse
        )
        checks.add_widget(self.checks_label)
        self.technical_disclosure = DetailsDisclosure(
            summary=self.tr("Show technical details")
        )
        self.technical_disclosure.setObjectName("troubleshootTechnicalDetails")
        self.variant_label = QLabel(
            self.tr("Fedora variant is detected when the session starts.")
        )
        self.variant_label.setWordWrap(True)
        self.variant_label.setObjectName("troubleshootVariantPreview")
        self.technical_budget_label = QLabel()
        self.technical_budget_label.setWordWrap(True)
        self.technical_budget_label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByKeyboard
            | Qt.TextInteractionFlag.TextSelectableByMouse
        )
        self.technical_disclosure.add_widget(self.variant_label)
        self.technical_disclosure.add_widget(self.technical_budget_label)
        checks.add_widget(self.technical_disclosure)
        layout.addWidget(checks)

        self.start_notice = InlineNotice("", "", kind="neutral")
        self.start_notice.setObjectName("troubleshootStartNotice")
        self.start_notice.hide()
        layout.addWidget(self.start_notice)

        self.action_bar = ActionBar()
        self.cancel_button = GhostButton(
            self.tr("Cancel"),
            description=self.tr(
                "Stop the running session and keep the previous completed session."
            ),
        )
        self.cancel_button.setObjectName("troubleshootCancel")
        self.cancel_button.clicked.connect(self.cancel_session)
        self.cancel_button.hide()
        self.action_bar.add_action(self.cancel_button)
        self.start_button = PrimaryButton(
            self.tr("Start read-only check"),
            description=self.tr("Run the checks for the selected symptom."),
        )
        self.start_button.setObjectName("troubleshootStart")
        self.start_button.clicked.connect(self.start_session)
        self.action_bar.add_action(self.start_button, primary=True)
        layout.addWidget(self.action_bar)

        self.progress = ActionProgress(self.tr("Preparing the selected check…"))
        self.progress.setObjectName("troubleshootProgress")
        self.progress.hide()
        self.progress_source = QLabel()
        self.progress_source.setObjectName("troubleshootProgressSource")
        self.progress_source.setWordWrap(True)
        self.progress.details_layout.addWidget(self.progress_source)
        layout.addWidget(self.progress)
        layout.addStretch()
        self._profile_changed()
        return page

    def _results_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(16)
        layout.addWidget(
            SectionHeader(
                self.tr("3. Results"),
                self.tr("Review what completed, what did not, and the safest next step."),
            )
        )
        self.result_notice = InlineNotice(
            self.tr("No troubleshooting session yet"),
            self.tr("Choose a problem and start an explicit read-only check."),
            kind="neutral",
        )
        self.result_notice.setObjectName("troubleshootResultNotice")
        layout.addWidget(self.result_notice)

        self.result_summary = Card(self.tr("Session summary"))
        self.result_summary.setObjectName("troubleshootSessionSummary")
        self.result_badge = StatusBadge(self.tr("No session"), kind="neutral")
        self.result_summary.add_widget(self.result_badge)
        self.result_meta = QLabel()
        self.result_meta.setObjectName("troubleshootResultMeta")
        self.result_meta.setWordWrap(True)
        self.result_summary.add_widget(self.result_meta)
        self.partial_warning = InlineNotice("", "", kind="warning")
        self.partial_warning.setObjectName("troubleshootPartialWarning")
        self.partial_warning.hide()
        self.result_summary.add_widget(self.partial_warning)
        self.result_checked = QLabel()
        self.result_checked.setObjectName("troubleshootCheckedSummary")
        self.result_checked.setWordWrap(True)
        self.result_summary.add_widget(self.result_checked)
        self.sources_disclosure = DetailsDisclosure(
            summary=self.tr("Show technical details")
        )
        self.sources_disclosure.setObjectName("troubleshootSourceDisclosure")
        self.result_summary.add_widget(self.sources_disclosure)
        layout.addWidget(self.result_summary)

        findings = Card(
            self.tr("Current findings"),
            self.tr("Select a finding to review its evidence and one safe next step."),
        )
        findings.setObjectName("troubleshootFindingsCard")
        self.finding_list = QListWidget()
        self.finding_list.setObjectName("troubleshootFindingList")
        self.finding_list.setAccessibleName(self.tr("Troubleshooting findings"))
        self.finding_list.currentRowChanged.connect(self._finding_selected)
        findings.add_widget(self.finding_list)
        self.finding_empty = EmptyState(
            self.tr("No current findings"),
            self.tr(
                "No issue was found by the checks that completed. "
                "Review incomplete checks before treating this as an all-clear."
            ),
        )
        self.finding_empty.setObjectName("troubleshootFindingEmpty")
        findings.add_widget(self.finding_empty)
        layout.addWidget(findings)

        self.finding_detail = Card(self.tr("Selected finding"))
        self.finding_detail.setObjectName("troubleshootFindingDetail")
        self.finding_status = StatusBadge(self.tr("No finding selected"), kind="neutral")
        self.finding_detail.add_widget(self.finding_status)
        self.finding_summary = QLabel()
        self.finding_summary.setWordWrap(True)
        self.finding_summary.setObjectName("troubleshootFindingSummary")
        self.finding_detail.add_widget(self.finding_summary)
        self.evidence_disclosure = DetailsDisclosure(
            summary=self.tr("Show technical evidence")
        )
        self.evidence_disclosure.setObjectName("troubleshootEvidenceDisclosure")
        self.finding_detail.add_widget(self.evidence_disclosure)
        self.next_step_label = QLabel()
        self.next_step_label.setWordWrap(True)
        self.next_step_label.setObjectName("troubleshootNextStepLabel")
        self.finding_detail.add_widget(self.next_step_label)
        self.next_step_button = SecondaryButton(
            self.tr("Open safe next step"),
            description=self.tr(
                "Open the existing route or Action Center handoff. "
                "No change is applied automatically."
            ),
        )
        self.next_step_button.setObjectName("troubleshootNextStep")
        self.next_step_button.clicked.connect(self._activate_next_step)
        self.finding_detail.add_widget(self.next_step_button)
        self.finding_detail.hide()
        layout.addWidget(self.finding_detail)

        self.related_card = Card(
            self.tr("Possibly related"),
            self.tr(
                "These changes happened nearby in time or affect the same component. "
                "They are not presented as proven causes."
            ),
        )
        self.related_card.setObjectName("troubleshootRelatedChanges")
        self.related_label = QLabel()
        self.related_label.setWordWrap(True)
        self.related_card.add_widget(self.related_label)
        self.related_card.hide()
        layout.addWidget(self.related_card)

        self.comparison_card = Card(
            self.tr("Follow-up comparison"),
            self.tr(
                "A later compatible session can show whether each original finding "
                "is resolved, unchanged, worsened, or not comparable."
            ),
        )
        self.comparison_card.setObjectName("troubleshootComparison")
        self.comparison_label = QLabel()
        self.comparison_label.setWordWrap(True)
        self.comparison_card.add_widget(self.comparison_label)
        self.comparison_card.hide()
        layout.addWidget(self.comparison_card)

        layout.addStretch()
        return page

    def _profile_changed(self, *_args: Any) -> None:
        profile = require_profile(self.selected_profile_id())
        checked_areas = []
        technical_lines = []
        for budget in profile.source_budgets:
            label = self.tr(self._SOURCE_LABELS.get(budget.source_id, budget.source_id))
            checked_areas.append(self.tr("• %1").replace("%1", label))
            optional = self.tr("optional") if not budget.required else self.tr("required")
            variants = (
                self.tr("Traditional and Atomic")
                if len(budget.variants) == 2
                else self.tr("Atomic")
                if "atomic" in budget.variants
                else self.tr("Traditional")
            )
            technical_lines.append(
                self.tr("• %1 — up to %2 seconds · %3 · %4")
                .replace("%1", label)
                .replace("%2", f"{budget.timeout_seconds:g}")
                .replace("%3", optional)
                .replace("%4", variants)
            )
        self.checks_label.setText("\n".join(checked_areas))
        self.technical_budget_label.setText("\n".join(technical_lines))
        requires_application = dict(profile.parameter_schema).get("application_id") is not None
        self.application_input.setVisible(requires_application)
        symptom_limitation = self._selected_symptom()[3]
        if symptom_limitation:
            message = self.tr(symptom_limitation)
        elif profile.availability == "reduced":
            message = {
                "application-journal-collector-unavailable": self.tr(
                    "Application logs are not included in this check."
                ),
                "network-scan-excluded": self.tr(
                    "Network scanning is not included. Only the local connection and DNS settings are checked."
                ),
            }.get(
                profile.limitation_reason_code,
                self.tr("Some checks are not available for this symptom."),
            )
        else:
            message = ""
        if message:
            self.profile_limitation.set_notice(
                "warning",
                self.tr("Some checks are unavailable"),
                message,
            )
            self.profile_limitation.show()
        else:
            self.profile_limitation.hide()

    def selected_profile_id(self) -> str:
        return self._selected_symptom()[2]

    def _selected_symptom(self) -> tuple[str, str, str, str]:
        symptom_id = str(self.profile_selector.currentData() or self._SYMPTOMS[0][0])
        return next(
            (symptom for symptom in self._SYMPTOMS if symptom[0] == symptom_id),
            self._SYMPTOMS[0],
        )

    def start_session(self) -> None:
        """Create the worker only after direct user activation."""
        if self._worker is not None and self._worker.isRunning():
            return
        profile = require_profile(self.selected_profile_id())
        parameters: dict[str, Any] = {}
        if dict(profile.parameter_schema).get("application_id") is not None:
            application_id = self.application_input.text().strip()
            if not application_id:
                self.start_notice.set_notice(
                    "warning",
                    self.tr("Application is required"),
                    self.tr("Enter the application command before starting this profile."),
                )
                self.start_notice.show()
                self.application_input.setFocus()
                return
            parameters["application_id"] = application_id

        if self.worker_factory is None:
            from core.workers.troubleshooting_worker import TroubleshootingWorker

            worker = TroubleshootingWorker(
                profile.id,
                parameters=parameters,
                parent=self,
            )
        else:
            worker = self.worker_factory(profile.id, parameters, self)
        self._worker = worker
        self.start_notice.hide()
        self.progress.set_busy(self.tr("Starting the read-only check…"))
        self.progress_source.setText(self.tr("Current source: Preparing"))
        self.progress.show()
        self.start_button.set_loading(True, self.tr("Checking…"))
        self.cancel_button.setEnabled(True)
        self.cancel_button.show()
        worker.source_progress.connect(self._on_progress)
        worker.finished.connect(self._on_finished)
        worker.error.connect(self._on_error)
        worker.start()

    def cancel_session(self) -> None:
        worker = self._worker
        if worker is None or not worker.isRunning():
            return
        self.cancel_button.setEnabled(False)
        self.progress.set_busy(self.tr("Cancelling and preserving the previous session…"))
        worker.cancel()

    def _on_progress(self, progress: Any) -> None:
        if self._closing:
            return
        source_id = str(getattr(progress, "source_id", "") or "")
        state = str(getattr(progress, "state", "running") or "running")
        percentage = int(getattr(progress, "percentage", 0) or 0)
        label = self.tr(self._SOURCE_LABELS.get(source_id, source_id or "Finalizing"))
        state_label = self.tr(self._STATE_LABELS.get(state, "Running"))
        self.progress.set_progress(
            percentage,
            self.tr("%1 — %2").replace("%1", label).replace("%2", state_label),
        )
        self.progress_source.setText(
            self.tr("Current source: %1").replace("%1", label)
        )

    def _on_finished(self, outcome: Any) -> None:
        if self._closing:
            return
        self._current_session = outcome.session
        self._comparison = getattr(outcome, "comparison", None)
        self._finish_worker()
        self._render_session(
            outcome.session,
            self._comparison,
            str(getattr(outcome, "persistence_reason_code", "") or ""),
        )
        self.view_switcher.set_active_view("results")
        self._select_view("results")

    def _on_error(self, _message: str) -> None:
        if self._closing:
            return
        self._finish_worker()
        self.start_notice.set_notice(
            "error",
            self.tr("Troubleshooting could not finish"),
            self.tr(
                "No result replaced the previous completed session. "
                "Review source availability and try again."
            ),
        )
        self.start_notice.show()

    def _finish_worker(self) -> None:
        worker = self._worker
        self._worker = None
        self.progress.hide()
        self.cancel_button.hide()
        self.start_button.set_loading(False)
        self.start_button.setText(
            self.tr("Check again")
            if self._current_session is not None
            else self.tr("Start read-only check")
        )
        if worker is not None:
            worker.wait(1000)
            worker.deleteLater()

    def _load_latest_session(self) -> None:
        session, reason_code = self.history.latest()
        if session is None:
            if reason_code:
                self.result_notice.set_notice(
                    "warning",
                    self.tr("Previous sessions are unavailable"),
                    self.tr(
                        "The session store could not be read safely. "
                        "Starting a check will not overwrite an unknown future schema."
                    ),
                )
            return
        self._current_session = session
        self._render_session(session, None, reason_code)
        self.start_button.setText(self.tr("Check again"))
        symptom_id = next(
            (
                symptom[0]
                for symptom in self._SYMPTOMS
                if symptom[2] == session.profile_id
            ),
            "",
        )
        index = self.profile_selector.findData(symptom_id)
        if index >= 0:
            self.profile_selector.setCurrentIndex(index)

    def _render_session(
        self,
        session: TroubleshootingSession,
        comparison: TroubleshootingComparison | None,
        persistence_reason_code: str,
    ) -> None:
        profile = require_profile(session.profile_id)
        state_text, kind = SESSION_STATUS.get(
            session.state,
            ("Status unavailable", "neutral"),
        )
        state_label = self.tr(state_text)
        self.result_notice.set_notice(
            kind,
            state_label,
            self._session_message(session),
        )
        self.result_badge.set_status(
            self.tr("%1 · %2")
            .replace("%1", self.tr(profile.title))
            .replace("%2", state_label),
            kind=kind,
        )
        completed = (
            datetime.fromtimestamp(session.completed_at).astimezone().strftime("%Y-%m-%d %H:%M")
            if session.completed_at is not None
            else self.tr("Not completed")
        )
        variant = self.tr("Atomic Fedora") if session.variant == "atomic" else self.tr("Traditional Fedora")
        self.result_meta.setText(
            self.tr("Fedora variant: %1 · Completed: %2 · Findings: %3")
            .replace("%1", variant)
            .replace("%2", completed)
            .replace("%3", str(len(session.findings)))
        )
        checked = [
            self.tr(self._SOURCE_LABELS.get(result.source_id, result.source_id))
            for result in session.source_results
        ]
        self.result_checked.setText(
            self.tr("Checked: %1").replace(
                "%1",
                ", ".join(checked) if checked else self.tr("No checks completed"),
            )
        )
        incomplete = tuple(
            result
            for result in session.source_results
            if result.state not in {"completed", "empty"}
        )
        if incomplete or persistence_reason_code:
            messages = []
            if incomplete:
                messages.append(
                    self.tr("Incomplete sources: %1").replace(
                        "%1",
                        ", ".join(
                            self.tr(self._SOURCE_LABELS.get(item.source_id, item.source_id))
                            for item in incomplete
                        ),
                    )
                )
            if persistence_reason_code:
                messages.append(
                    self.tr(
                        "This result could not be added to writable session history."
                    )
                )
            self.partial_warning.set_notice(
                "warning",
                self.tr("Result is not a complete all-clear"),
                " ".join(messages),
            )
            self.partial_warning.show()
        else:
            self.partial_warning.hide()
        self.sources_disclosure.set_details(self._source_details(session))

        self.finding_list.clear()
        for finding in session.findings:
            self.finding_list.addItem(
                self.tr("%1 · %2")
                .replace("%1", self.tr(finding.title))
                .replace("%2", self.tr(finding.severity.title()))
            )
        self.finding_empty.setVisible(not session.findings)
        self.finding_list.setVisible(bool(session.findings))
        self.finding_detail.setVisible(bool(session.findings))
        if session.findings:
            self.finding_list.setCurrentRow(0)
        else:
            self._selected_finding = None

        if session.related_changes:
            lines = []
            for change in session.related_changes:
                when = datetime.fromtimestamp(change.occurred_at).astimezone().strftime("%Y-%m-%d %H:%M")
                reasons = ", ".join(
                    self.tr(reason.replace("_", " "))
                    for reason in sorted(change.match_reasons)
                )
                lines.append(
                    self.tr("Possibly related · %1 · %2 · %3")
                    .replace("%1", when)
                    .replace("%2", reasons)
                    .replace("%3", ", ".join(change.affected_resources))
                )
            self.related_label.setText("\n".join(lines))
            self.related_card.show()
        else:
            self.related_card.hide()

        self._render_comparison(comparison)

    def _session_message(self, session: TroubleshootingSession) -> str:
        if session.state == "completed":
            return (
                self.tr("%1 finding(s) need review.").replace(
                    "%1", str(len(session.findings))
                )
                if session.findings
                else self.tr("All applicable sources completed without a current finding.")
            )
        if session.state == "partial":
            return self.tr(
                "Some checks were unavailable, out of date, incomplete, or timed out. "
                "The result is not an all-clear."
            )
        if session.state == "cancelled":
            return self.tr(
                "The session was cancelled. The previous completed session was preserved."
            )
        return self.tr(
            "The check failed without enough usable results for a conclusion."
        )

    def _source_details(self, session: TroubleshootingSession) -> str:
        lines = []
        for result in session.source_results:
            label = self.tr(self._SOURCE_LABELS.get(result.source_id, result.source_id))
            state = self.tr(self._STATE_LABELS.get(result.state, result.state.title()))
            completed = datetime.fromtimestamp(result.completed_at).astimezone().strftime("%Y-%m-%d %H:%M:%S")
            lines.append(
                self.tr("%1\nState: %2\nCollected: %3\nFreshness/readiness reason: %4")
                .replace("%1", label)
                .replace("%2", state)
                .replace("%3", completed)
                .replace("%4", result.reason_code or self.tr("current"))
            )
        return "\n\n".join(lines)

    def _finding_selected(self, row: int) -> None:
        session = self._current_session
        if session is None or not 0 <= row < len(session.findings):
            self._selected_finding = None
            self.finding_detail.hide()
            return
        finding = session.findings[row]
        self._selected_finding = finding
        kind = "error" if finding.severity == "critical" else "warning"
        confidence = {
            "confirmed": self.tr("High"),
            "supported": self.tr("Medium"),
            "limited": self.tr("Limited"),
        }.get(finding.evidence_quality, self.tr("Limited"))
        self.finding_status.set_status(
            self.tr("%1 · Confidence: %2")
            .replace("%1", self.tr(finding.severity.title()))
            .replace("%2", confidence),
            kind=kind,
        )
        self.finding_summary.setText(
            self.tr("Found: %1\nConfidence: %2")
            .replace("%1", self.tr(finding.summary))
            .replace("%2", confidence)
        )
        facts = "\n".join(
            f"{key}: {value}"
            for key, value in sorted(finding.evidence_dict().items())
        )
        self.evidence_disclosure.set_details(
            self.tr(
                "Source: %1\nEvidence quality: %2\nFreshness: %3\n"
                "Why this is shown: %4\nAffected resources: %5\nCollected: %6\n%7"
            )
            .replace(
                "%1",
                self.tr(self._SOURCE_LABELS.get(finding.source_id, finding.source_id)),
            )
            .replace("%2", self.tr(finding.evidence_quality.title()))
            .replace("%3", self.tr(finding.freshness.title()))
            .replace("%4", self.tr(finding.evidence_explanation))
            .replace("%5", ", ".join(finding.affected_resources))
            .replace(
                "%6",
                datetime.fromtimestamp(finding.collected_at).astimezone().strftime(
                    "%Y-%m-%d %H:%M:%S"
                ),
            )
            .replace("%7", facts)
        )
        label, enabled = self._next_step_presentation(finding.next_step)
        self.next_step_label.setText(label)
        self.next_step_button.setVisible(enabled)
        self.finding_detail.show()

    def _next_step_presentation(self, step: NextStep) -> tuple[str, bool]:
        if step.kind == "action":
            return (
                self.tr(
                    "Next step: open Action Center and create a plan for review. "
                    "Nothing runs automatically."
                ),
                True,
            )
        if step.kind == "navigation":
            return (
                self.tr("Next step: open the relevant settings. Nothing changes automatically."),
                True,
            )
        if step.kind == "collect":
            return (
                self.tr("Next safe step: collect the named additional read-only source."),
                True,
            )
        if step.kind == "manual":
            return (
                self.tr("Manual guidance: %1").replace("%1", self.tr(step.guidance)),
                False,
            )
        return (
            self.tr(
                "No safe automated next step is available. Review the evidence manually."
            ),
            False,
        )

    def _activate_next_step(self) -> None:
        finding = self._selected_finding
        if finding is None:
            return
        step = finding.next_step
        if step.kind == "action":
            self.actionCenterRequested.emit(step.target_id, step.parameters_dict())
        elif step.kind == "navigation":
            self.routeRequested.emit(step.target_id, step.parameters_dict())
        elif step.kind == "collect":
            self.start_notice.set_notice(
                "info",
                self.tr("Additional evidence remains explicit"),
                self.tr(
                    "Start the compatible profile again to collect the bounded source."
                ),
            )
            self.start_notice.show()
            self.view_switcher.set_active_view("guided")
            self._select_view("guided")

    def _render_comparison(
        self,
        comparison: TroubleshootingComparison | None,
    ) -> None:
        if comparison is None:
            self.comparison_card.hide()
            return
        counts = {
            "resolved": 0,
            "unchanged": 0,
            "worsened": 0,
            "not_comparable": 0,
        }
        for outcome in comparison.outcomes:
            counts[outcome.state] += 1
        self.comparison_label.setText(
            self.tr(
                "Resolved: %1 · Unchanged: %2 · Worsened: %3 · "
                "Not comparable: %4\nOverall: %5"
            )
            .replace("%1", str(counts["resolved"]))
            .replace("%2", str(counts["unchanged"]))
            .replace("%3", str(counts["worsened"]))
            .replace("%4", str(counts["not_comparable"]))
            .replace(
                "%5",
                self.tr("Comparable")
                if comparison.comparable
                else self.tr("Not fully comparable"),
            )
        )
        self.comparison_card.show()

    def _select_view(self, view_id: str) -> None:
        self.stack.setCurrentIndex(1 if view_id == "results" else 0)

    def cleanup(self) -> None:
        self._closing = True
        worker = self._worker
        if worker is None:
            return
        if worker.isRunning():
            worker.cancel()
            worker.wait(1000)
        if not worker.isRunning():
            worker.deleteLater()
        else:
            worker.setParent(None)
        self._worker = None
