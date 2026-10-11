"""Local-only profile authoring using independently inspected catalog controls."""
from __future__ import annotations

from typing import Any

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import (
    QCheckBox,
    QDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from core.tasks.tweak_library import edit_profile
from core.tasks.tweak_profiles import TweakProfile
from core.tasks.tweaks import BY_ID, TweakState
from ui.components.tweak_controls import TweakControl
from ui.tweak_profile_views import ProfileEditorExitDialog


class ProfileEditorWidget(QWidget):
    """Editable copy whose save is persisted only by the window operation owner."""

    saveRequested = pyqtSignal(object, bool, bool, bool)
    exitRequested = pyqtSignal()

    def __init__(self, profile: TweakProfile, states: tuple[TweakState, ...], parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.source = profile
        self.states = tuple(states)
        self.rows: dict[str, tuple[QCheckBox, TweakControl]] = {}
        self._saving = False
        self.setObjectName("profileEditorView")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        explanation = QLabel(self.tr(
            "Save a new version in your library. Saving changes no computer settings. "
            "Clear a setting's box to remove it; unavailable values are retained. Apply later through a fresh review."
        ))
        explanation.setWordWrap(True)
        layout.addWidget(explanation)

        name_label = QLabel(self.tr("Profile name:"))
        self.name = QLineEdit()
        self.name.setText(self.tr("%1 (copy)").replace("%1", profile.name[:100]))
        self._initial_name = self.name.text()
        self.name.setAccessibleName(self.tr("Profile name"))
        name_label.setBuddy(self.name)
        layout.addWidget(name_label)
        layout.addWidget(self.name)

        body = QWidget()
        settings_layout = QVBoxLayout(body)
        original = dict(profile.settings)
        inspected = {state.tweak.id: state for state in states}
        ids = list(original)
        ids.extend(state.tweak.id for state in states if state.tweak.id not in original
                   and state.tweak.desktop == profile.desktop and not state.tweak.system_wide and not state.tweak.privileged)
        for key in ids:
            tweak = BY_ID.get(key)
            state = inspected.get(key)
            editable = bool(tweak and tweak.desktop == profile.desktop and not tweak.system_wide and not tweak.privileged
                            and state and state.status == "ready" and state.choices)
            title = self.tr(tweak.title) if tweak else key
            include = QCheckBox(title)
            include.setChecked(key in original)
            include.setAccessibleName(self.tr("Include %1").replace("%1", title))
            include.setEnabled(key in original or editable)
            settings_layout.addWidget(include)
            control = TweakControl(tweak.control_kind if tweak else "dropdown")
            control.setAccessibleName(self.tr("Target value for %1").replace("%1", title))
            value = original.get(key, state.value if state else "")
            choices = state.choices if editable and state else ()
            if value and value not in {choice for choice, _label in choices}:
                control.addItem(self.tr("Retained value: %1").replace("%1", value), value)
            for choice, label in choices:
                control.addItem(self.tr(label), choice)
            control.rebuild()
            control.setCurrentIndex(control.findData(value))
            if control.currentIndex() < 0 and control.count():
                control.setCurrentIndex(0)
            control.setEnabled(editable and include.isChecked())
            include.toggled.connect(lambda checked, widget=control, available=editable: widget.setEnabled(checked and available))
            settings_layout.addWidget(control)
            if not editable:
                reason = state.message if state and state.message else self.tr(
                    "Unknown or unavailable on this desktop. Retain the original value or clear the box to remove it."
                )
                notice = QLabel(reason)
                notice.setWordWrap(True)
                settings_layout.addWidget(notice)
            self.rows[key] = (include, control)
        settings_layout.addStretch()
        layout.addWidget(body)

        self.error = QLabel()
        self.error.setWordWrap(True)
        self.error.setAccessibleName(self.tr("Profile validation error"))
        layout.addWidget(self.error)
        actions = QHBoxLayout()
        self.save_button = QPushButton(self.tr("Save copy"))
        self.save_button.setObjectName("profileSaveCopy")
        self.save_button.setAccessibleName(self.tr("Save this profile as a new copy"))
        self.review_button = QPushButton(self.tr("Save and review…"))
        self.review_button.setObjectName("profileSaveAndReview")
        self.review_button.setAccessibleName(self.tr("Save this profile copy and review it against current settings"))
        for button, review in ((self.save_button, False), (self.review_button, True)):
            button.setAutoDefault(False)
            button.clicked.connect(lambda _checked=False, after_review=review: self.request_save(review_after=after_review))
            actions.addWidget(button)
        self.back_button = QPushButton(self.tr("Back to library"))
        self.back_button.setAutoDefault(False)
        self.back_button.clicked.connect(self.request_exit)
        actions.addWidget(self.back_button)
        layout.addLayout(actions)

    def profile_for_save(self) -> TweakProfile:
        settings = tuple(
            (key, str(control.currentData() or ""))
            for key, (include, control) in self.rows.items()
            if include.isChecked()
        )
        result = edit_profile(self.source, self.name.text(), settings, self.states)
        if result == self.source:
            raise ValueError(self.tr("Change the name or settings to save a new version."))
        return result

    def is_dirty(self) -> bool:
        current = tuple(
            (key, str(control.currentData() or ""))
            for key, (include, control) in self.rows.items()
            if include.isChecked()
        )
        return self.name.text() != self._initial_name or current != self.source.settings

    def request_save(
        self, *, review_after: bool = False, return_after: bool = False, close_after: bool = False
    ) -> bool:
        try:
            profile = self.profile_for_save()
        except ValueError as exc:
            self.error.setText(str(exc))
            self.name.setFocus()
            return False
        self.error.clear()
        self.saveRequested.emit(profile, bool(review_after), bool(return_after), bool(close_after))
        return True

    def request_exit(self) -> None:
        if not self.is_dirty():
            self.exitRequested.emit()
            return
        choice = ProfileEditorExitDialog.choose(self)
        if choice == "discard":
            self.exitRequested.emit()
        elif choice == "save":
            self.request_save(return_after=True)

    def request_close(self) -> str:
        """Protect a dirty draft when the owning application is closing."""
        if self._saving:
            return "cancel"
        if not self.is_dirty():
            return "allow"
        choice = ProfileEditorExitDialog.choose(self)
        if choice == "discard":
            return "allow"
        if choice == "save" and self.request_save(return_after=True, close_after=True):
            return "saving"
        return "cancel"

    def set_save_error(self, message: str) -> None:
        self.error.setText(str(message))
        self.save_button.setEnabled(True)
        self.review_button.setEnabled(True)

    def set_saving(self, saving: bool) -> None:
        self._saving = bool(saving)
        for button in (self.save_button, self.review_button, self.back_button):
            button.setEnabled(not saving)


class ProfileEditorDialog(QDialog):
    """Compatibility wrapper for callers that need the former modal editor."""

    def __init__(self, profile: TweakProfile, states: tuple[TweakState, ...], parent: Any = None) -> None:
        super().__init__(parent)
        self.saved_profile: TweakProfile | None = None
        self.setWindowTitle(self.tr("Edit profile copy"))
        self.resize(760, 600)
        layout = QVBoxLayout(self)
        self.editor = ProfileEditorWidget(profile, states, self)
        layout.addWidget(self.editor)
        self.rows = self.editor.rows
        self.name = self.editor.name
        self.error = self.editor.error
        self.editor.saveRequested.connect(self._saved)

    def _saved(self, profile: TweakProfile, _review_after: bool, _return_after: bool, _close_after: bool) -> None:
        self.saved_profile = profile
        self.accept()

    def _save(self) -> None:
        self.editor.request_save()
