"""Direct, state-backed Fedora tweak controls for the utility shell."""

from __future__ import annotations

from typing import Any

from core.tasks.tweaks import TweakState, visible_tweaks
from PyQt6.QtCore import QTimer, pyqtSignal
from PyQt6.QtWidgets import QComboBox, QHBoxLayout, QLabel, QLineEdit, QPushButton, QVBoxLayout, QWidget

from ui.components import Card, PageScaffold
from ui.components.settings import SettingRow


class TweaksPage(QWidget):
    """Render inspected values; request changes without owning execution."""

    refreshRequested = pyqtSignal()
    changeRequested = pyqtSignal(str, str)

    def __init__(self, profile: object, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.profile = profile
        self._shown_once = False
        self._busy = False
        self._rows: dict[str, tuple[SettingRow, QComboBox]] = {}
        self._last_change: tuple[str, str, bool, str] | None = None
        self.setObjectName("tweaksPage")
        self.setAccessibleName(self.tr("Fedora tweaks"))
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        self.scaffold = PageScaffold(
            self.tr("Tweaks"),
            self.tr("Change one supported setting at a time and see its verified value."),
        )
        root.addWidget(self.scaffold)

        intro = Card(
            self.tr("Make Fedora yours"),
            self.tr("Controls reflect the current system setting. Changes are checked before and after they run."),
        )
        self.scaffold.add_widget(intro)
        search_row = QHBoxLayout()
        self.search_input = QLineEdit()
        self.search_input.setObjectName("tweaksSearch")
        self.search_input.setPlaceholderText(self.tr("Search settings…"))
        self.search_input.setAccessibleName(self.tr("Search tweaks"))
        self.search_input.setClearButtonEnabled(True)
        self.search_input.textChanged.connect(self._filter_rows)
        search_row.addWidget(self.search_input, 1)
        self.refresh_button = QPushButton(self.tr("Refresh"))
        self.refresh_button.setObjectName("tweaksRefresh")
        self.refresh_button.clicked.connect(self.refreshRequested.emit)
        search_row.addWidget(self.refresh_button)
        intro.add_widget(self._wrap(search_row))
        self.status_label = QLabel(self.tr("Reading current settings…"))
        self.status_label.setObjectName("tweaksStatus")
        self.status_label.setWordWrap(True)
        intro.add_widget(self.status_label)

        groups: dict[str, Card] = {}
        for tweak in visible_tweaks(profile):
            group = groups.get(tweak.group)
            if group is None:
                group = Card(self.tr(tweak.group))
                group.setObjectName(f"tweaksGroup{tweak.group}")
                groups[tweak.group] = group
                self.scaffold.add_widget(group)
            control = QComboBox()
            control.setObjectName(f"tweakControl_{tweak.id}")
            control.setAccessibleName(self.tr(tweak.title))
            control.setEnabled(False)
            row = SettingRow(self.tr(tweak.title), self.tr(tweak.description), control)
            row.setObjectName(f"tweakRow_{tweak.id}")
            group.add_widget(row)
            self._rows[tweak.id] = (row, control)
            control.activated.connect(lambda _index, item=tweak.id: self._selected(item))
        if not self._rows:
            self.status_label.setText(self.tr("Tweak controls are unavailable until a supported Fedora desktop is detected."))
        self.scaffold.content_layout.addStretch()

    @staticmethod
    def _wrap(layout: QHBoxLayout) -> QWidget:
        widget = QWidget()
        widget.setLayout(layout)
        return widget

    def showEvent(self, event: Any) -> None:
        super().showEvent(event)
        if self._rows:
            self._shown_once = True
            QTimer.singleShot(0, self.refreshRequested.emit)

    def _filter_rows(self, query: str) -> None:
        needle = query.strip().casefold()
        for row, _control in self._rows.values():
            text = f"{row.title_label.text()} {row.description_label.text()}".casefold()
            row.setVisible(not needle or needle in text)

    def _selected(self, tweak_id: str) -> None:
        if self._busy:
            return
        row, control = self._rows[tweak_id]
        value = str(control.currentData() or "")
        if not value or value == str(control.property("currentValue") or ""):
            return
        self.changeRequested.emit(tweak_id, value)

    def restore_selection(self, tweak_id: str) -> None:
        _row, control = self._rows[tweak_id]
        index = control.findData(control.property("currentValue"))
        if index >= 0:
            control.setCurrentIndex(index)

    def set_busy(self, busy: bool, message: str = "") -> None:
        self._busy = busy
        self.refresh_button.setEnabled(not busy)
        for _row, control in self._rows.values():
            control.setEnabled(not busy and bool(control.property("ready")))
        if message:
            self.status_label.setText(message)

    def set_states(self, states: tuple[TweakState, ...]) -> None:
        self.set_busy(False, self.tr("Current settings loaded. Choose one value to change it."))
        for state in states:
            pair = self._rows.get(state.tweak.id)
            if pair is None:
                continue
            row, control = pair
            control.blockSignals(True)
            control.clear()
            control.setProperty("ready", state.status == "ready")
            control.setProperty("currentValue", state.value)
            if state.value and state.value not in {value for value, _label in state.choices}:
                control.addItem(self.tr("Current custom value: %1").replace("%1", state.value), state.value)
            for value, label in state.choices:
                control.addItem(self.tr(label), value)
            index = control.findData(state.value)
            if index >= 0:
                control.setCurrentIndex(index)
            control.setEnabled(state.status == "ready" and not self._busy)
            control.blockSignals(False)
            if state.status != "ready":
                row.set_feedback(state.message or self.tr("This setting is unavailable."), kind="dependency")
            elif self._last_change and self._last_change[0] == state.tweak.id:
                _id, target, success, message = self._last_change
                if success and state.value == target:
                    row.set_feedback(self.tr("Saved and verified: %1").replace("%1", state.value), kind="saved")
                else:
                    detail = message or self.tr("The change could not be verified.")
                    row.set_feedback(self.tr("Current value: %1. %2 Refresh and try again.").replace("%1", state.value).replace("%2", detail), kind="error")
            else:
                row.clear_feedback()

    def set_outcome(self, tweak_id: str, target: str, outcome: object) -> None:
        success = bool(getattr(outcome, "success", False))
        message = str(getattr(outcome, "message", ""))
        self._last_change = (tweak_id, target, success, message)
        row, _control = self._rows[tweak_id]
        if success:
            row.set_feedback(self.tr("Setting verified. Refreshing its current value…"), kind="changed")
        else:
            self.restore_selection(tweak_id)
            row.set_feedback(message or self.tr("The change was not verified."), kind="error")
        self.status_label.setText(message or self.tr("Refreshing current settings…"))

    def set_error(self, message: str) -> None:
        self.set_busy(False, self.tr("Could not read current settings: %1. Refresh to retry.").replace("%1", message))
        for row, control in self._rows.values():
            index = control.findData(control.property("currentValue"))
            if index >= 0:
                control.setCurrentIndex(index)
            control.setEnabled(False)
            row.set_feedback(self.tr("Current value could not be confirmed. Refresh before changing it."), kind="error")

    def focus_task(self, task_id: str) -> bool:
        key = str(task_id).removeprefix("tune:")
        if key in self._rows:
            self._rows[key][1].setFocus()
            return True
        self.search_input.setFocus()
        return key in {"tune", "tweaks", "desktop"}
