"""Keyboard-accessible setup and searchable profile-library presentation."""
from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtCore import QEventLoop, Qt, QTimer
from PyQt6.QtGui import QFont
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QApplication, QDialog, QFileDialog, QMessageBox, QScrollArea

from core.tasks.setup_configurations import (
    SetupApplication, SetupDocument, SetupComparison, SetupComparisonEntry, serialize_setup,
)
from core.tasks.tweak_library import LibraryEntry
from core.tasks.tweak_profiles import TweakProfile
from core.tasks.tweaks import TWEAKS, TweakState
from services.software.installed_applications import InstalledApplication, InstalledInventory
from ui.tweak_profile_views import ProfileLibraryView
from ui.setup_configurations import SetupConfigurationsPage
from ui.main_window_setup import MainWindowSetupMixin
from ui.operation_worker import OperationControllerQtAdapter


class SetupUiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def make_page(self):
        with patch("ui.setup_configurations.SetupLibrary.list", return_value=()), \
                patch("ui.setup_configurations.SetupProgressStore.list", return_value=()):
            return SetupConfigurationsPage()

    def test_large_text_keeps_controls_in_narrow_view_and_supports_keyboard(self):
        page = self.make_page()
        font = QFont(page.font())
        font.setPointSize(18)
        page.setFont(font)
        apps = tuple(InstalledApplication(f"App {index:03d}", f"app-{index:03d}", "fedora", "system", f"app-{index:03d}")
                     for index in range(20))
        page.set_inventory(InstalledInventory(apps), ())
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll.setWidget(page)
        scroll.resize(700, 650)
        scroll.show()
        self.app.processEvents()

        self.assertLessEqual(page.minimumSizeHint().width(), scroll.viewport().width())
        self.assertLessEqual(page.width(), scroll.viewport().width())
        self.assertEqual(scroll.horizontalScrollBar().maximum(), 0)
        self.assertGreater(scroll.verticalScrollBar().maximum(), 0)
        self.assertGreaterEqual(page.app_table.viewport().height(), 100)
        self.assertEqual(page.back_button.accessibleName(), "Return to Overview")
        page.back_button.setFocus()
        QTest.keyClick(page.back_button, Qt.Key.Key_Tab)
        self.app.processEvents()
        self.assertIs(self.app.focusWidget(), page.refresh_button)
        self.assertTrue(page.app_search.accessibleName())
        scroll.verticalScrollBar().setValue(scroll.verticalScrollBar().maximum())
        self.app.processEvents()
        self.assertLessEqual(page.create_button.geometry().bottom() - scroll.verticalScrollBar().value(),
                             scroll.viewport().height())
        scroll.close()

    def test_profile_search_matches_setting_names_and_restores_selection(self):
        work = LibraryEntry("work", TweakProfile("Work", "kde", (("kde-single-click", "false"),)))
        creative = LibraryEntry("creative", TweakProfile("Creative", "kde", (("kde-global-theme", "Breeze"),)))
        view = ProfileLibraryView()
        view.set_entries((work, creative), selected_id="creative", errors=("A profile file could not be read.",))

        self.assertIn("could not be read", view.library_notice.text())
        view.search.setText("open files")
        self.assertEqual(view.entries.count(), 1)
        self.assertEqual(view.selected_entry().id, "work")
        view.search.clear()
        self.assertEqual(view.entries.count(), 2)
        self.assertEqual(view.selected_entry().id, "creative")
        view.close()

    def test_add_to_setup_emits_the_selected_profile(self):
        profile = TweakProfile("Work", "kde", (("kde-single-click", "false"),))
        entry = LibraryEntry("work", profile)
        view = ProfileLibraryView()
        view.set_entries((entry,))
        emitted = []
        view.actionRequested.connect(lambda action, selected: emitted.append((action, selected)))

        view.setup_button.click()

        self.assertEqual(emitted, [("setup", entry)])
        view.close()

    def test_only_explicit_skip_is_persisted_and_it_is_not_success(self):
        class Progress:
            def __init__(self):
                self.updates = []

            def update(self, progress_id, step, status):
                self.updates.append((progress_id, step, status))

            def list(self):
                return ({"id": "run", "setup_id": "setup", "status": "partial", "started_at": 1,
                         "steps": {"app:" + "a" * 24: {"status": "skipped"}}},)

        progress = Progress()
        with patch("ui.setup_configurations.SetupProgressStore", return_value=progress):
            page = SetupConfigurationsPage()
            self.assertTrue(page.record_skipped_steps("run", ("app:" + "a" * 24,), "Skipped by user."))

        self.assertEqual(progress.updates, [("run", "app:" + "a" * 24, "skipped")])
        self.assertIn("Skipped by user", page.status.text())
        self.assertNotIn("succeeded", page.progress_status.text())
        page.close()

    def test_continuation_signal_carries_setup_and_progress_ids(self):
        page = SetupConfigurationsPage()
        emitted = []
        page.continueSetupRequested.connect(lambda setup_id, progress_id: emitted.append((setup_id, progress_id)))

        page.continueSetupRequested.emit("setup-id", "progress-id")

        self.assertEqual(emitted, [("setup-id", "progress-id")])
        page.close()

    def test_apply_preparation_waits_until_the_scan_adapter_is_released(self):
        class Harness(MainWindowSetupMixin):
            def __init__(self):
                self._utility_operation_adapter = None
                self.prepared_after_release = []

            def tr(self, text):
                return text

            def _setup_idle(self, _page):
                return True

            def _profile_controller(self):
                return object()

            def _new_utility_operation_adapter(self, **_kwargs):
                adapter = OperationControllerQtAdapter()
                self._utility_operation_adapter = adapter
                adapter.stopped.connect(lambda: setattr(self, "_utility_operation_adapter", None))
                return adapter

            def _setup_scan(self, _document, _adapter, _controller, *, discover_apps):
                return ("scan-result", discover_apps)

            def _prepare_setup_reviews(self, _page, _setup_id, _document, scan, *, continuation_progress_id=""):
                self.prepared_after_release.append((scan, self._utility_operation_adapter, continuation_progress_id))

        profile = TweakProfile("Work", "kde", ())
        document = SetupDocument("Work", (), profile)
        page = SetupConfigurationsPage()
        harness = Harness()
        loop = QEventLoop()
        adapter_holder = []

        with patch("core.tasks.setup_configurations.SetupLibrary.get", return_value=document):
            self.assertTrue(harness._apply_setup(page, document.digest, continuation_progress_id="resume-id"))
            adapter_holder.append(harness._utility_operation_adapter)
            adapter_holder[0].stopped.connect(loop.quit)
            QTimer.singleShot(5_000, loop.quit)
            loop.exec()

        self.assertEqual(harness.prepared_after_release, [(('scan-result', True), None, "resume-id")])
        page.close()

    def test_inventory_preserves_checked_apps_and_supported_settings(self):
        page = self.make_page()
        app = InstalledApplication("Firefox", "firefox", "fedora", "system", "firefox")
        tweak = next(item for item in TWEAKS if item.id == "kde-single-click")
        state = TweakState(tweak, "ready", "false", tweak.choices)
        inventory = InstalledInventory((app,))

        page.set_inventory(inventory, (state,))
        page.app_model.item(0, 0).setCheckState(Qt.CheckState.Checked)
        page.settings_model.item(0, 0).setCheckState(Qt.CheckState.Checked)
        page.set_inventory(inventory, (state,))

        self.assertEqual(page.selected_applications()[0].app_id, "firefox")
        self.assertEqual(page.selected_setting_ids(), ("kde-single-click",))
        page.close()

    def test_create_saves_only_checked_data_and_pending_profile(self):
        page = self.make_page()
        app = InstalledApplication("Firefox", "firefox", "fedora", "system", "firefox")
        tweak = next(item for item in TWEAKS if item.id == "kde-single-click")
        state = TweakState(tweak, "ready", "false", tweak.choices)
        page.set_inventory(InstalledInventory((app,)), (state,))
        page.app_model.item(0, 0).setCheckState(Qt.CheckState.Checked)
        page.settings_model.item(0, 0).setCheckState(Qt.CheckState.Checked)
        page.setup_name.setText("Work")
        emitted = []
        page.importRequested.connect(emitted.append)

        page._create()

        self.assertEqual(emitted[0].name, "Work")
        self.assertEqual(emitted[0].applications[0].app_id, "firefox")
        self.assertEqual(emitted[0].profile.settings, (("kde-single-click", "false"),))

        page.set_pending_profile(TweakProfile("Comfort", "kde", (("kde-single-click", "false"),)))
        page._create()
        self.assertEqual(emitted[-1].name, "Comfort")
        page.close()

    def test_import_preview_and_export_round_trip(self):
        page = self.make_page()
        document = SetupDocument("Work", (SetupApplication("fedora", "firefox", "firefox", name="Firefox"),),
                                 TweakProfile("Work", "kde", (("kde-single-click", "false"),)))
        identifier = document.digest
        page.set_setups(((identifier, document),))
        page.setup_picker.setCurrentIndex(1)

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "work.json"
            with patch.object(QFileDialog, "getSaveFileName", return_value=(str(path), "JSON")):
                page._export_file()
            self.assertEqual(path.read_bytes(), serialize_setup(document))

            imported_path = Path(directory) / "import.json"
            imported_path.write_bytes(serialize_setup(document))
            imported = []
            page.importRequested.connect(imported.append)
            with patch.object(QFileDialog, "getOpenFileName", return_value=(str(imported_path), "JSON")), \
                    patch.object(page, "_show_import_preview", return_value=True):
                page._import_file()
            self.assertEqual(imported, [document])
        page.close()

    def test_import_rejects_future_document_without_touching_library(self):
        page = self.make_page()
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "future.json"
            path.write_text('{"schema":"loofi.setup/v99"}', encoding="utf-8")
            with patch.object(QFileDialog, "getOpenFileName", return_value=(str(path), "JSON")), \
                    patch.object(QMessageBox, "warning") as warning:
                page._import_file()

        warning.assert_called_once()
        page.close()

    def test_read_only_comparison_dialog_and_cancelled_import_preview(self):
        page = self.make_page()
        comparison = SetupComparison("a" * 64, "Work", 1, (
            SetupComparisonEntry("application", "a" * 24, "Firefox", "missing", desired="fedora"),
        ))

        def close_modal():
            for widget in QApplication.topLevelWidgets():
                if isinstance(widget, QDialog) and widget.isVisible():
                    widget.reject()

        QTimer.singleShot(0, close_modal)
        page.show_comparison(comparison)
        QTimer.singleShot(0, close_modal)
        self.assertFalse(page._show_import_preview(SetupDocument("Work", (), TweakProfile("Work", "kde", ()))))
        page.close()


if __name__ == "__main__":
    unittest.main()
