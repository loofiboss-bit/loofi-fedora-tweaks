"""Profile selection dialogs and shared, window-owned worker integration."""
from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from typing import Any, cast

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QDialog, QDialogButtonBox, QFileDialog, QInputDialog, QLabel, QListWidget, QListWidgetItem, QMessageBox, QPushButton, QHBoxLayout, QVBoxLayout

from core.actions.operation_controller import OperationController
from core.tasks.tweaks import BY_ID, snapshot
from core.tasks.tweak_profiles import ProfileExport, ProfileResult, ProfileReview, apply_profile, export_profile, load_profile, review_profile, save_profile


class ProfileSelectionDialog(QDialog):
    """Scrollable keyboard-accessible selection, with blocked rows visible."""

    def __init__(self, title: str, subtitle: str, rows: list[tuple[str, str, bool]], parent: Any = None, *, accept_label: str = "Apply selected settings") -> None:
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
        cancel_button = buttons.button(QDialogButtonBox.StandardButton.Cancel)
        accept_button = buttons.button(QDialogButtonBox.StandardButton.Ok)
        if cancel_button is not None:
            cancel_button.setDefault(True)
            cancel_button.setAutoDefault(False)
        if accept_button is not None:
            accept_button.setText(self.tr(accept_label))
            accept_button.setDefault(False)
            accept_button.setAutoDefault(False)
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


class ProfileLibraryDialog(QDialog):
    """Select a stored profile without applying or deleting it implicitly."""

    def __init__(self, entries: Any, parent: Any = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(self.tr("My profile library"))
        self.resize(720, 480)
        self.operation = "review"
        self.library_entries = tuple(entries)
        layout = QVBoxLayout(self)
        label = QLabel(self.tr("Edit a copy of any profile and save a new version. Review exact settings before applying. Use Load profile to import a portable file."))
        label.setWordWrap(True)
        layout.addWidget(label)
        self.entries = QListWidget()
        self.entries.setAccessibleName(self.tr("Built-in and personal profiles"))
        self.entries.setWordWrap(True)
        for entry in self.library_entries:
            kind = self.tr("Built-in") if entry.builtin else self.tr("Personal")
            name = self.tr(entry.profile.name) if entry.builtin else entry.profile.name
            description = self.tr(entry.description) if entry.builtin else ""
            item = QListWidgetItem(f"{name} [{entry.profile.desktop}] — {kind}\n{description}")
            item.setData(Qt.ItemDataRole.UserRole, entry)
            self.entries.addItem(item)
        layout.addWidget(self.entries)
        primary_actions = QHBoxLayout()
        actions = QHBoxLayout()
        self.review_button = QPushButton(self.tr("Review selected profile…"))
        self.edit_button = QPushButton(self.tr("Edit a copy…"))
        self.compare_button = QPushButton(self.tr("Compare profiles…"))
        self.export_button = QPushButton(self.tr("Export…"))
        self.remove_button = QPushButton(self.tr("Remove from library"))
        cancel = QPushButton(self.tr("Cancel"))
        cancel.setDefault(True)
        for button, operation in ((self.review_button, "review"), (self.edit_button, "edit"), (self.compare_button, "compare"), (self.export_button, "export"), (self.remove_button, "remove")):
            button.setAutoDefault(False)
            button.clicked.connect(lambda _checked=False, chosen=operation: self._choose(chosen))
            (primary_actions if operation in ("review", "edit", "compare") else actions).addWidget(button)
        cancel.clicked.connect(self.reject)
        actions.addWidget(cancel)
        layout.addLayout(primary_actions)
        layout.addLayout(actions)
        self.entries.currentRowChanged.connect(self._selection_changed)
        if self.entries.count():
            self.entries.setCurrentRow(0)
        self._selection_changed()

    def selected_entry(self) -> Any:
        item = self.entries.currentItem()
        return item.data(Qt.ItemDataRole.UserRole) if item else None

    def _selection_changed(self, _row: int = -1) -> None:
        entry = self.selected_entry()
        self.compare_button.setEnabled(entry is not None and any(other.id != entry.id and other.profile.desktop == entry.profile.desktop for other in self.library_entries))
        self.review_button.setEnabled(entry is not None)
        self.edit_button.setEnabled(entry is not None)
        self.export_button.setEnabled(entry is not None)
        self.remove_button.setEnabled(entry is not None and not entry.builtin)

    def _choose(self, operation: str) -> None:
        self.operation = operation
        self.accept()


class TweakProfilesMixin:
    """Use the shell's sole operation adapter; no parallel mutation workers."""

    _utility_operation_controller: Any

    def _profile_controller(self: Any) -> OperationController:
        if self._utility_operation_controller is None:
            self._utility_operation_controller = OperationController()
        return cast(OperationController, self._utility_operation_controller)

    def _profile_idle(self: Any, page: Any) -> bool:
        if self._utility_operation_adapter is not None:
            page.set_profile_notice(self.tr("Another operation is in progress. Try again when it finishes."), error=True)
            return False
        return True

    def _start_tweak_preset(self: Any, page: Any, preset_id: str | None = None) -> bool:
        """Review and apply a built-in preset through portable profile actions."""
        from core.tasks.tweak_library import ProfileLibrary
        from core.tasks.tweak_presets import profile_for_preset

        if not self._profile_idle(page):
            return False
        if preset_id is None:
            adapter = self._new_utility_operation_adapter(phase="inspection", operation_name=self.tr("Reading profile library"))
            results: list[Any] = []
            adapter.finished.connect(results.append)
            adapter.failed.connect(lambda message: page.set_profile_notice(str(message), error=True))
            adapter.stopped.connect(lambda: self._show_tweak_library(page, results[0]) if results else None)
            page.set_profile_notice(self.tr("Reading profile library…"))
            return bool(adapter.start(lambda: ProfileLibrary().list_with_errors(page.profile)))
        try:
            profile = profile_for_preset(preset_id, page.profile)
        except ValueError as exc:
            page.set_error(str(exc))
            return False
        return bool(self._review_library_profile(page, profile, builtin=True))

    def _review_library_profile(self: Any, page: Any, profile: Any, *, builtin: bool = False) -> bool:
        controller = self._profile_controller()
        adapter = self._new_utility_operation_adapter(phase="review", operation_name=self.tr("Reviewing profile settings"))
        results: list[ProfileReview] = []
        adapter.finished.connect(results.append)
        adapter.failed.connect(page.set_error)
        adapter.cancelled.connect(lambda: page.set_busy(False, self.tr("Profile review cancelled.")))
        adapter.stopped.connect(lambda: self._review_tweak_profile_import(page, results[0], profile.name if builtin else None) if results else None)
        page.set_busy(True, self.tr("Reviewing profile settings…"), cancellable=True)
        return bool(adapter.start(lambda: review_profile(profile, controller, is_cancelled=lambda: adapter.cancel_requested)))

    def _show_tweak_library(self: Any, page: Any, entries: Any) -> None:
        if (isinstance(entries, tuple) and len(entries) == 2
                and isinstance(entries[0], (tuple, list)) and isinstance(entries[1], (tuple, list))
                and all(isinstance(error, str) for error in entries[1])):
            values, errors = entries
        else:
            values, errors = entries, ()
        kwargs = {"focus": bool(getattr(page, "_profile_focus_pending", False))}
        if errors:
            kwargs["errors"] = errors
        page.set_profile_entries(values, **kwargs)
        page.set_profile_notice(self.tr("Choose a profile to review, compare, edit, or add to a configuration."))

    def _handle_tweak_profile_action(self: Any, page: Any, action_name: str, entry: Any) -> None:
        """Dispatch a visible profile-library action without hiding the library."""
        from core.tasks.tweak_library import ProfileLibrary

        if entry is None:
            return
        if action_name == "setup":
            if self.switch_to_route("setup"):
                setup_entry = self._sidebar_index.get("setup")
                if setup_entry is not None:
                    setup_page = self._real_widget_for_entry(setup_entry)
                    setter = getattr(setup_page, "set_pending_profile", None)
                    if callable(setter):
                        setter(entry.profile)
            return
        if action_name == "review":
            self._review_library_profile(page, entry.profile, builtin=entry.builtin)
            return
        if action_name == "edit":
            self._start_tweak_profile_editor(page, entry.profile)
            return
        if action_name == "compare":
            from ui.tweak_profile_comparison import ProfileComparisonDialog

            comparison = ProfileComparisonDialog(tuple(page._profile_entries), entry, page)
            if comparison.exec() != QDialog.DialogCode.Accepted or comparison.chosen_entry is None:
                return
            selected = comparison.chosen_entry
            if comparison.operation == "edit":
                self._start_tweak_profile_editor(page, selected.profile)
            elif comparison.operation == "review":
                self._review_library_profile(page, selected.profile, builtin=selected.builtin)
            return
        if action_name == "remove":
            if entry.builtin:
                return
            if QMessageBox.question(page, self.tr("Remove local profile"), self.tr("Remove this profile from your library?")) != QMessageBox.StandardButton.Yes:
                return

            def operation() -> None:
                ProfileLibrary().remove(entry.id)
        elif action_name == "export":
            filename, _filter = QFileDialog.getSaveFileName(page, self.tr("Export profile"), "settings.json", self.tr("JSON profiles (*.json)"))
            if not filename:
                return

            def operation() -> None:
                save_profile(Path(filename), entry.profile)
        else:
            return
        if not self._profile_idle(page):
            return
        adapter = self._new_utility_operation_adapter(phase="inspection", operation_name=self.tr("Updating profile library"))
        adapter.failed.connect(lambda message: page.set_profile_notice(str(message), error=True))
        if action_name == "remove":
            adapter.stopped.connect(lambda: self._start_tweak_preset(page))
        else:
            adapter.finished.connect(lambda _result: page.set_profile_notice(self.tr("Profile exported.")))
        page.set_profile_notice(self.tr("Updating profile library…"))
        adapter.start(operation)

    def _start_tweak_profile_editor(self: Any, page: Any, profile: Any) -> bool:
        """Inspect editor choices on the window-owned read-only worker."""
        if not self._profile_idle(page):
            return False
        controller = self._profile_controller()
        adapter = self._new_utility_operation_adapter(phase="inspection", operation_name=self.tr("Inspecting profile choices"))
        results: list[Any] = []
        adapter.finished.connect(results.append)
        adapter.failed.connect(lambda message: page.set_profile_notice(str(message), error=True))
        adapter.cancelled.connect(lambda: page.set_profile_notice(self.tr("Profile editor inspection cancelled.")))
        adapter.stopped.connect(lambda: self._show_tweak_profile_editor(page, profile, results[0]) if results else None)
        page.set_busy(True, self.tr("Reading supported profile choices…"), cancellable=True)
        return bool(adapter.start(lambda: snapshot(page.profile, controller.orchestrator.runtime, is_cancelled=lambda: adapter.cancel_requested)))

    def _show_tweak_profile_editor(self: Any, page: Any, profile: Any, states: Any) -> None:
        page.set_busy(False, self.tr("Edit a local copy; computer settings change only after a separate review."))
        page.show_profile_editor(profile, states)

    def _save_tweak_profile_copy(
        self: Any, page: Any, profile: Any, review_after: bool, return_after: bool, *, close_after: bool = False
    ) -> bool:
        """Persist first, then select the exact stored profile or review it fresh."""
        if not self._profile_idle(page):
            return False
        from core.tasks.tweak_library import ProfileLibrary

        adapter = self._new_utility_operation_adapter(phase="inspection", operation_name=self.tr("Saving profile copy"))
        results: list[Any] = []
        adapter.finished.connect(results.append)

        def save_failed(message: str) -> None:
            page.set_profile_notice(str(message), error=True)
            if close_after:
                setattr(self, "_quit_after_profile_save", False)

        def save_cancelled() -> None:
            page.set_profile_notice(self.tr("Profile saving was cancelled."), error=True)
            if close_after:
                setattr(self, "_quit_after_profile_save", False)

        adapter.failed.connect(save_failed)
        adapter.cancelled.connect(save_cancelled)
        page.set_profile_saving(True)
        page.set_profile_notice(self.tr("Saving profile copy…"))

        def finish() -> None:
            page.set_profile_saving(False)
            if not results:
                if close_after:
                    setattr(self, "_quit_after_profile_save", False)
                return
            saved = results[0]
            entries = tuple(item for item in page._profile_entries if item.id != saved.id) + (saved,)
            page.set_profile_entries(entries, selected_id=saved.id)
            page.set_profile_notice(self.tr("Profile copy saved and selected."))
            if review_after:
                # The returned object is the exact validated, persisted profile.
                self._review_library_profile(page, saved.profile, builtin=False)
            elif not return_after:
                page.set_profile_notice(self.tr("Profile copy saved and selected."))
            if close_after and not review_after:
                from PyQt6.QtCore import QTimer

                quit_after_save = bool(getattr(self, "_quit_after_profile_save", False))
                setattr(self, "_quit_after_profile_save", False)
                QTimer.singleShot(0, self.quit_app if quit_after_save else self.close)

        adapter.stopped.connect(finish)
        started = bool(adapter.start(lambda: ProfileLibrary().add(profile)))
        if not started:
            page.set_profile_saving(False)
            page.set_profile_notice(self.tr("Profile copy could not be saved; your draft is still open."), error=True)
            if close_after:
                setattr(self, "_quit_after_profile_save", False)
        return started

    def _start_tweak_profile_export(self: Any, page: Any) -> bool:
        if not self._profile_idle(page):
            return False
        name, accepted = QInputDialog.getText(page, self.tr("Save current settings"), self.tr("Profile name:"), text=self.tr("My settings"))
        if not accepted:
            return False
        controller = self._profile_controller()
        adapter = self._new_utility_operation_adapter(phase="inspection", operation_name=self.tr("Reading settings for profile"))
        results: list[ProfileExport] = []
        adapter.finished.connect(results.append)
        adapter.failed.connect(lambda message: page.set_profile_notice(str(message), error=True))
        adapter.cancelled.connect(lambda: page.set_busy(False, self.tr("Profile export cancelled.")))
        adapter.stopped.connect(lambda: self._review_tweak_profile_export(page, results[0]) if results else None)
        page.set_busy(True, self.tr("Reading settings for export…"), cancellable=True)
        return bool(adapter.start(lambda: export_profile(name, page.profile, controller.orchestrator.runtime, is_cancelled=lambda: adapter.cancel_requested)))

    def _review_tweak_profile_export(self: Any, page: Any, exported: ProfileExport) -> None:
        page.set_busy(False, self.tr("Choose the settings to save."))
        rows = [(key, f"{page.tr(BY_ID[key].title)}: {value}", True) for key, value in exported.profile.settings]
        rows.extend((key, f"{key}: {reason}", False) for key, reason in exported.omitted)
        dialog = ProfileSelectionDialog(self.tr("Save current settings"), self.tr("Choose supported user settings. Unavailable, custom and system-wide values are omitted."), rows, page, accept_label="Continue")
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        selected = set(dialog.selected_ids())
        if not selected:
            page.set_busy(False, self.tr("No settings selected."))
            return
        destination, accepted = QInputDialog.getItem(
            page, self.tr("Save profile"), self.tr("Save destination:"),
            [self.tr("My profile library"), self.tr("Portable JSON file")], 0, False,
        )
        if not accepted:
            return
        filename = ""
        if destination == self.tr("Portable JSON file"):
            filename, _filter = QFileDialog.getSaveFileName(page, self.tr("Save tweak profile"), "settings.json", self.tr("JSON profiles (*.json)"))
            if not filename:
                return
        chosen = replace(exported.profile, settings=tuple(row for row in exported.profile.settings if row[0] in selected))
        if not self._profile_idle(page):
            return
        adapter = self._new_utility_operation_adapter(phase="inspection", operation_name=self.tr("Saving profile"))
        adapter.failed.connect(lambda message: page.set_profile_notice(str(message), error=True))
        adapter.finished.connect(lambda _result: page.set_profile_notice(self.tr("Profile saved with %1 settings.").replace("%1", str(len(chosen.settings)))))
        page.set_profile_notice(self.tr("Saving profile…"))
        from core.tasks.tweak_library import ProfileLibrary

        adapter.start(lambda: save_profile(Path(filename), chosen) if filename else ProfileLibrary().add(chosen))

    def _start_tweak_profile_import(self: Any, page: Any) -> bool:
        if not self._profile_idle(page):
            return False
        filename, _filter = QFileDialog.getOpenFileName(page, self.tr("Load tweak profile"), "", self.tr("JSON profiles (*.json)"))
        if not filename:
            return False
        controller = self._profile_controller()
        adapter = self._new_utility_operation_adapter(phase="review", operation_name=self.tr("Reviewing imported profile"))
        results: list[ProfileReview] = []
        adapter.finished.connect(results.append)
        adapter.failed.connect(lambda message: page.set_profile_notice(str(message), error=True))
        adapter.cancelled.connect(lambda: page.set_profile_notice(self.tr("Profile review cancelled.")))
        adapter.stopped.connect(lambda: self._review_tweak_profile_import(page, results[0]) if results else None)
        page.set_busy(True, self.tr("Reading and reviewing profile…"), cancellable=True)

        def import_and_review() -> ProfileReview:
            from core.tasks.tweak_library import ProfileLibrary

            profile = load_profile(Path(filename))
            review = review_profile(profile, controller, is_cancelled=lambda: adapter.cancel_requested)
            if not adapter.cancel_requested:
                ProfileLibrary().add(profile)
            return review

        return bool(adapter.start(import_and_review))

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
        adapter = self._new_utility_operation_adapter(phase="change", operation_name=self.tr("Applying reviewed profile"))
        results: list[ProfileResult] = []
        adapter.finished.connect(results.append)
        adapter.failed.connect(lambda message: page.set_profile_notice(str(message), error=True))
        adapter.cancelled.connect(lambda: page.set_profile_notice(self.tr("Profile application cancelled before any change started.")))
        adapter.stopped.connect(lambda: self._finish_tweak_profile(page, results[0], review, tuple(selected)) if results else None)
        page.set_busy(True, self.tr("Applying reviewed settings…"), cancellable=True)
        page.cancel_snapshot_button.setText(self.tr("Cancel remaining changes"))
        adapter.start(lambda: apply_profile(review, controller, confirmed=True, selected_ids=selected, is_cancelled=lambda: adapter.cancel_requested))

    def _finish_tweak_profile(self: Any, page: Any, result: ProfileResult, review: ProfileReview | None = None, selected_ids: tuple[str, ...] | None = None) -> None:
        page.set_busy(False, result.message)
        page.set_profile_result(result)
        if result.success and review is not None and selected_ids is not None:
            from core.tasks.guide_profile_results import GuideProfileResultStore

            try:
                GuideProfileResultStore().save(result, review, selected_ids)
            except (OSError, RuntimeError, TypeError, ValueError):
                page.set_profile_notice(self.tr("Settings results remain in Activity. A complete profile result reference could not be saved."), error=True)
        affected = tuple(entry.id for entry in result.entries if entry.status != "skipped")
        if not affected:
            return
        controller = self._profile_controller()
        adapter = self._new_utility_operation_adapter(phase="verification", operation_name=self.tr("Verifying profile settings"))
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
