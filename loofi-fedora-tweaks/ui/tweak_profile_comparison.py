"""Read-only comparison of saved library targets, with explicit follow-up actions."""
from __future__ import annotations

from typing import Any

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QComboBox, QDialog, QHBoxLayout, QLabel, QListWidget, QListWidgetItem, QPushButton, QVBoxLayout

from core.tasks.tweak_library import LibraryEntry, compare_profiles


class ProfileComparisonDialog(QDialog):
    def __init__(self, entries: tuple[LibraryEntry, ...], selected: LibraryEntry, parent: Any = None) -> None:
        super().__init__(parent)
        self.operation = ""
        self.chosen_entry: LibraryEntry | None = None
        self.setWindowTitle(self.tr("Compare profiles"))
        self.resize(820, 560)
        layout = QVBoxLayout(self)
        notice = QLabel(self.tr("Compare saved targets from left to right. Current computer settings are not inspected. Edit a copy or start a fresh review separately."))
        notice.setWordWrap(True)
        layout.addWidget(notice)
        selectors = QHBoxLayout()
        self.left = QComboBox()
        self.right = QComboBox()
        for combo, title in ((self.left, "Left profile"), (self.right, "Right profile")):
            label = QLabel(self.tr(title))
            label.setBuddy(combo)
            combo.setAccessibleName(self.tr(title))
            combo.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
            combo.setMinimumContentsLength(16)
            selectors.addWidget(label)
            selectors.addWidget(combo, 1)
            for entry in entries:
                name = self.tr(entry.profile.name) if entry.builtin else entry.profile.name
                combo.addItem(f"{name} [{entry.profile.desktop}] — {entry.id[:12]}", entry)
                combo.setItemData(combo.count() - 1, f"{name}\n{entry.id}", Qt.ItemDataRole.ToolTipRole)
        layout.addLayout(selectors)
        self.error = QLabel()
        self.error.setWordWrap(True)
        layout.addWidget(self.error)
        self.rows = QListWidget()
        self.rows.setAccessibleName(self.tr("Saved profile differences"))
        self.rows.setWordWrap(True)
        layout.addWidget(self.rows)
        self.action_buttons: list[QPushButton] = []
        for combo, side in ((self.left, "left"), (self.right, "right")):
            actions = QHBoxLayout()
            for operation, text in (("edit", f"Edit {side} copy…"), ("review", f"Review {side} profile…")):
                button = QPushButton(self.tr(text))
                button.setAutoDefault(False)
                button.clicked.connect(lambda _checked=False, chosen=combo, action=operation: self._choose(chosen, action))
                actions.addWidget(button)
                self.action_buttons.append(button)
            layout.addLayout(actions)
        close = QPushButton(self.tr("Close"))
        close.setDefault(True)
        close.clicked.connect(self.reject)
        layout.addWidget(close)
        selected_index = next((index for index, entry in enumerate(entries) if entry.id == selected.id), 0)
        self.left.setCurrentIndex(selected_index)
        other_index = next((index for index, entry in enumerate(entries) if entry.id != selected.id and entry.profile.desktop == selected.profile.desktop), selected_index)
        self.right.setCurrentIndex(other_index)
        self.left.currentIndexChanged.connect(self._refresh)
        self.right.currentIndexChanged.connect(self._refresh)
        self._refresh()

    def _refresh(self) -> None:
        self.rows.clear()
        try:
            comparison = compare_profiles(self.left.currentData(), self.right.currentData())
        except ValueError as exc:
            self.error.setText(self.tr(str(exc)))
            for button in self.action_buttons:
                button.setEnabled(False)
            return
        self.error.clear()
        for button in self.action_buttons:
            button.setEnabled(True)
        for row in comparison.entries:
            old = (self.tr(row.left_label) if row.left_label != row.left_value else row.left_label) if row.left_label is not None else self.tr("Absent")
            new = (self.tr(row.right_label) if row.right_label != row.right_value else row.right_label) if row.right_label is not None else self.tr("Absent")
            # Exact values remain visible even when the catalog supplies a label.
            if row.left_label != row.left_value:
                old += f" ({row.left_value})"
            if row.right_label != row.right_value:
                new += f" ({row.right_value})"
            title = self.tr(row.title) if row.title != row.id else row.id
            item = QListWidgetItem(f"{title} ({row.id}) [{self.tr(row.status)}]\n{old} → {new}")
            self.rows.addItem(item)
        if not comparison.entries:
            self.error.setText(self.tr("Both profiles contain no settings."))

    def _choose(self, combo: QComboBox, operation: str) -> None:
        self.chosen_entry = combo.currentData()
        self.operation = operation
        self.accept()
