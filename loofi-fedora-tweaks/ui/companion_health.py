"""Local saved-session comparison and editable community support drafts."""
from __future__ import annotations

from datetime import datetime
from typing import Any

from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import (
    QComboBox, QDialog, QDialogButtonBox, QFileDialog, QLabel, QPlainTextEdit, QVBoxLayout,
)

from core.export.support_question import SupportQuestionService
from core.troubleshooting.comparison import compare_sessions
from core.troubleshooting.models import TroubleshootingComparison, TroubleshootingSession
from ui.components import Card, SecondaryButton


class CompanionHealthMixin:
    """Use saved history without collecting again or choosing a baseline implicitly."""

    _saved_sessions: tuple[TroubleshootingSession, ...]
    _comparison: TroubleshootingComparison | None
    _stop_timer: QTimer | None

    def _build_companion_health(self: Any, layout: Any) -> None:
        card = Card(self.tr("Compare saved checks"), self.tr("Choose a saved result and an earlier baseline. Incomplete evidence is never treated as resolved."))
        self.saved_session_selector = QComboBox()
        self.saved_session_selector.setAccessibleName(self.tr("Saved troubleshooting result"))
        self.saved_session_selector.setObjectName("healthSavedSession")
        self.baseline_selector = QComboBox()
        self.baseline_selector.setAccessibleName(self.tr("Earlier comparison baseline"))
        self.baseline_selector.setObjectName("healthComparisonBaseline")
        card.add_widget(QLabel(self.tr("Saved result")))
        card.add_widget(self.saved_session_selector)
        card.add_widget(QLabel(self.tr("Baseline")))
        card.add_widget(self.baseline_selector)
        self.compare_saved_button = SecondaryButton(self.tr("Compare with earlier check"))
        self.compare_saved_button.clicked.connect(self._compare_saved)
        card.add_widget(self.compare_saved_button)
        self.support_question_button = SecondaryButton(self.tr("Prepare a support question"))
        self.support_question_button.clicked.connect(self._prepare_support_question)
        card.add_widget(self.support_question_button)
        layout.addWidget(card)
        self._saved_sessions = ()
        self.saved_session_selector.currentIndexChanged.connect(self._saved_session_selected)

    def _refresh_saved_sessions(self: Any) -> None:
        try:
            reader = getattr(self.history, "sessions", None)
            sessions = tuple(reader()) if callable(reader) else ()
        except (OSError, RuntimeError, TypeError, ValueError):
            sessions = ()
        self._saved_sessions = tuple(sessions)
        self.saved_session_selector.blockSignals(True)
        self.saved_session_selector.clear()
        for session in self._saved_sessions:
            self.saved_session_selector.addItem(self._saved_session_label(session), session.session_id)
        if self._current_session is not None:
            index = self.saved_session_selector.findData(self._current_session.session_id)
            self.saved_session_selector.setCurrentIndex(index)
        self.saved_session_selector.blockSignals(False)
        self._refresh_baselines()

    def _saved_session_label(self: Any, session: Any) -> str:
        when = datetime.fromtimestamp(session.completed_at or session.started_at).astimezone().strftime("%Y-%m-%d %H:%M:%S")
        return str(self.tr("%1 · %2 · %3").replace("%1", when).replace("%2", session.profile_id).replace("%3", session.session_id[:8]))

    def _refresh_baselines(self: Any) -> None:
        previous = self.baseline_selector.currentData()
        self.baseline_selector.clear()
        self.baseline_selector.addItem(self.tr("Choose an earlier saved check"), "")
        current = self._current_session
        if current is not None:
            for session in self._saved_sessions:
                if session.session_id != current.session_id and (session.completed_at or session.started_at) < (current.completed_at or current.started_at):
                    self.baseline_selector.addItem(self._saved_session_label(session), session.session_id)
        index = self.baseline_selector.findData(previous)
        if index >= 0:
            self.baseline_selector.setCurrentIndex(index)
        self.compare_saved_button.setEnabled(self.baseline_selector.count() > 1)
        self.support_question_button.setEnabled(current is not None and any(s.session_id == current.session_id for s in self._saved_sessions))

    def _saved_session_selected(self: Any, *_args: Any) -> None:
        selected = self.saved_session_selector.currentData()
        session = next((s for s in self._saved_sessions if s.session_id == selected), None)
        if session is None:
            return
        self._current_session = session
        self._render_session(session, None, "")
        self._refresh_baselines()

    def select_saved_session(self: Any, session_id: str) -> bool:
        """Select one exact saved check for review without collecting again."""
        requested = str(session_id or "").strip()
        if not requested:
            return False
        index = self.saved_session_selector.findData(requested)
        if index < 0:
            self._refresh_saved_sessions()
            index = self.saved_session_selector.findData(requested)
        if index < 0:
            self.result_notice.set_notice(
                "warning",
                self.tr("Saved result unavailable"),
                self.tr("The exact linked session is no longer available. No other session was selected."),
            )
            return False
        self.saved_session_selector.setCurrentIndex(index)
        self.view_switcher.set_active_view("results")
        self._select_view("results")
        return self._current_session is not None and self._current_session.session_id == requested

    def _compare_saved(self: Any) -> None:
        selected = self.baseline_selector.currentData()
        before = next((s for s in self._saved_sessions if s.session_id == selected), None)
        if before is None or self._current_session is None:
            return
        self._comparison = compare_sessions(before, self._current_session)
        self._render_comparison(self._comparison)

    def _prepare_support_question(self: Any) -> None:
        session = self._current_session
        if session is None:
            return
        # Read only this exact saved UUID; the service never refreshes diagnostics.
        dialog = QDialog(self)
        dialog.setWindowTitle(self.tr("Prepare a support question"))
        dialog.resize(700, 600)
        layout = QVBoxLayout(dialog)
        layout.addWidget(QLabel(self.tr("Describe the problem and steps. Review and edit the masked preview before exporting locally.")))
        problem = QPlainTextEdit()
        problem.setAccessibleName(self.tr("Problem description"))
        problem.setPlaceholderText(self.tr("What happened, and what did you expect?"))
        steps = QPlainTextEdit()
        steps.setAccessibleName(self.tr("Steps to reproduce"))
        steps.setPlaceholderText(self.tr("Steps to reproduce the problem"))
        preview = QPlainTextEdit()
        preview.setAccessibleName(self.tr("Editable support question preview"))
        notice = QLabel()
        notice.setWordWrap(True)
        for widget in (problem, steps, preview, notice):
            layout.addWidget(widget)
        generate = SecondaryButton(self.tr("Prepare masked preview"))
        export = SecondaryButton(self.tr("Export Markdown or ZIP"))
        export.setEnabled(False)
        service = SupportQuestionService()

        def prepare() -> None:
            try:
                preview.setPlainText(service.preview(session.session_id, problem.toPlainText(), steps.toPlainText()))
                export.setEnabled(True)
                notice.setText(self.tr("Review the draft for private details before sharing it."))
            except (OSError, LookupError, RuntimeError, ValueError) as exc:
                export.setEnabled(False)
                notice.setText(self.tr("Could not prepare the selected saved check: %1").replace("%1", str(exc)))

        def save() -> None:
            path, selected_filter = QFileDialog.getSaveFileName(dialog, self.tr("Export support question"), "support-question.md",
                                                                self.tr("Markdown (*.md);;ZIP (*.zip)"))
            if not path:
                return
            if not path.lower().endswith((".md", ".zip")):
                path += ".zip" if "*.zip" in selected_filter else ".md"
            try:
                service.export(path, preview.toPlainText())
                notice.setText(self.tr("Saved locally. No question was published."))
            except (OSError, RuntimeError, ValueError) as exc:
                notice.setText(self.tr("Export failed: %1").replace("%1", str(exc)))

        generate.clicked.connect(prepare)
        export.clicked.connect(save)
        layout.addWidget(generate)
        layout.addWidget(export)
        close = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        close.rejected.connect(dialog.reject)
        layout.addWidget(close)
        dialog.exec()

    def _render_comparison(
        self: Any,
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
        baseline = next((s for s in self._saved_sessions if s.session_id == comparison.before_session_id), None)
        titles: dict[str, str] = {f.fingerprint: self.tr(f.title) for f in baseline.findings} if baseline else {}
        labels = {"resolved": self.tr("Resolved"), "unchanged": self.tr("Unchanged"),
                  "worsened": self.tr("Worsened"), "not_comparable": self.tr("Not comparable")}
        detail = [self.tr("Baseline: %1\nResult: %2").replace("%1", comparison.before_session_id).replace("%2", comparison.after_session_id)]
        for outcome in comparison.outcomes:
            detail.append(self.tr("%1: %2 (%3)").replace("%1", titles.get(outcome.original_fingerprint, outcome.original_fingerprint))
                          .replace("%2", labels[outcome.state]).replace("%3", outcome.reason_code))
        self.comparison_label.setText(self.comparison_label.text() + "\n" + "\n".join(detail))
        self.comparison_card.show()

    @property
    def busy(self: Any) -> bool:
        return self._worker is not None and bool(self._worker.isRunning())

    def request_stop(self: Any) -> None:
        """Keep ownership until cooperative readers stop before window teardown."""
        self._closing = True
        if self._worker is not None and self._worker.isRunning():
            self._worker.cancel()
            if self._stop_timer is None:
                self._stop_timer = QTimer(self)
                self._stop_timer.setInterval(25)
                self._stop_timer.timeout.connect(self._check_stopped)
            self._stop_timer.start()
        else:
            self._check_stopped()

    def _check_stopped(self: Any) -> None:
        if self.busy:
            return
        if self._stop_timer is not None:
            self._stop_timer.stop()
        worker, self._worker = self._worker, None
        if worker is not None:
            worker.deleteLater()
        self.stopped.emit()

    def cleanup(self: Any) -> None:
        self.request_stop()
