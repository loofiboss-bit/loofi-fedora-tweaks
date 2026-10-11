"""Focused UX contracts for the v33 Tweaks and profile workspace."""
from __future__ import annotations

import os
from types import MappingProxyType, SimpleNamespace
from unittest import TestCase
from unittest.mock import Mock, patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication, QDialog, QLabel, QPushButton

from core.tasks.tweak_library import LibraryEntry
from core.tasks.tweak_profiles import ProfileEntryResult, ProfileResult, TweakProfile
from core.tasks.tweaks import BY_ID, TweakState
from ui.main_window_utility import MainWindowUtilityMixin
from ui.tweak_profiles import TweakProfilesMixin
from ui.tweaks_page import TweaksPage


class Signal:
    def __init__(self) -> None:
        self.callback = None

    def connect(self, callback) -> None:
        self.callback = callback

    def emit(self, *args) -> None:
        if self.callback is not None:
            self.callback(*args)


class Adapter:
    def __init__(self) -> None:
        for name in ("finished", "failed", "cancelled", "stopped"):
            setattr(self, name, Signal())
        self.operation = None

    def start(self, operation) -> bool:
        self.operation = operation
        return True

    def complete(self, *, late_cancel_flag: bool = False) -> object:
        result = self.operation()
        self.finished.emit(result)
        if late_cancel_flag:
            self.cancel_requested = True
        self.stopped.emit()
        return result


def entry(identifier: str, profile: TweakProfile | None = None, *, builtin: bool = False) -> LibraryEntry:
    selected = profile or TweakProfile(identifier, "kde", (("kde-single-click", "true"),))
    return LibraryEntry(identifier, selected, builtin=builtin)


class TweaksV33Tests(TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def make_page(self) -> TweaksPage:
        return TweaksPage(SimpleNamespace(
            is_fedora=True,
            desktop=SimpleNamespace(value="kde"),
            session_type=SimpleNamespace(value="wayland"),
            deployment_backend=SimpleNamespace(value="dnf5"),
        ))

    def test_profile_draft_survives_subview_navigation_and_dirty_exit_cancel(self) -> None:
        page = self.make_page()
        source = TweakProfile("Original", "kde", (("kde-single-click", "false"),))
        state = TweakState(BY_ID["kde-single-click"], "ready", "false", BY_ID["kde-single-click"].choices)
        try:
            page.show_profile_editor(source, (state,))
            editor = page.profile_editor_view
            include, control = editor.rows["kde-single-click"]
            control.setCurrentIndex(control.findData("true"))
            page.set_subview("settings", load_profiles=False)
            page.set_subview("profiles")
            self.assertIs(page.profile_views.currentWidget(), editor)
            self.assertEqual(control.currentData(), "true")

            with patch("ui.tweak_profile_views.ProfileEditorExitDialog.choose", return_value="cancel"):
                editor.request_exit()
            self.assertIs(page.profile_views.currentWidget(), editor)
            self.assertTrue(page._profile_editor_open)
        finally:
            page.close()

    def test_dirty_editor_offers_discard_and_save_before_exit(self) -> None:
        page = self.make_page()
        source = TweakProfile("Original", "kde", (("kde-single-click", "false"),))
        state = TweakState(BY_ID["kde-single-click"], "ready", "false", BY_ID["kde-single-click"].choices)
        try:
            page.show_profile_editor(source, (state,))
            editor = page.profile_editor_view
            editor.name.setText("Edited copy")
            exited: list[bool] = []
            saved: list[tuple[object, bool, bool]] = []
            editor.exitRequested.connect(lambda: exited.append(True))
            editor.saveRequested.connect(lambda *args: saved.append(args))
            with patch("ui.tweak_profile_views.ProfileEditorExitDialog.choose", return_value="discard"):
                editor.request_exit()
            self.assertEqual(exited, [True])
            self.assertEqual(saved, [])

            page.show_profile_editor(source, (state,))
            editor = page.profile_editor_view
            editor.name.setText("Saved copy")
            editor.saveRequested.connect(lambda *args: saved.append(args))
            with patch("ui.tweak_profile_views.ProfileEditorExitDialog.choose", return_value="save"):
                editor.request_exit()
            self.assertEqual(len(saved), 1)
            self.assertTrue(saved[0][2])
            self.assertEqual(saved[0][0].name, "Saved copy")
        finally:
            page.close()

    def test_window_close_offers_save_discard_cancel_and_waits_for_save(self) -> None:
        page = self.make_page()
        source = TweakProfile("Original", "kde", (("kde-single-click", "false"),))
        state = TweakState(BY_ID["kde-single-click"], "ready", "false", BY_ID["kde-single-click"].choices)
        try:
            page.show_profile_editor(source, (state,))
            editor = page.profile_editor_view
            editor.name.setText("Edited before close")
            with patch("ui.tweak_profile_views.ProfileEditorExitDialog.choose", return_value="cancel"):
                self.assertEqual(page.request_close_for_profile(), "cancel")
            self.assertTrue(page._profile_editor_open)

            saved: list[tuple[object, bool, bool, bool]] = []
            editor.saveRequested.connect(lambda *args: saved.append(args))
            with patch("ui.tweak_profile_views.ProfileEditorExitDialog.choose", return_value="save"):
                self.assertEqual(page.request_close_for_profile(), "saving")
            self.assertEqual(len(saved), 1)
            self.assertTrue(saved[0][2])
            self.assertTrue(saved[0][3])
            editor.set_saving(True)
            self.assertEqual(page.request_close_for_profile(), "cancel")
        finally:
            page.close()

    def test_profile_save_selects_exact_persisted_copy_then_reviews_it_fresh(self) -> None:
        original = TweakProfile("Original", "kde", ())
        persisted = TweakProfile("Validated copy", "kde", (("kde-single-click", "true"),))
        stored = entry("content-hash", persisted)
        adapter = Adapter()
        page = Mock(_profile_entries=(entry("existing"),))
        owner = SimpleNamespace(
            tr=lambda text: text,
            _profile_idle=lambda _page: True,
            _new_utility_operation_adapter=Mock(return_value=adapter),
            _review_library_profile=Mock(),
        )
        with patch("core.tasks.tweak_library.ProfileLibrary") as library:
            library.return_value.add.return_value = stored
            self.assertTrue(TweakProfilesMixin._save_tweak_profile_copy(owner, page, original, True, False))
            adapter.complete(late_cancel_flag=True)
        page.set_profile_entries.assert_called_once()
        args, kwargs = page.set_profile_entries.call_args
        self.assertEqual(kwargs["selected_id"], stored.id)
        self.assertIn(stored, args[0])
        owner._review_library_profile.assert_called_once_with(page, persisted, builtin=False)

    def test_profile_save_failure_or_cancel_never_starts_review(self) -> None:
        for terminal in ("failed", "cancelled"):
            with self.subTest(terminal=terminal):
                adapter = Adapter()
                page = Mock(_profile_entries=())
                owner = SimpleNamespace(
                    tr=lambda text: text,
                    _profile_idle=lambda _page: True,
                    _new_utility_operation_adapter=Mock(return_value=adapter),
                    _review_library_profile=Mock(),
                )
                profile = TweakProfile("Copy", "kde", ())
                with patch("core.tasks.tweak_library.ProfileLibrary") as library:
                    if terminal == "failed":
                        library.return_value.add.side_effect = OSError("Read-only directory")
                        TweakProfilesMixin._save_tweak_profile_copy(owner, page, profile, True, False)
                        with self.assertRaisesRegex(OSError, "Read-only"):
                            adapter.operation()
                        adapter.failed.emit("OSError: Read-only directory")
                    else:
                        adapter.operation = lambda: self.fail("A cancelled save must not write the profile")
                        adapter.cancelled.emit()
                    adapter.stopped.emit()
                owner._review_library_profile.assert_not_called()
                page.set_profile_entries.assert_not_called()

    @patch("PyQt6.QtCore.QTimer.singleShot")
    def test_profile_close_after_save_waits_for_successful_persistence(self, single_shot) -> None:
        profile = TweakProfile("Saved on close", "kde", ())
        stored = entry("saved-on-close", profile)
        adapter = Adapter()
        page = Mock(_profile_entries=())
        owner = SimpleNamespace(
            tr=lambda text: text,
            close=Mock(),
            _profile_idle=lambda _page: True,
            _new_utility_operation_adapter=Mock(return_value=adapter),
            _review_library_profile=Mock(),
        )
        with patch("core.tasks.tweak_library.ProfileLibrary") as library:
            library.return_value.add.return_value = stored
            self.assertTrue(TweakProfilesMixin._save_tweak_profile_copy(
                owner, page, profile, False, True, close_after=True
            ))
            single_shot.assert_not_called()
            adapter.complete()
        single_shot.assert_called_once_with(0, owner.close)
        owner._review_library_profile.assert_not_called()

    @patch("PyQt6.QtCore.QTimer.singleShot")
    def test_quit_requested_during_profile_close_save_resumes_quit_after_success(self, single_shot) -> None:
        profile = TweakProfile("Saved before quit", "kde", ())
        stored = entry("saved-before-quit", profile)
        adapter = Adapter()
        page = Mock(_profile_entries=())
        owner = SimpleNamespace(
            tr=lambda text: text,
            close=Mock(),
            quit_app=Mock(),
            _quit_after_profile_save=True,
            _profile_idle=lambda _page: True,
            _new_utility_operation_adapter=Mock(return_value=adapter),
            _review_library_profile=Mock(),
        )
        with patch("core.tasks.tweak_library.ProfileLibrary") as library:
            library.return_value.add.return_value = stored
            self.assertTrue(TweakProfilesMixin._save_tweak_profile_copy(
                owner, page, profile, False, True, close_after=True
            ))
            adapter.complete()
        single_shot.assert_called_once_with(0, owner.quit_app)
        self.assertFalse(owner._quit_after_profile_save)
        owner.close.assert_not_called()

    @patch("ui.tweak_profiles.review_profile")
    def test_cancelled_or_late_profile_review_does_not_open_final_review(self, review_profile) -> None:
        adapter = Adapter()
        page = Mock(profile=object())
        runtime = object()
        owner = SimpleNamespace(
            tr=lambda text: text,
            _profile_idle=lambda _page: True,
            _profile_controller=lambda: SimpleNamespace(orchestrator=SimpleNamespace(runtime=runtime)),
            _new_utility_operation_adapter=Mock(return_value=adapter),
            _review_tweak_profile_import=Mock(),
        )
        source = TweakProfile("Profile", "kde", ())
        TweakProfilesMixin._review_library_profile(owner, page, source)
        adapter.cancelled.emit()
        adapter.stopped.emit()
        owner._review_tweak_profile_import.assert_not_called()

        # An out-of-order late worker response after stop must remain inert.
        adapter.finished.emit(object())
        owner._review_tweak_profile_import.assert_not_called()
        review_profile.assert_not_called()

    def test_rows_disclose_scope_and_profile_results_link_each_real_run(self) -> None:
        page = self.make_page()
        try:
            direct = page._rows["kde-single-click"][0]
            system = page._rows["dnf-parallel-downloads"][0]
            self.assertIn("Applies immediately · This user", direct.description_label.text())
            self.assertIn("Review required · This computer", system.description_label.text())

            opened: list[str] = []
            page.activityRequested.connect(opened.append)
            result = ProfileResult("partially_succeeded", (
                ProfileEntryResult("kde-single-click", "succeeded", "Verified.", "run-one"),
                ProfileEntryResult("kde-double-click-interval", "failed", "Could not verify.", "run-two"),
                ProfileEntryResult("future-setting", "skipped", "Unavailable."),
            ), "One setting failed.")
            page.set_profile_result(result)
            links = page.profile_result_card.findChildren(QPushButton)
            self.assertEqual(len(links), 2)
            for button in links:
                button.click()
            self.assertEqual(opened, ["run-one", "run-two"])
            result_text = " ".join(label.text() for label in page.profile_result_card.findChildren(QLabel))
            self.assertIn(BY_ID["kde-single-click"].title, result_text)
        finally:
            page.close()

    def test_focus_routes_to_the_matching_tweaks_subview(self) -> None:
        page = self.make_page()
        try:
            page.set_subview("profiles", load_profiles=False)
            self.assertTrue(page.focus_tweak("kde-single-click"))
            self.assertTrue(page._subview_buttons["settings"].isChecked())
            self.assertTrue(page.focus_task("tune:profile-library"))
            self.assertTrue(page._subview_buttons["profiles"].isChecked())
        finally:
            page.close()

    def test_application_review_shows_exact_scope_before_authorizing(self) -> None:
        items = (
            SimpleNamespace(
                title="Firefox",
                parameters=MappingProxyType({"source": "flatpak", "package_id": "org.mozilla.firefox"}),
                metadata=MappingProxyType({"source_label": "Flathub"}),
            ),
            SimpleNamespace(
                title="Neovim",
                parameters=MappingProxyType({"source": "fedora", "package_id": "neovim"}),
                metadata=MappingProxyType({"source_label": "Fedora"}),
            ),
        )
        bundle = SimpleNamespace(
            title="Install selected applications",
            description="Review the exact applications.",
            metadata=MappingProxyType({"variant": "traditional"}),
            items=items,
        )
        selection = SimpleNamespace(bundle=bundle)
        owner = SimpleNamespace(
            tr=lambda text: text,
            _utility_operation_adapter=None,
            _set_utility_notice=Mock(),
            _start_utility_bundle=Mock(return_value=True),
        )
        page = object()
        with patch("ui.confirm_dialog.ReviewedActionDialog") as dialog_type:
            dialog_type.return_value.exec.return_value = QDialog.DialogCode.Rejected
            self.assertFalse(MainWindowUtilityMixin._review_utility_bundle(owner, page, selection))
            args = dialog_type.call_args.args
            scope = args[2]
            self.assertIn("Firefox", scope)
            self.assertIn("Source: Flathub", scope)
            self.assertIn("Package identifier: org.mozilla.firefox", scope)
            self.assertIn("System Flatpak installation", scope)
            self.assertIn("Source: Fedora", scope)
            self.assertIn("Package identifier: neovim", scope)
            self.assertIn("System package installation via DNF5", scope)
            owner._start_utility_bundle.assert_not_called()

            dialog_type.return_value.exec.return_value = QDialog.DialogCode.Accepted
            self.assertTrue(MainWindowUtilityMixin._review_utility_bundle(owner, page, selection))
            owner._start_utility_bundle.assert_called_once_with(page, selection)
