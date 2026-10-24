"""Inline library and authoring views for personal tweak profiles."""
from __future__ import annotations

from typing import Any

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QGridLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
    QWidget,
)
from core.tasks.tweaks import BY_ID


class ProfileLibraryView(QWidget):
    """Select a saved profile and request explicit follow-up actions."""

    actionRequested = pyqtSignal(str, object)
    saveCurrentRequested = pyqtSignal()
    loadRequested = pyqtSignal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("profileLibraryView")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        explanation = QLabel(self.tr(
            "Review a profile against current settings, or edit a copy and save it locally. "
            "No computer settings change until a separate review is approved."
        ))
        explanation.setWordWrap(True)
        layout.addWidget(explanation)
        self.search = QLineEdit()
        self.search.setPlaceholderText(self.tr("Search profile names and settings…"))
        self.search.setAccessibleName(self.tr("Search profile library"))
        self.search.textChanged.connect(self._apply_filter)
        layout.addWidget(self.search)
        self.library_notice = QLabel(self.tr("Search by profile name or supported setting."))
        self.library_notice.setWordWrap(True)
        self.library_notice.setObjectName("profileLibraryNotice")
        layout.addWidget(self.library_notice)
        self._all_entries: tuple[Any, ...] = ()
        self._read_errors: tuple[str, ...] = ()
        self._selected_id = ""
        self.entries = QListWidget()
        self.entries.setObjectName("profileLibraryEntries")
        self.entries.setAccessibleName(self.tr("Built-in and personal profiles"))
        self.entries.setWordWrap(True)
        self.entries.currentRowChanged.connect(self._selection_changed)
        layout.addWidget(self.entries, 1)

        primary = QGridLayout()
        self.review_button = self._button("Review selected profile…", "Review the selected profile against current settings")
        self.edit_button = self._button("Edit a copy…", "Edit a copy of the selected profile")
        self.compare_button = self._button("Compare profiles…", "Compare the selected profile with another profile")
        self.setup_button = self._button("Add to configuration", "Add this settings profile to My Fedora configuration")
        for index, (button, action) in enumerate(((self.review_button, "review"), (self.edit_button, "edit"), (self.compare_button, "compare"))):
            button.clicked.connect(lambda _checked=False, selected=action: self._request(selected))
            primary.addWidget(button, index // 2, index % 2)
        self.setup_button.clicked.connect(lambda: self._request("setup"))
        primary.addWidget(self.setup_button, 1, 1)
        layout.addLayout(primary)

        secondary = QGridLayout()
        self.export_button = self._button("Export…", "Export the selected profile")
        self.remove_button = self._button("Remove from library", "Remove the selected personal profile")
        self.save_current_button = self._button("Save current settings…", "Save supported user settings as a profile")
        self.load_button = self._button("Load profile…", "Load and review a portable profile")
        secondary_actions = ((self.export_button, "export"), (self.remove_button, "remove"))
        for index, (button, action) in enumerate(secondary_actions):
            button.clicked.connect(lambda _checked=False, selected=action: self._request(selected))
            secondary.addWidget(button, index, 0)
        self.save_current_button.clicked.connect(self.saveCurrentRequested.emit)
        self.load_button.clicked.connect(self.loadRequested.emit)
        secondary.addWidget(self.save_current_button, 0, 1)
        secondary.addWidget(self.load_button, 1, 1)
        layout.addLayout(secondary)

    def _button(self, label: str, accessible: str) -> QPushButton:
        button = QPushButton(self.tr(label))
        button.setAccessibleName(self.tr(accessible))
        button.setAutoDefault(False)
        return button

    def set_entries(self, entries: Any, *, selected_id: str = "", errors: Any = ()) -> None:
        self._all_entries = tuple(entries)
        self._read_errors = tuple(str(item) for item in errors)
        self.library_notice.setText(" ".join(self._read_errors) if self._read_errors else self.tr("Search by profile name or supported setting."))
        self._selected_id = selected_id or getattr(self.selected_entry(), "id", "")
        self._apply_filter()

    def _apply_filter(self, _query: str = "") -> None:
        values = self._all_entries
        needle = self.search.text().strip().casefold()
        if needle:
            values = tuple(entry for entry in values if needle in " ".join(
                (entry.profile.name, entry.description,
                 *(f"{key} {BY_ID[key].title if key in BY_ID else key}" for key, _value in entry.profile.settings))
            ).casefold())
        self.entries.blockSignals(True)
        self.entries.clear()
        for entry in values:
            kind = self.tr("Built-in") if entry.builtin else self.tr("Personal")
            name = self.tr(entry.profile.name) if entry.builtin else entry.profile.name
            description = self.tr(entry.description) if entry.builtin else self.tr("Personal copy saved on this computer.")
            setting_names = ", ".join(BY_ID[key].title if key in BY_ID else key for key, _value in entry.profile.settings)
            item = QListWidgetItem(f"{name} [{entry.profile.desktop}] — {kind}\n{description}\n{setting_names}")
            item.setData(Qt.ItemDataRole.UserRole, entry)
            self.entries.addItem(item)
        selected_index = -1
        for index in range(self.entries.count()):
            selected_item = self.entries.item(index)
            if selected_item is not None and getattr(selected_item.data(Qt.ItemDataRole.UserRole), "id", "") == self._selected_id:
                selected_index = index
                break
        self.entries.setCurrentRow(selected_index if selected_index >= 0 else (0 if self.entries.count() else -1))
        self.entries.blockSignals(False)
        if not self._selected_id:
            self._selected_id = getattr(self.selected_entry(), "id", "")
        self._update_action_buttons()

    def selected_entry(self) -> Any:
        item = self.entries.currentItem()
        return item.data(Qt.ItemDataRole.UserRole) if item is not None else None

    def focus_entries(self) -> None:
        self.entries.setFocus(Qt.FocusReason.OtherFocusReason)

    def _selection_changed(self, _row: int = -1) -> None:
        self._selected_id = getattr(self.selected_entry(), "id", "")
        self._update_action_buttons()

    def _update_action_buttons(self) -> None:
        entry = self.selected_entry()
        same_desktop_peer = False
        if entry is not None:
            same_desktop_peer = any(candidate.id != entry.id and candidate.profile.desktop == entry.profile.desktop
                                    for candidate in self._all_entries)
        for button in (self.review_button, self.edit_button, self.export_button, self.setup_button):
            button.setEnabled(entry is not None)
        self.compare_button.setEnabled(same_desktop_peer)
        self.remove_button.setEnabled(entry is not None and not entry.builtin)

    def _request(self, action: str) -> None:
        entry = self.selected_entry()
        if entry is not None:
            self.actionRequested.emit(action, entry)


class ProfileEditorExitDialog:
    """Small helper kept separate so all dirty exits share one decision."""

    @staticmethod
    def choose(parent: QWidget) -> str:
        from PyQt6.QtWidgets import QMessageBox

        dialog = QMessageBox(parent)
        dialog.setIcon(QMessageBox.Icon.Question)
        dialog.setWindowTitle(parent.tr("Unsaved profile copy"))
        dialog.setText(parent.tr("Save your profile copy before leaving this editor?"))
        dialog.setInformativeText(parent.tr("Your computer settings have not changed."))
        save = dialog.addButton(parent.tr("Save copy"), QMessageBox.ButtonRole.AcceptRole)
        discard = dialog.addButton(parent.tr("Discard"), QMessageBox.ButtonRole.DestructiveRole)
        cancel = dialog.addButton(QMessageBox.StandardButton.Cancel)
        dialog.setDefaultButton(cancel)
        dialog.setEscapeButton(cancel)
        dialog.exec()
        clicked = dialog.clickedButton()
        if clicked is save:
            return "save"
        if clicked is discard:
            return "discard"
        return "cancel"
