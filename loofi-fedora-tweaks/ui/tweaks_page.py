"""Direct, state-backed Fedora tweak controls for the utility shell."""

from __future__ import annotations

from typing import Any

from core.tasks.tweaks import TweakState, visible_tweaks
from core.tweak_commands import values_equal
from PyQt6.QtCore import QTimer, pyqtSignal
from PyQt6.QtWidgets import QComboBox, QHBoxLayout, QLabel, QLineEdit, QPushButton, QVBoxLayout, QWidget

from ui.components import Card, PageScaffold
from ui.components.settings import SettingRow


class TweaksPage(QWidget):
    """Render inspected values; request changes without owning execution."""

    refreshRequested = pyqtSignal()
    changeRequested = pyqtSignal(str, str)
    restoreRequested = pyqtSignal(str, str)

    def __init__(self, profile: object, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.profile = profile
        self._shown_once = False
        self._busy = False
        self._rows: dict[str, tuple[SettingRow, QComboBox]] = {}
        self._groups: dict[str, Card] = {}
        self._group_rows: dict[str, list[SettingRow]] = {}
        self._last_changes: dict[str, tuple[str, bool, str, bool]] = {}
        self._restore_buttons: dict[str, QPushButton] = {}
        self._restore_notices: dict[str, QLabel] = {}
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

        for tweak in visible_tweaks(profile):
            group = self._groups.get(tweak.group)
            if group is None:
                group = Card(self.tr(tweak.group))
                group.setObjectName(f"tweaksGroup{tweak.group}")
                self._groups[tweak.group] = group
                self._group_rows[tweak.group] = []
                self.scaffold.add_widget(group)
            control = QComboBox()
            control.setObjectName(f"tweakControl_{tweak.id}")
            control.setAccessibleName(self.tr(tweak.title))
            control.setEnabled(False)
            row = SettingRow(self.tr(tweak.title), self.tr(tweak.description), control)
            row.setObjectName(f"tweakRow_{tweak.id}")
            group.add_widget(row)
            self._rows[tweak.id] = (row, control)
            self._group_rows[tweak.group].append(row)
            restore = QPushButton(self.tr("Restore previous value"))
            restore.setObjectName(f"tweakRestore_{tweak.id}")
            restore.setAccessibleName(self.tr("Restore previous value for %1").replace("%1", self.tr(tweak.title)))
            restore.setEnabled(False)
            restore.hide()
            restore.clicked.connect(lambda _checked=False, item=tweak.id: self._restore_selected(item))
            row_layout = row.layout()
            assert row_layout is not None
            row_layout.addWidget(restore)
            self._restore_buttons[tweak.id] = restore
            notice = QLabel()
            notice.setWordWrap(True)
            notice.hide()
            row_layout.addWidget(notice)
            self._restore_notices[tweak.id] = notice
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
        for group_name, rows in self._group_rows.items():
            card = self._groups.get(group_name)
            if card is not None:
                card.setVisible(any(not r.isHidden() for r in rows))

    def _selected(self, tweak_id: str) -> None:
        if self._busy:
            return
        row, control = self._rows[tweak_id]
        value = str(control.currentData() or "")
        if not value or value == str(control.property("currentValue") or ""):
            return
        self.changeRequested.emit(tweak_id, value)

    def _restore_selected(self, tweak_id: str) -> None:
        button = self._restore_buttons[tweak_id]
        source_id = str(button.property("sourceRunId") or "")
        if not self._busy and button.isEnabled() and source_id:
            self.restoreRequested.emit(tweak_id, source_id)

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
        for button in self._restore_buttons.values():
            button.setEnabled(not busy and bool(button.property("ready")) and bool(button.property("sourceRunId")))
        if message:
            self.status_label.setText(message)

    def set_states(self, states: tuple[TweakState, ...]) -> None:
        self.set_busy(False, self.tr("Current settings loaded. Choose one value to change it."))
        for state in states:
            pair = self._rows.get(state.tweak.id)
            if pair is None:
                continue
            row, control = pair
            restore = self._restore_buttons[state.tweak.id]
            restore.setProperty("sourceRunId", state.restore_run_id)
            restore.setProperty("restoreValue", state.restore_value)
            restore.setProperty("ready", state.status == "ready")
            restore.setEnabled(state.status == "ready" and bool(state.restore_run_id) and not self._busy)
            restore.setVisible(bool(state.restore_run_id or state.restore_message))
            notice = self._restore_notices[state.tweak.id]
            restore_text = self.tr("Previous value: %1").replace("%1", state.restore_value) if state.restore_run_id else self.tr(state.restore_message)
            notice.setText(restore_text)
            notice.setVisible(bool(restore_text))
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
            elif state.tweak.id in self._last_changes:
                target, success, message, restored = self._last_changes[state.tweak.id]
                if success and values_equal(state.tweak.id, state.value, target):
                    text = self.tr("Previous value restored and verified: %1") if restored else self.tr("Saved setting verified: %1")
                    text = text.replace("%1", state.value)
                    if state.tweak.desktop == "kde":
                        text += " " + self.tr("Reopen affected applications if the change is not visible yet.")
                    row.set_feedback(text, kind="saved")
                else:
                    detail = message or self.tr("The change could not be verified.")
                    row.set_feedback(self.tr("Current value: %1. %2 Refresh and try again.").replace("%1", state.value).replace("%2", detail), kind="error")
            else:
                row.clear_feedback()

    def set_outcome(self, tweak_id: str, target: str, outcome: object, *, restored: bool = False) -> None:
        success = bool(getattr(outcome, "success", False))
        message = str(getattr(outcome, "message", ""))
        self._last_changes[tweak_id] = (target, success, message, restored)
        row, _control = self._rows[tweak_id]
        if success:
            row.set_feedback(self.tr("Saved setting verified. Refreshing its current value…"), kind="changed")
        else:
            self.restore_selection(tweak_id)
            row.set_feedback(message or self.tr("The change was not verified."), kind="error")
        self.status_label.setText(message or self.tr("Refreshing current settings…"))

    def set_restore_error(self, tweak_id: str, message: str) -> None:
        """Invalidate one restoration offer without misreporting other rows."""
        self.set_busy(False, message)
        self._last_changes.pop(tweak_id, None)
        row, control = self._rows[tweak_id]
        control.setProperty("ready", False)
        control.setEnabled(False)
        button = self._restore_buttons[tweak_id]
        button.setProperty("sourceRunId", "")
        button.setEnabled(False)
        row.set_feedback(message, kind="error")
        notice = self._restore_notices[tweak_id]
        notice.setText(self.tr("Refresh this setting before trying again."))
        notice.show()

    def set_error(self, message: str) -> None:
        self.set_busy(False, self.tr("Could not read current settings: %1. Refresh to retry.").replace("%1", message))
        for button in self._restore_buttons.values():
            button.setProperty("ready", False)
            button.setEnabled(False)
        for row, control in self._rows.values():
            control.setProperty("ready", False)
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
