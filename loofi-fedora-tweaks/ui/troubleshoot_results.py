"""Results presentation for the guided troubleshooting surface."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from PyQt6.QtWidgets import QLabel, QListWidget, QVBoxLayout, QWidget

from core.troubleshooting.models import (
    NextStep,
    TroubleshootingComparison,
    TroubleshootingFinding,
    TroubleshootingSession,
)
from core.troubleshooting.profiles import require_profile
from ui.components import (
    Card,
    DetailsDisclosure,
    EmptyState,
    InlineNotice,
    SectionHeader,
    SecondaryButton,
    StatusBadge,
)
from ui.troubleshoot_presentation import SESSION_STATUS


class TroubleshootResultsMixin:
    """Build and update the read-only results and follow-up views."""

    _selected_finding: TroubleshootingFinding | None

    def _results_page(self: Any) -> QWidget:
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

        from ui.space_guide import SpaceGuideCard

        self.space_guide = SpaceGuideCard(self)
        self.space_guide.actionRequested.connect(self.actionCenterRequested)
        self.space_guide.routeRequested.connect(self.routeRequested)
        self.space_guide.recheckRequested.connect(self._recheck_storage)
        self.space_guide.hide()
        layout.addWidget(self.space_guide)

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
                "Open the existing supported workflow or settings handoff. "
                "No change is applied automatically."
            ),
        )
        self.next_step_button.setObjectName("troubleshootNextStep")
        self.next_step_button.clicked.connect(self._activate_next_step)
        self.finding_detail.add_widget(self.next_step_button)
        self.recheck_button = SecondaryButton(self.tr("Recheck after returning"), description=self.tr("Run the read-only symptom check again only when you choose."))
        self.recheck_button.setObjectName("troubleshootRecheck")
        self.recheck_button.clicked.connect(self.start_session)
        self.recheck_button.hide()
        self.finding_detail.add_widget(self.recheck_button)
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

        self._build_companion_health(layout)

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

    def _load_latest_session(self: Any) -> None:
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
        self: Any,
        session: TroubleshootingSession,
        comparison: TroubleshootingComparison | None,
        persistence_reason_code: str,
    ) -> None:
        profile = require_profile(session.profile_id)
        storage = next((result for result in session.source_results if result.source_id == "storage-reclaim"), None)
        facts = storage.to_dict().get("facts", {}) if storage is not None else {}
        guide = facts.get("space_guide") if session.profile_id == "storage_pressure" else None
        self.space_guide.set_observation(guide if isinstance(guide, dict) else None)
        self._show_device_settings(profile.id)
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
        if persistence_reason_code:
            self.partial_warning.set_notice(
                "warning",
                self.tr("Session history is read-only"),
                self.tr("This result could not be added to writable session history."),
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

    def _recheck_storage(self: Any) -> None:
        self._select_symptom_card("storage_full")
        self.start_session()

    def _session_message(self: Any, session: TroubleshootingSession) -> str:
        if session.state == "completed":
            if session.profile_id == "screen_sharing_not_working":
                return str(self.tr("Existing services and advertised ScreenCast support were checked. Test actual screen sharing in your application yourself."))
            if session.profile_id in self.device_settings_cards:
                return str(self.tr("Device metadata was checked. Confirm actual playback or connectivity yourself."))
            return str(
                self.tr("%1 finding(s) need review.").replace(
                    "%1", str(len(session.findings))
                )
                if session.findings
                else self.tr("All applicable sources completed without a current finding.")
            )
        if session.state == "partial":
            return str(self.tr(
                "Some checks were incomplete. Review the available findings and source details before treating this as complete."
            ))
        if session.state == "cancelled":
            return str(self.tr(
                "The session was cancelled. The previous completed session was preserved."
            ))
        return str(self.tr(
            "The check failed without enough usable results for a conclusion."
        ))

    def _source_details(self: Any, session: TroubleshootingSession) -> str:
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

    def _finding_selected(self: Any, row: int) -> None:
        session = self._current_session
        if session is None or not 0 <= row < len(session.findings):
            self._selected_finding = None
            self.finding_detail.hide()
            return
        finding = session.findings[row]
        self._selected_finding = finding
        kind = "error" if finding.severity == "critical" else "info" if finding.severity == "info" else "warning"
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

    def _next_step_presentation(self: Any, step: NextStep) -> tuple[str, bool]:
        if step.kind == "action":
            return (
                self.tr(
                    "Next step: review the suggested change before applying it. "
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

    def _activate_next_step(self: Any) -> None:
        finding = self._selected_finding
        if finding is None:
            return
        step = finding.next_step
        if step.kind == "action":
            self.actionCenterRequested.emit(step.target_id, step.parameters_dict())
        elif step.kind == "navigation":
            self.recheck_button.show()
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
