"""Profile selection dialogs and shared, window-owned worker integration."""
from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from typing import Any, cast

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QDialog, QDialogButtonBox, QFileDialog, QInputDialog, QLabel, QListWidget, QListWidgetItem, QMessageBox, QVBoxLayout

from core.actions.operation_controller import OperationController
from core.tasks.tweaks import BY_ID, snapshot
from core.tasks.tweak_profiles import ProfileExport, ProfileResult, ProfileReview, apply_profile, export_profile, load_profile, review_profile, save_profile


class ProfileSelectionDialog(QDialog):
    """Scrollable keyboard-accessible selection, with blocked rows visible."""

    def __init__(self, title: str, subtitle: str, rows: list[tuple[str, str, bool]], parent: Any = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(title)
        self.resize(720, 480)
        layout = QVBoxLayout(self)
        label = QLabel(subtitle)
        label.setWordWrap(True)
        layout.addWidget(label)
        self.entries = QListWidget()
        self.entries.setAccessibleName(self.tr("Profile settings"))
        self.entries.setWordWrap(True)
        for key, text, selectable in rows:
            item = QListWidgetItem(text)
            item.setData(Qt.ItemDataRole.UserRole, key)
            if selectable:
                item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
                item.setCheckState(Qt.CheckState.Checked)
            else:
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEnabled)
            self.entries.addItem(item)
        layout.addWidget(self.entries)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Cancel | QDialogButtonBox.StandardButton.Ok)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def selected_ids(self) -> tuple[str, ...]:
        selected: list[str] = []
        for index in range(self.entries.count()):
            item = self.entries.item(index)
            if item is not None and item.checkState() == Qt.CheckState.Checked:
                selected.append(str(item.data(Qt.ItemDataRole.UserRole)))
        return tuple(selected)


class TweakProfilesMixin:
    """Use the shell's sole operation adapter; no parallel mutation workers."""

    _utility_operation_controller: Any

    def _profile_controller(self: Any) -> OperationController:
        if self._utility_operation_controller is None:
            self._utility_operation_controller = OperationController()
        return cast(OperationController, self._utility_operation_controller)

    def _profile_idle(self: Any, page: Any) -> bool:
        if self._utility_operation_adapter is not None:
            page.set_error(self.tr("Another operation is in progress. Try again when it finishes."))
            return False
        return True

    def _start_tweak_preset(self: Any, page: Any) -> bool:
        """Review and apply a built-in preset through portable profile actions."""
        from core.tasks.tweak_presets import PRESETS, profile_for_preset

        if not self._profile_idle(page):
            return False
        # PlatformProfile exposes a desktop identity through the shared helper;
        # resolve availability by attempting the closed preset mapping.
        available = []
        for preset in PRESETS:
            try:
                profile_for_preset(preset.id, page.profile)
            except ValueError:
                continue
            available.append(preset)
        if not available:
            page.set_error(self.tr("No presets are available for this desktop."))
            return False
        from PyQt6.QtWidgets import QInputDialog

        names = [self.tr(preset.name) for preset in available]
        chosen, accepted = QInputDialog.getItem(page, self.tr("Choose a desktop preset"),
                                                self.tr("Choose a preset to review:"), names, 0, False)
        if not accepted:
            return False
        preset = available[names.index(chosen)]
        try:
            profile = profile_for_preset(preset.id, page.profile)
        except ValueError as exc:
            page.set_error(str(exc))
            return False
        controller = self._profile_controller()
        adapter = self._new_utility_operation_adapter(phase="review")
        results: list[ProfileReview] = []
        adapter.finished.connect(results.append)
        adapter.failed.connect(page.set_error)
        adapter.cancelled.connect(lambda: page.set_busy(False, self.tr("Preset review cancelled.")))
        adapter.stopped.connect(lambda: self._review_tweak_profile_import(page, results[0], preset.name) if results else None)
        page.set_busy(True, self.tr("Reviewing preset settings…"), cancellable=True)
        return bool(adapter.start(lambda: review_profile(profile, controller, is_cancelled=lambda: adapter.cancel_requested)))

    def _start_tweak_profile_export(self: Any, page: Any) -> bool:
        if not self._profile_idle(page):
            return False
        name, accepted = QInputDialog.getText(page, self.tr("Save current settings"), self.tr("Profile name:"), text=self.tr("My settings"))
        if not accepted:
            return False
        controller = self._profile_controller()
        adapter = self._new_utility_operation_adapter(phase="inspection")
        results: list[ProfileExport] = []
        adapter.finished.connect(results.append)
        adapter.failed.connect(page.set_error)
        adapter.cancelled.connect(lambda: page.set_busy(False, self.tr("Profile export cancelled.")))
        adapter.stopped.connect(lambda: self._review_tweak_profile_export(page, results[0]) if results else None)
        page.set_busy(True, self.tr("Reading settings for export…"), cancellable=True)
        return bool(adapter.start(lambda: export_profile(name, page.profile, controller.orchestrator.runtime, is_cancelled=lambda: adapter.cancel_requested)))

    def _review_tweak_profile_export(self: Any, page: Any, exported: ProfileExport) -> None:
        page.set_busy(False, self.tr("Choose the settings to save."))
        rows = [(key, f"{page.tr(BY_ID[key].title)}: {value}", True) for key, value in exported.profile.settings]
        rows.extend((key, f"{key}: {reason}", False) for key, reason in exported.omitted)
        dialog = ProfileSelectionDialog(self.tr("Save current settings"), self.tr("Choose supported user settings. Unavailable, custom and system-wide values are omitted."), rows, page)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        selected = set(dialog.selected_ids())
        if not selected:
            page.set_busy(False, self.tr("No settings selected."))
            return
        filename, _filter = QFileDialog.getSaveFileName(page, self.tr("Save tweak profile"), "settings.json", self.tr("JSON profiles (*.json)"))
        if not filename:
            return
        chosen = replace(exported.profile, settings=tuple(row for row in exported.profile.settings if row[0] in selected))
        if not self._profile_idle(page):
            return
        adapter = self._new_utility_operation_adapter(phase="inspection")
        adapter.failed.connect(page.set_error)
        adapter.finished.connect(lambda _result: page.set_busy(False, self.tr("Profile saved with %1 settings.").replace("%1", str(len(chosen.settings)))))
        page.set_busy(True, self.tr("Saving profile…"))
        adapter.start(lambda: save_profile(Path(filename), chosen))

    def _start_tweak_profile_import(self: Any, page: Any) -> bool:
        if not self._profile_idle(page):
            return False
        filename, _filter = QFileDialog.getOpenFileName(page, self.tr("Load tweak profile"), "", self.tr("JSON profiles (*.json)"))
        if not filename:
            return False
        controller = self._profile_controller()
        adapter = self._new_utility_operation_adapter(phase="review")
        results: list[ProfileReview] = []
        adapter.finished.connect(results.append)
        adapter.failed.connect(page.set_error)
        adapter.cancelled.connect(lambda: page.set_busy(False, self.tr("Profile review cancelled.")))
        adapter.stopped.connect(lambda: self._review_tweak_profile_import(page, results[0]) if results else None)
        page.set_busy(True, self.tr("Reading and reviewing profile…"), cancellable=True)
        return bool(adapter.start(lambda: review_profile(load_profile(Path(filename)), controller, is_cancelled=lambda: adapter.cancel_requested)))

    def _review_tweak_profile_import(self: Any, page: Any, review: ProfileReview, preset_name: str | None = None) -> None:
        page.set_busy(False, self.tr("Review the profile changes before applying them."))
        rows = [(entry.id, f"{page.tr(entry.title)}: {entry.before or '?'} → {entry.value} [{page.tr(entry.status)}] {entry.message}", entry.status == "ready") for entry in review.entries]
        title = self.tr("Review preset: %1").replace("%1", self.tr(preset_name)) if preset_name else self.tr("Review profile: %1").replace("%1", review.name)
        dialog = ProfileSelectionDialog(title,
                                        self.tr("Apply only the checked changes. Each setting is verified; remaining changes stop if a value changed or verification fails. Previous values remain in Activity."), rows, page)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        selected = dialog.selected_ids()
        if not selected:
            page.set_busy(False, self.tr("No changes selected."))
            return
        if not self._profile_idle(page):
            return
        controller = self._profile_controller()
        adapter = self._new_utility_operation_adapter(phase="change")
        results: list[ProfileResult] = []
        adapter.finished.connect(results.append)
        adapter.failed.connect(page.set_error)
        adapter.cancelled.connect(lambda: page.set_busy(False, self.tr("Profile application cancelled before any change started.")))
        adapter.stopped.connect(lambda: self._finish_tweak_profile(page, results[0]) if results else None)
        page.set_busy(True, self.tr("Applying reviewed settings…"), cancellable=True)
        page.cancel_snapshot_button.setText(self.tr("Cancel remaining changes"))
        adapter.start(lambda: apply_profile(review, controller, confirmed=True, selected_ids=selected, is_cancelled=lambda: adapter.cancel_requested))

    def _finish_tweak_profile(self: Any, page: Any, result: ProfileResult) -> None:
        page.set_busy(False, result.message)
        dialog = QMessageBox(page)
        dialog.setWindowTitle(self.tr("Profile results"))
        dialog.setText(result.message)
        dialog.setIcon(QMessageBox.Icon.Information if result.success else QMessageBox.Icon.Warning)
        dialog.setDetailedText("\n".join(f"{entry.id}: {entry.status} — {entry.message}" for entry in result.entries))
        dialog.exec()
        affected = tuple(entry.id for entry in result.entries if entry.status != "skipped")
        if not affected:
            return
        controller = self._profile_controller()
        adapter = self._new_utility_operation_adapter(phase="inspection")
        adapter.finished.connect(page.set_states)

        def invalidate_affected(message: str) -> None:
            for tweak_id in affected:
                page.set_check_error(tweak_id, message)

        adapter.failed.connect(invalidate_affected)
        adapter.cancelled.connect(lambda: invalidate_affected(self.tr("Settings inspection cancelled. Previous values are not current.")))
        page.set_busy(True, self.tr("Checking settings included in the profile…"), cancellable=True)
        started = adapter.start(
            lambda: snapshot(
                page.profile,
                controller.orchestrator.runtime,
                tweak_ids=affected,
                is_cancelled=lambda: adapter.cancel_requested,
            )
        )
        if not started:
            invalidate_affected(self.tr("Settings inspection could not be started. Refresh to try again."))
