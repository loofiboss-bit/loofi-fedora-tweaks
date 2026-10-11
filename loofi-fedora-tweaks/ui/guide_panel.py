"""Overview card for resumable guides and exact verified-result links."""

from __future__ import annotations

from typing import cast

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import QComboBox, QHBoxLayout, QInputDialog, QLabel, QListWidget, QListWidgetItem, QVBoxLayout, QWidget

from core.tasks.guides import (
    GUIDES,
    GUIDES_BY_ID,
    ProgressStatus,
    GuideProgressSnapshot,
    GuideStep,
    GuideProgressStore,
    EvidenceReferenceKind,
    guide_evidence,
    guide_evidence_exists,
)
from ui.components.actions import QuietButton, SecondaryButton
from ui.components.cards import Card
from ui.components.feedback import DetailsDisclosure


def _step_evidence_available(step: GuideStep, progress: object) -> bool:
    raw_evidence_kind = str(getattr(progress, "evidence_kind", ""))
    evidence_id = str(getattr(progress, "evidence_id", ""))
    if raw_evidence_kind not in {"", "action_run", "troubleshooting_session"}:
        return False
    evidence_kind = cast(EvidenceReferenceKind, raw_evidence_kind)
    action_ids = step.evidence_action_ids if evidence_kind == "action_run" else None
    return guide_evidence_exists(evidence_kind, evidence_id, action_ids=action_ids)


class GuidePanel(QWidget):
    """A navigation-only guide player; all mutations stay in their owning flows."""

    guideChanged = pyqtSignal(str)
    targetRequested = pyqtSignal(object)

    def __init__(self, parent: QWidget | None = None, *, store: GuideProgressStore | None = None) -> None:
        super().__init__(parent)
        self.store = store or GuideProgressStore()
        self.active_guide = ""
        self.active_step = ""
        self._snapshot: GuideProgressSnapshot | None = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.card = Card(
            self.tr("Everyday guides"),
            self.tr("Choose a goal and follow its steps across the existing Fedora workflows."),
            parent=self,
        )
        layout.addWidget(self.card)

        self.guide_selector = QComboBox(self.card)
        self.guide_selector.setObjectName("guideSelector")
        self.guide_selector.setAccessibleName(self.tr("Choose an everyday guide"))
        self.guide_selector.addItem(self.tr("Choose a guide"), "")
        for guide in GUIDES:
            self.guide_selector.addItem(self.tr(guide.title), guide.id)
            self.guide_selector.setItemData(self.guide_selector.count() - 1, self.tr(guide.description), Qt.ItemDataRole.ToolTipRole)
        self.guide_selector.currentIndexChanged.connect(self._guide_selected)
        self.card.add_widget(self.guide_selector)

        self.guide_description = QLabel(self.tr("Guide progress is saved locally and can be resumed."), self.card)
        self.guide_description.setWordWrap(True)
        self.guide_description.setObjectName("cardDescription")
        self.card.add_widget(self.guide_description)

        self.current_step_label = QLabel(self.tr("Choose a guide to see its next step."), self.card)
        self.current_step_label.setWordWrap(True)
        self.current_step_label.setObjectName("guideCurrentStep")
        self.card.add_widget(self.current_step_label)

        self.open_button = SecondaryButton(self.tr("Open next step"), parent=self.card)
        self.open_button.setAccessibleDescription(self.tr("Open the selected guide step without applying changes."))
        self.open_button.clicked.connect(self._open_step)
        self.card.add_widget(self.open_button)

        self.details_disclosure = DetailsDisclosure(summary=self.tr("Show guide steps and progress"), parent=self.card)
        self.details_disclosure.setObjectName("guideDetailsDisclosure")
        self.card.add_widget(self.details_disclosure)

        self.step_list = QListWidget(self.card)
        self.step_list.setObjectName("guideSteps")
        self.step_list.setAccessibleName(self.tr("Guide steps"))
        self.step_list.setMaximumHeight(180)
        self.step_list.currentRowChanged.connect(self._step_selected)
        self.details_disclosure.add_widget(self.step_list)

        self.status_label = QLabel("", self.card)
        self.status_label.setWordWrap(True)
        self.status_label.setObjectName("guideProgressStatus")
        self.details_disclosure.add_widget(self.status_label)

        button_row = QWidget(self.card)
        buttons = QHBoxLayout(button_row)
        buttons.setContentsMargins(0, 0, 0, 0)
        self.review_button = QuietButton(self.tr("Mark reviewed"), parent=self.card)
        self.review_button.clicked.connect(lambda: self._set_step_state("reviewed"))
        buttons.addWidget(self.review_button)
        self.skip_button = QuietButton(self.tr("Skip step"), parent=self.card)
        self.skip_button.clicked.connect(lambda: self._set_step_state("skipped"))
        buttons.addWidget(self.skip_button)
        self.evidence_button = QuietButton(self.tr("Link verified result"), parent=self.card)
        self.evidence_button.clicked.connect(self._link_evidence)
        buttons.addWidget(self.evidence_button)
        self.details_disclosure.add_widget(button_row)
        self._current_step_expanded_text = self.tr("Next step: %1")

        self._load_saved_selection()

    def _load_saved_selection(self) -> None:
        try:
            snapshot = self.store.read()
        except (OSError, RuntimeError, TypeError, ValueError):
            self.status_label.setText(self.tr("Saved guide progress is unavailable. The file was left unchanged."))
            self.details_disclosure.toggle_button.setChecked(True)
            self._set_controls_enabled(False)
            return
        if snapshot.active_guide:
            index = self.guide_selector.findData(snapshot.active_guide)
            if index >= 0:
                self.guide_selector.blockSignals(True)
                self.guide_selector.setCurrentIndex(index)
                self.guide_selector.blockSignals(False)
                self.active_guide = snapshot.active_guide
                self.active_step = snapshot.active_step
                self._snapshot = snapshot
                self.guide_description.setText(self.tr(GUIDES_BY_ID[self.active_guide].description))
                self._render_steps()
                self.guideChanged.emit(self.active_guide)

    def open_guide(self, guide_id: str) -> bool:
        """Select a guide from global search or the shell resume control."""
        index = self.guide_selector.findData(str(guide_id))
        if index < 0:
            return False
        self.guide_selector.setCurrentIndex(index)
        self.setFocus(Qt.FocusReason.OtherFocusReason)
        return True

    def open_step(self, guide_id: str, step_id: str) -> bool:
        """Select and open one step through its normal navigation-only path."""
        if guide_id not in GUIDES_BY_ID or step_id not in {step.id for step in GUIDES_BY_ID[guide_id].steps}:
            return False
        if not self.open_guide(guide_id):
            return False
        for row in range(self.step_list.count()):
            item = self.step_list.item(row)
            if item is not None and item.data(Qt.ItemDataRole.UserRole) == step_id:
                self.step_list.setCurrentRow(row)
                self._open_step()
                return True
        return False

    def _guide_selected(self, _index: int) -> None:
        guide_id = str(self.guide_selector.currentData() or "")
        if not guide_id:
            self.active_guide = ""
            self.active_step = ""
            self.step_list.clear()
            self.current_step_label.setText(self.tr("Choose a guide to see its next step."))
            self.open_button.setEnabled(False)
            self.details_disclosure.toggle_button.setChecked(False)
            self._snapshot = None
            try:
                self._snapshot = self.store.clear_active()
                self.status_label.clear()
                self._set_controls_enabled(True)
            except (OSError, RuntimeError, TypeError, ValueError) as exc:
                self.status_label.setText(self.tr("Could not save guide progress: %1").replace("%1", str(exc)))
                self._set_controls_enabled(False)
            self.guide_description.setText(self.tr("Guide progress is saved locally and can be resumed."))
            self.guideChanged.emit("")
            return
        guide = GUIDES_BY_ID[guide_id]
        self.active_guide = guide_id
        self.guide_description.setText(self.tr(guide.description))
        try:
            snapshot = self.store.read()
            if snapshot.writable:
                snapshot = self.store.select(guide_id)
            self._snapshot = snapshot
            self.active_step = snapshot.active_step if snapshot.active_guide == guide_id else ""
            self.status_label.setText(
                self.tr("Progress is read-only because it uses a newer format.")
                if not snapshot.writable
                else ""
            )
            if not snapshot.writable:
                self.details_disclosure.toggle_button.setChecked(True)
            self._render_steps()
            self.guideChanged.emit(guide_id)
        except (OSError, RuntimeError, TypeError, ValueError) as exc:
            self.status_label.setText(self.tr("Could not save guide progress: %1").replace("%1", str(exc)))
            self._set_controls_enabled(False)

    def _render_steps(self) -> None:
        guide = GUIDES_BY_ID.get(self.active_guide)
        if guide is None:
            self.step_list.clear()
            return
        try:
            self._snapshot = self.store.read()
        except (OSError, RuntimeError, TypeError, ValueError):
            if self._snapshot is None:
                self._snapshot = self.store.read()
        self.step_list.blockSignals(True)
        self.step_list.clear()
        selected_row = 0
        state_labels = {
            "in_progress": self.tr("In progress"),
            "reviewed": self.tr("Reviewed"),
            "skipped": self.tr("Skipped"),
            "verified": self.tr("Verified result linked"),
            "evidence_missing": self.tr("Result linked"),
        }
        for index, step in enumerate(guide.steps):
            progress = self._snapshot.steps.get(step.id)
            state: str = progress.state if progress else "not_started"
            if progress and progress.state == "verified" and not _step_evidence_available(step, progress):
                state = "evidence_missing"
            label = self.tr(state_labels.get(state, "Not started" if state == "not_started" else "Evidence missing"))
            item = QListWidgetItem(f"{label} · {self.tr(step.title)}")
            item.setData(Qt.ItemDataRole.UserRole, step.id)
            item.setToolTip(self.tr(step.description))
            self.step_list.addItem(item)
            if step.id == self.active_step:
                selected_row = index
        self.step_list.setCurrentRow(selected_row)
        self.step_list.blockSignals(False)
        self._update_progress_text()
        self._update_button_states()

    def _step_selected(self, row: int) -> None:
        guide = GUIDES_BY_ID.get(self.active_guide)
        if guide is None or row < 0 or row >= len(guide.steps):
            return
        step = guide.steps[row]
        self.active_step = step.id
        try:
            snapshot = self.store.read()
            if snapshot.writable:
                self._snapshot = self.store.select(guide.id, step.id)
            else:
                self._snapshot = snapshot
            self.status_label.setText(self.tr("Progress is read-only because it uses a newer format.") if not self._snapshot.writable else "")
        except (OSError, RuntimeError, TypeError, ValueError) as exc:
            self.status_label.setText(self.tr("Could not save guide progress: %1").replace("%1", str(exc)))
        self._update_progress_text()
        self._update_button_states()

    def _current_step(self) -> GuideStep | None:
        guide = GUIDES_BY_ID.get(self.active_guide)
        row = self.step_list.currentRow()
        if guide is None or row < 0 or row >= len(guide.steps):
            return None
        return guide.steps[row]

    def _open_step(self) -> None:
        step = self._current_step()
        if step is None:
            return
        try:
            self._snapshot = self.store.read()
        except (OSError, RuntimeError, TypeError, ValueError) as exc:
            self.status_label.setText(self.tr("Could not save guide progress: %1").replace("%1", str(exc)))
            return
        progress = self._snapshot.steps.get(step.id)
        target = step.target
        evidence_available = bool(
            progress is not None
            and progress.state == "verified"
            and _step_evidence_available(step, progress)
        )
        if evidence_available and progress is not None:
            if progress.evidence_kind == "action_run":
                from core.tasks.guides import GuideTarget

                target = GuideTarget("changes", context=(("run_id", progress.evidence_id),))
            elif progress.evidence_kind == "troubleshooting_session":
                from core.tasks.guides import GuideTarget

                target = GuideTarget("health", context=(("session_id", progress.evidence_id),))
        if progress is None or progress.state == "skipped" or (progress.state == "verified" and not evidence_available):
            try:
                self._snapshot = self.store.update_step(self.active_guide, step.id, "in_progress")
            except (OSError, RuntimeError, TypeError, ValueError) as exc:
                self.status_label.setText(self.tr("Could not save guide progress: %1").replace("%1", str(exc)))
                return
        self._render_steps()
        self.targetRequested.emit(target)

    def _set_step_state(self, state: ProgressStatus) -> None:
        step = self._current_step()
        if step is None:
            return
        try:
            self._snapshot = self.store.update_step(self.active_guide, step.id, state)
        except (OSError, RuntimeError, TypeError, ValueError) as exc:
            self.status_label.setText(self.tr("Could not save guide progress: %1").replace("%1", str(exc)))
            return
        self.status_label.setText(self.tr("Step marked %1.").replace("%1", self.tr(state.replace("_", " "))))
        self._render_steps()
        self.guideChanged.emit(self.active_guide)

    def _link_evidence(self) -> None:
        step = self._current_step()
        if step is None or not step.evidence_kinds:
            return
        candidates = [
            item
            for kind in step.evidence_kinds
            for item in guide_evidence(
                kind,
                action_ids=step.evidence_action_ids if kind == "action_run" else None,
            )
        ]
        if not candidates:
            self.status_label.setText(self.tr("No compatible verified result is available yet."))
            return
        labels = [f"{item.label} · {item.id}" for item in candidates]
        chosen, accepted = QInputDialog.getItem(self, self.tr("Link a verified result"), self.tr("Choose an exact saved result."), labels, 0, False)
        if not accepted:
            return
        evidence = candidates[labels.index(chosen)]
        try:
            self._snapshot = self.store.update_step(
                self.active_guide,
                step.id,
                "verified",
                evidence_kind=evidence.kind,
                evidence_id=evidence.id,
            )
        except (OSError, RuntimeError, TypeError, ValueError) as exc:
            self.status_label.setText(self.tr("Could not link the result: %1").replace("%1", str(exc)))
            return
        self.status_label.setText(self.tr("Verified result linked. This records the operation result, not the overall system state."))
        self._render_steps()
        self.guideChanged.emit(self.active_guide)

    def _update_progress_text(self) -> None:
        guide = GUIDES_BY_ID.get(self.active_guide)
        if guide is None or self._snapshot is None:
            return
        values = [self._snapshot.steps.get(step.id) for step in guide.steps]
        reviewed = sum(item is not None and item.state == "reviewed" for item in values)
        skipped = sum(item is not None and item.state == "skipped" for item in values)
        verified = sum(
            item is not None and item.state == "verified" and _step_evidence_available(step, item)
            for step, item in zip(guide.steps, values)
        )
        missing = sum(
            item is not None and item.state == "verified" and not _step_evidence_available(step, item)
            for step, item in zip(guide.steps, values)
        )
        self.status_label.setText(
            self.tr("%1 reviewed · %2 skipped · %3 verified result(s) · %4 unavailable")
            .replace("%1", str(reviewed))
            .replace("%2", str(skipped))
            .replace("%3", str(verified))
            .replace("%4", str(missing))
        )
        if not self._snapshot.writable:
            self.status_label.setText(self.status_label.text() + " · " + self.tr("Progress is read-only because it uses a newer format."))
            self.details_disclosure.toggle_button.setChecked(True)
        step = self._current_step()
        if step is None:
            self.current_step_label.setText(self.tr("Choose a guide to see its next step."))
        else:
            self.current_step_label.setText(self._current_step_expanded_text.replace("%1", self.tr(step.title)))
        self.open_button.setEnabled(bool(self._snapshot.writable and step is not None))

    def _update_button_states(self) -> None:
        step = self._current_step()
        writable = bool(self._snapshot and self._snapshot.writable)
        self._set_controls_enabled(writable and step is not None)
        self.evidence_button.setVisible(bool(step and step.evidence_kinds))

    def _set_controls_enabled(self, enabled: bool) -> None:
        for button in (self.open_button, self.review_button, self.skip_button, self.evidence_button):
            button.setEnabled(bool(enabled))


__all__ = ["GuidePanel"]
