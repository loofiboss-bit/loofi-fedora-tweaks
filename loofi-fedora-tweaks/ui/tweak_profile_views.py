"""Inline library and authoring views for personal tweak profiles."""
from __future__ import annotations

from typing import Any

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QGridLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


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
        for index, (button, action) in enumerate(((self.review_button, "review"), (self.edit_button, "edit"), (self.compare_button, "compare"))):
            button.clicked.connect(lambda _checked=False, selected=action: self._request(selected))
            primary.addWidget(button, index // 2, index % 2)
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

    def set_entries(self, entries: Any, *, selected_id: str = "") -> None:
        values = tuple(entries)
        self.entries.blockSignals(True)
        self.entries.clear()
        for entry in values:
            kind = self.tr("Built-in") if entry.builtin else self.tr("Personal")
            name = self.tr(entry.profile.name) if entry.builtin else entry.profile.name
            description = self.tr(entry.description) if entry.builtin else self.tr("Personal copy saved on this computer.")
            item = QListWidgetItem(f"{name} [{entry.profile.desktop}] — {kind}\n{description}")
            item.setData(Qt.ItemDataRole.UserRole, entry)
            self.entries.addItem(item)
        selected_index = -1
        for index in range(self.entries.count()):
            selected_item = self.entries.item(index)
            if selected_item is not None and getattr(selected_item.data(Qt.ItemDataRole.UserRole), "id", "") == selected_id:
                selected_index = index
                break
        self.entries.setCurrentRow(selected_index if selected_index >= 0 else (0 if self.entries.count() else -1))
        self.entries.blockSignals(False)
        self._selection_changed()

    def selected_entry(self) -> Any:
        item = self.entries.currentItem()
        return item.data(Qt.ItemDataRole.UserRole) if item is not None else None

    def focus_entries(self) -> None:
        self.entries.setFocus(Qt.FocusReason.OtherFocusReason)

    def _selection_changed(self, _row: int = -1) -> None:
        entry = self.selected_entry()
        same_desktop_peer = False
        if entry is not None:
            for index in range(self.entries.count()):
                item = self.entries.item(index)
                candidate = item.data(Qt.ItemDataRole.UserRole) if item is not None else None
                if candidate is not None and candidate.id != entry.id and candidate.profile.desktop == entry.profile.desktop:
                    same_desktop_peer = True
                    break
        for button in (self.review_button, self.edit_button, self.export_button):
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
