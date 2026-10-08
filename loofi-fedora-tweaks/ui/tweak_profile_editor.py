"""Local-only profile authoring using independently inspected catalog controls."""
from __future__ import annotations

from typing import Any

from PyQt6.QtWidgets import QCheckBox, QDialog, QDialogButtonBox, QLabel, QLineEdit, QScrollArea, QVBoxLayout, QWidget

from core.tasks.tweak_library import edit_profile
from core.tasks.tweak_profiles import TweakProfile
from core.tasks.tweaks import BY_ID, TweakState
from ui.components.tweak_controls import TweakControl


class ProfileEditorDialog(QDialog):
    """Keep every original row until its inclusion box is explicitly cleared."""

    def __init__(self, profile: TweakProfile, states: tuple[TweakState, ...], parent: Any = None) -> None:
        super().__init__(parent)
        self.source = profile
        self.states = states
        self.saved_profile: TweakProfile | None = None
        self.rows: dict[str, tuple[QCheckBox, TweakControl]] = {}
        self.setWindowTitle(self.tr("Edit profile copy"))
        self.resize(760, 600)
        layout = QVBoxLayout(self)
        explanation = QLabel(self.tr("Save a new version in your library. Saving changes no computer settings. Clear a setting's box to remove it; unavailable values are retained. Apply later through a fresh review."))
        explanation.setWordWrap(True)
        layout.addWidget(explanation)
        name_label = QLabel(self.tr("Profile name:"))
        self.name = QLineEdit()
        self.name.setText(self.tr("%1 (copy)").replace("%1", profile.name[:100]))
        self.name.setAccessibleName(self.tr("Profile name"))
        name_label.setBuddy(self.name)
        layout.addWidget(name_label)
        layout.addWidget(self.name)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
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
            # Unknown rows remain removable; unavailable absent rows cannot be added.
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
                reason = state.message if state and state.message else self.tr("Unknown or unavailable on this desktop. Retain the original value or clear the box to remove it.")
                notice = QLabel(reason)
                notice.setWordWrap(True)
                settings_layout.addWidget(notice)
            self.rows[key] = (include, control)
        settings_layout.addStretch()
        scroll.setWidget(body)
        layout.addWidget(scroll)
        self.error = QLabel()
        self.error.setWordWrap(True)
        self.error.setAccessibleName(self.tr("Profile validation error"))
        layout.addWidget(self.error)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        save = buttons.button(QDialogButtonBox.StandardButton.Save)
        if save is not None:
            save.setText(self.tr("Save new version"))
            save.setAutoDefault(False)
        cancel = buttons.button(QDialogButtonBox.StandardButton.Cancel)
        if cancel is not None:
            cancel.setDefault(True)
        buttons.accepted.connect(self._save)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _save(self) -> None:
        settings = tuple((key, str(control.currentData() or "")) for key, (include, control) in self.rows.items() if include.isChecked())
        try:
            self.saved_profile = edit_profile(self.source, self.name.text(), settings, self.states)
            if self.saved_profile == self.source:
                raise ValueError(self.tr("Change the name or settings to save a new version."))
        except ValueError as exc:
            self.error.setText(str(exc))
            return
        self.accept()
