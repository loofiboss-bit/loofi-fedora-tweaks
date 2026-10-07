"""Direct, state-backed Fedora tweak controls for the utility shell."""

from __future__ import annotations

from typing import Any

from core.tasks.tweaks import TweakState, default_for, visible_tweaks
from core.tweak_commands import values_equal
from PyQt6.QtCore import QEvent, QTimer, pyqtSignal
from PyQt6.QtWidgets import QButtonGroup, QComboBox, QGridLayout, QHBoxLayout, QLabel, QLineEdit, QMenu, QPushButton, QToolButton, QVBoxLayout, QWidget, QWidgetAction

from ui.components import Card, PageScaffold
from ui.components.settings import SettingRow
from ui.components.tweak_controls import TweakControl
from utils.settings import SettingsManager
from ui.icon_pack import get_qicon
from ui.design import semantic_color


from core.plugins.interface import PluginInterface


class TweaksPage(QWidget, PluginInterface):
    """Render inspected values; request changes without owning execution."""

    refreshRequested = pyqtSignal()
    changeRequested = pyqtSignal(str, str)
    restoreRequested = pyqtSignal(str, str)
    cancelSnapshotRequested = pyqtSignal()
    snapshotProgress = pyqtSignal(int, int)

    def __init__(self, profile: object = None, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.profile = profile
        self._shown_once = False
        self._busy = False
        self._rows: dict[str, tuple[SettingRow, TweakControl]] = {}
        self._groups: dict[str, Card] = {}
        self._group_rows: dict[str, list[SettingRow]] = {}
        self._last_changes: dict[str, tuple[str, bool, str, bool]] = {}
        self._restore_buttons: dict[str, QPushButton] = {}
        self._restore_notices: dict[str, QLabel] = {}
        self._reset_buttons: dict[str, QPushButton] = {}
        self._changed: set[str] = set()
        self._unavailable: set[str] = set()
        self._tweaks = {tweak.id: tweak for tweak in visible_tweaks(profile)}
        self._state_choices = {key: tweak.choices for key, tweak in self._tweaks.items()}
        self._settings = SettingsManager.instance()
        self._favorites = set(self._settings.get("favorite_tweaks", []))
        self._favorite_buttons: dict[str, QToolButton] = {}
        self._pending: dict[str, str] = {}
        self._activation_messages: dict[str, str] = {}
        self._reading = False
        self.setObjectName("tweaksPage")
        self.setAccessibleName(self.tr("Fedora tweaks"))
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        self.scaffold = PageScaffold(
            self.tr("Tweaks"),
            self.tr("Change one supported setting at a time and see its verified value."),
        )
        root.addWidget(self.scaffold)

        intro = Card()
        intro.setObjectName("tweaksFilters")
        intro.setProperty("surfaceRole", "toolbar")
        intro.body.setContentsMargins(0, 0, 0, 8)
        intro.body.setSpacing(8)
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
        self.cancel_snapshot_button = QPushButton(self.tr("Cancel check"))
        self.cancel_snapshot_button.setObjectName("tweaksCancelCheck")
        self.cancel_snapshot_button.setAccessibleName(self.tr("Cancel reading current settings"))
        self.cancel_snapshot_button.clicked.connect(self.cancelSnapshotRequested.emit)
        self.cancel_snapshot_button.hide()
        search_row.addWidget(self.cancel_snapshot_button)
        intro.add_widget(self._wrap(search_row))
        filters = QGridLayout()
        self._filter_layout = filters
        self.category_filter = QComboBox()
        self.category_filter.setAccessibleName(self.tr("Setting category"))
        self.category_filter.addItem(self.tr("All categories"), "")
        for name in dict.fromkeys(tweak.group for tweak in self._tweaks.values()):
            self.category_filter.addItem(self.tr(name), name)
        self.category_filter.currentIndexChanged.connect(lambda _index: self._filter_rows(self.search_input.text()))
        self.category_filter.setMinimumWidth(max(self.category_filter.fontMetrics().horizontalAdvance(self.category_filter.itemText(i)) for i in range(self.category_filter.count())) + 48)
        filters.addWidget(self.category_filter, 0, 0)
        self._view_group = QButtonGroup(self)
        self._view_buttons: dict[str, QPushButton] = {}
        for name, label in (("all", "All"), ("favorites", "Favorites"), ("changed", "Changed"), ("unavailable", "Unavailable")):
            button = QPushButton(self.tr(label))
            button.setCheckable(True)
            button.setObjectName("tweaksView")
            button.setAccessibleName(self.tr("Show %1 settings").replace("%1", self.tr(label)))
            if name == "changed":
                button.setToolTip(self.tr("Shows settings that differ from Loofi's standard value."))
                button.setAccessibleDescription(self.tr("Shows settings that differ from Loofi's standard value."))
            self._view_group.addButton(button)
            self._view_buttons[name] = button
            button.toggled.connect(lambda _checked: self._filter_rows(self.search_input.text()))
            filters.addWidget(button, 0, len(self._view_buttons))
        self._view_buttons["all"].setChecked(True)
        self.changed_only = self._view_buttons["changed"]
        filters.setColumnStretch(5, 1)
        intro.add_widget(self._wrap(filters))
        self.results_label = QLabel()
        self.results_label.setObjectName("tweaksResults")
        self.results_label.setWordWrap(True)
        intro.add_widget(self.results_label)
        self.empty_state = Card(self.tr("No settings found"), self.tr("Try another search or clear your filters."))
        self.empty_state.setObjectName("tweaksEmpty")
        self.clear_filters_button = QPushButton(self.tr("Clear filters"))
        self.clear_filters_button.clicked.connect(self.clear_filters)
        self.empty_state.add_widget(self.clear_filters_button)
        self.empty_state.hide()
        self.scaffold.add_widget(self.empty_state)
        self.status_label = QLabel(self.tr("Reading current settings…"))
        self.status_label.setObjectName("tweaksStatus")
        self.status_label.setWordWrap(True)
        intro.add_widget(self.status_label)
        self.snapshotProgress.connect(self.set_snapshot_progress)

        for tweak in visible_tweaks(profile):
            group = self._groups.get(tweak.group)
            if group is None:
                group = Card(self.tr(tweak.group))
                group.setObjectName(f"tweaksGroup{tweak.group}")
                group.setProperty("surfaceRole", "settings")
                group.body.setSpacing(0)
                self._groups[tweak.group] = group
                self._group_rows[tweak.group] = []
                self.scaffold.add_widget(group)
            control = TweakControl(getattr(tweak, "control_kind", "auto"))
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
            actions = QHBoxLayout()
            actions.setContentsMargins(0, 0, 0, 0)
            favorite = QToolButton()
            favorite.setObjectName("tweakFavorite")
            favorite.setIcon(get_qicon("favorite", size=20, tint=semantic_color("text_muted")))
            favorite.setCheckable(True)
            favorite.setChecked(tweak.id in self._favorites)
            favorite.toggled.connect(lambda _checked: self._refresh_favorite_icons())
            favorite.setAccessibleName(self.tr("Favorite %1").replace("%1", self.tr(tweak.title)))
            favorite.setToolTip(self.tr("Remove from favorites") if tweak.id in self._favorites else self.tr("Add to favorites"))
            favorite.clicked.connect(lambda checked, item=tweak.id: self._save_favorite(item, checked))
            self._favorite_buttons[tweak.id] = favorite
            actions.addWidget(favorite)
            actions.addWidget(restore)
            menu_button = QToolButton()
            menu_button.setText("⋯")
            menu_button.setObjectName("tweakRowActions")
            menu_button.setAccessibleName(self.tr("Actions for %1").replace("%1", self.tr(tweak.title)))
            menu_button.setToolTip(self.tr("Loofi standard value and technical details"))
            menu_button.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
            menu = QMenu(menu_button)
            menu_button.setMenu(menu)
            actions.addWidget(menu_button)
            row.control_layout.addLayout(actions)
            self._restore_buttons[tweak.id] = restore
            reset = QPushButton(self.tr("Use Loofi standard value"))
            reset.setObjectName(f"tweakReset_{tweak.id}")
            reset.setAccessibleName(self.tr("Set %1 to Loofi's standard value").replace("%1", self.tr(tweak.title)))
            reset.setProperty("defaultValue", default_for(tweak))
            reset.setEnabled(False)
            reset.hide()
            reset.clicked.connect(lambda _checked=False, item=tweak.id: self._reset_selected(item))
            reset_action = QWidgetAction(menu)
            reset_action.setDefaultWidget(reset)
            menu.addAction(reset_action)
            details_action = QWidgetAction(menu)
            details = QLabel(self.tr("ID: %1\nLoofi standard: %2\nScope: %3").replace("%1", tweak.id).replace("%2", self._label_for(tweak.id, default_for(tweak))).replace("%3", self.tr("System") if tweak.system_wide else self.tr("Current user")))
            details.setWordWrap(True)
            details.setMargin(12)
            details_action.setDefaultWidget(details)
            menu.addAction(details_action)
            self._reset_buttons[tweak.id] = reset
            notice = QLabel()
            notice.setWordWrap(True)
            notice.hide()
            row_layout = row.layout()
            assert row_layout is not None
            row_layout.addWidget(notice)
            self._restore_notices[tweak.id] = notice
            control.activated.connect(lambda _index, item=tweak.id: self._selected(item))
        if not self._rows:
            self.status_label.setText(self.tr("Tweak controls are unavailable until a supported Fedora desktop is detected."))
        self.scaffold.content_layout.addStretch()
        self._filter_rows("")
        self._refresh_favorite_icons()

    @staticmethod
    def _wrap(layout: QHBoxLayout | QGridLayout) -> QWidget:
        widget = QWidget()
        widget.setLayout(layout)
        return widget

    def showEvent(self, event: Any) -> None:
        super().showEvent(event)
        if self._rows:
            self._shown_once = True
            QTimer.singleShot(0, self.refreshRequested.emit)

    def _label_for(self, tweak_id: str, value: str) -> str:
        return next((self.tr(label) for key, label in self._state_choices[tweak_id] if values_equal(tweak_id, key, value)), value)

    def _save_favorite(self, tweak_id: str, checked: bool) -> None:
        previous = list(self._settings.get("favorite_tweaks", []))
        updated = [item for item in previous if item != tweak_id]
        if checked:
            updated.append(tweak_id)
        self._settings.set("favorite_tweaks", updated)
        if self._settings.save():
            self._favorites = set(updated)
        else:
            self._settings.set("favorite_tweaks", previous)
            self._favorite_buttons[tweak_id].setChecked(tweak_id in self._favorites)
            self.status_label.setText(self.tr("Could not save favorites. Your previous favorites were kept."))
        favorite = self._favorite_buttons[tweak_id]
        favorite.setToolTip(self.tr("Remove from favorites") if favorite.isChecked() else self.tr("Add to favorites"))
        self._filter_rows(self.search_input.text())

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        if not hasattr(self, "_filter_layout"):
            return
        controls = (self.category_filter, *self._view_buttons.values())
        available = max(1, self.width() - 64)
        row, column, occupied = 0, 0, 0
        for control in controls:
            needed = max(control.minimumWidth(), control.sizeHint().width()) + 12
            if occupied and occupied + needed > available:
                row, column, occupied = row + 1, 0, 0
            self._filter_layout.removeWidget(control)
            self._filter_layout.addWidget(control, row, column)
            column += 1
            occupied += needed

    def clear_filters(self) -> None:
        self.search_input.clear()
        self.category_filter.setCurrentIndex(0)
        self._view_buttons["all"].setChecked(True)
        self._filter_rows("")

    def _filter_rows(self, query: str) -> None:
        if not hasattr(self, "category_filter"):
            return
        needle = query.strip().casefold()
        category = str(self.category_filter.currentData() or "")
        view = next((name for name, button in self._view_buttons.items() if button.isChecked()), "all")
        count = 0
        for tweak_id, (row, _control) in self._rows.items():
            tweak = self._tweaks[tweak_id]
            aliases = " ".join(getattr(tweak, "search_terms", ()))
            text = f"{row.title_label.text()} {row.description_label.text()} {tweak.group} {aliases}".casefold()
            in_view = view == "all" or view == "favorites" and tweak_id in self._favorites or view == "changed" and tweak_id in self._changed or view == "unavailable" and tweak_id in self._unavailable
            matches = (not needle or needle in text) and (not category or tweak.group == category) and in_view
            row.setVisible(matches)
            count += int(matches)
        for group_name, rows in self._group_rows.items():
            self._groups[group_name].setVisible(any(not row.isHidden() for row in rows))
        if hasattr(self, "results_label"):
            self.results_label.setText(self.tr("%1 of %2 settings").replace("%1", str(count)).replace("%2", str(len(self._rows))))
            self.empty_state.setVisible(count == 0 and bool(self._rows))

    def changeEvent(self, event: Any) -> None:
        super().changeEvent(event)
        if event.type() in {QEvent.Type.StyleChange, QEvent.Type.PaletteChange}:
            QTimer.singleShot(0, self._refresh_favorite_icons)

    def _refresh_favorite_icons(self) -> None:
        for button in getattr(self, "_favorite_buttons", {}).values():
            role = "accent_text" if button.isChecked() else "text_muted"
            button.setIcon(get_qicon("favorite", size=20, tint=semantic_color(role)))

    def set_pending(self, tweak_id: str, value: str) -> None:
        self._pending[tweak_id] = value
        self._activation_messages.pop(tweak_id, None)
        row, control = self._rows[tweak_id]
        row.value_label.setText(self.tr("Verified: %1 · Pending: %2").replace("%1", self._label_for(tweak_id, str(control.property("currentValue") or ""))).replace("%2", self._label_for(tweak_id, value)))
        row.value_label.show()

    def set_activation(self, tweak_id: str, message: str) -> None:
        self._activation_messages[tweak_id] = message
        self._rows[tweak_id][0].set_feedback(message, kind="saved")

    def _selected(self, tweak_id: str) -> None:
        if self._busy:
            return
        row, control = self._rows[tweak_id]
        value = str(control.currentData() or "")
        if not value or value == str(control.property("currentValue") or ""):
            return
        self.set_pending(tweak_id, value)
        self.changeRequested.emit(tweak_id, value)

    def _reset_selected(self, tweak_id: str) -> None:
        button = self._reset_buttons[tweak_id]
        value = str(button.property("defaultValue") or "")
        if not self._busy and button.isEnabled() and value:
            self.set_pending(tweak_id, value)
            self.changeRequested.emit(tweak_id, value)

    def _restore_selected(self, tweak_id: str) -> None:
        button = self._restore_buttons[tweak_id]
        source_id = str(button.property("sourceRunId") or "")
        if not self._busy and button.isEnabled() and source_id:
            self.set_pending(tweak_id, str(button.property("restoreValue") or ""))
            self.restoreRequested.emit(tweak_id, source_id)

    def restore_selection(self, tweak_id: str) -> None:
        _row, control = self._rows[tweak_id]
        index = control.findData(control.property("currentValue"))
        if index >= 0:
            control.setCurrentIndex(index)
        self._pending.pop(tweak_id, None)
        row = self._rows[tweak_id][0]
        row.value_label.setText(self.tr("Verified: %1").replace("%1", self._label_for(tweak_id, str(control.property("currentValue") or ""))))

    def set_busy(self, busy: bool, message: str = "", *, cancellable: bool = False) -> None:
        self._busy = busy
        self._reading = busy and cancellable
        self.refresh_button.setEnabled(not busy)
        self.cancel_snapshot_button.setVisible(self._reading)
        self.cancel_snapshot_button.setEnabled(self._reading)
        for _row, control in self._rows.values():
            control.setEnabled(not busy and bool(control.property("ready")))
        for button in self._restore_buttons.values():
            button.setEnabled(not busy and bool(button.property("ready")) and bool(button.property("sourceRunId")))
        for button in self._reset_buttons.values():
            button.setEnabled(not busy and bool(button.property("ready")))
        if message:
            self.status_label.setText(message)

    def set_snapshot_progress(self, completed: int, total: int) -> None:
        """Show inspection progress emitted from the background worker."""
        if self._reading:
            self.status_label.setText(
                self.tr("Checking settings: %1 of %2").replace("%1", str(completed)).replace("%2", str(total))
            )

    def set_states(self, states: tuple[TweakState, ...]) -> None:
        not_checked = sum(
            state.message.startswith(("Not checked because", "Setting inspection cancelled"))
            for state in states
        )
        checked = len(states) - not_checked
        if not_checked:
            message = (
                self.tr("%1 of %2 settings checked; %3 were not checked, so their current values remain unknown. Refresh to continue.")
                .replace("%1", str(checked))
                .replace("%2", str(len(states)))
                .replace("%3", str(not_checked))
            )
        else:
            message = self.tr("Checked %1 settings. Choose one value to change it.").replace("%1", str(checked))
        self.set_busy(False, message)
        for state in states:
            pair = self._rows.get(state.tweak.id)
            if pair is None:
                continue
            row, control = pair
            self._state_choices[state.tweak.id] = state.choices
            restore = self._restore_buttons[state.tweak.id]
            restore.setProperty("sourceRunId", state.restore_run_id)
            restore.setProperty("restoreValue", state.restore_value)
            restore.setProperty("ready", state.status == "ready")
            restore.setEnabled(state.status == "ready" and bool(state.restore_run_id) and not self._busy)
            restore.setVisible(bool(state.restore_run_id or state.restore_message))
            notice = self._restore_notices[state.tweak.id]
            restore_text = self.tr("Previous value: %1").replace("%1", self._label_for(state.tweak.id, state.restore_value)) if state.restore_run_id else self.tr(state.restore_message)
            restore.setText(self.tr("Restore %1").replace("%1", self._label_for(state.tweak.id, state.restore_value)) if state.restore_run_id else self.tr("Restore previous value"))
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
            control.rebuild()
            index = control.findData(state.value)
            control.setCurrentIndex(index)
            self._pending.pop(state.tweak.id, None)
            row.value_label.setText(self.tr("Verified: %1").replace("%1", self._label_for(state.tweak.id, state.value)) if state.status == "ready" else self.tr("Current value unavailable"))
            row.value_label.show()
            if state.status == "ready":
                self._unavailable.discard(state.tweak.id)
            else:
                self._unavailable.add(state.tweak.id)
            control.setEnabled(state.status == "ready" and not self._busy)
            control.blockSignals(False)
            default = str(self._reset_buttons[state.tweak.id].property("defaultValue") or "")
            is_changed = (
                state.status == "ready"
                and bool(default)
                and any(value == default for value, _label in state.choices)
                and not values_equal(state.tweak.id, state.value, default)
            )
            reset = self._reset_buttons[state.tweak.id]
            reset.setProperty("ready", is_changed)
            reset.setEnabled(is_changed and not self._busy)
            reset.setVisible(is_changed)
            if is_changed:
                self._changed.add(state.tweak.id)
            else:
                self._changed.discard(state.tweak.id)
            if state.status != "ready":
                row.set_feedback(state.message or self.tr("This setting is unavailable."), kind="dependency")
            elif state.tweak.id in self._last_changes:
                target, success, message, restored = self._last_changes[state.tweak.id]
                if success and values_equal(state.tweak.id, state.value, target):
                    text = self.tr("Previous value restored and verified: %1") if restored else self.tr("Saved setting verified: %1")
                    text = text.replace("%1", self._label_for(state.tweak.id, state.value))
                    effect = getattr(state.tweak, "effect_hint", "")
                    if state.tweak.id in self._activation_messages:
                        text += " " + self._activation_messages[state.tweak.id]
                    elif effect:
                        text += " " + self.tr(effect)
                    row.set_feedback(text, kind="saved")
                else:
                    detail = message or self.tr("The change could not be verified.")
                    row.set_feedback(self.tr("Current value: %1. %2 Refresh and try again.").replace("%1", state.value).replace("%2", detail), kind="error")
            else:
                row.clear_feedback()
        self._filter_rows(self.search_input.text())

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
        self._pending.clear()
        self.set_busy(False, self.tr("Could not read current settings: %1. Refresh to retry.").replace("%1", message))
        for button in [*self._restore_buttons.values(), *self._reset_buttons.values()]:
            button.setProperty("ready", False)
            button.setEnabled(False)
        for tweak_id, (row, control) in self._rows.items():
            current = str(control.property("currentValue") or "")
            row.value_label.setText(self.tr("Verified: %1").replace("%1", self._label_for(tweak_id, current)) if current else self.tr("Current value unavailable"))
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
