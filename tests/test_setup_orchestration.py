"""Reviewed orchestration for saved setup application batches."""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from PyQt6.QtWidgets import QMessageBox
from core.platform.profile import DeploymentBackend, DesktopEnvironment, PlatformProfile, SessionType
from core.tasks.applications import ApplicationRecord
from core.tasks.setup_configurations import SetupApplication, SetupDocument, SetupProgressStore
from core.tasks.tweak_profiles import TweakProfile
from services.software.application_discovery import DiscoverySnapshot
from services.software.installed_applications import InstalledInventory
from ui.main_window_setup import MainWindowSetupMixin


class _Signal:
    def __init__(self):
        self.values = []

    def emit(self, *values):
        self.values.append(values)


class _Page:
    def __init__(self, store):
        self.store = store
        self.status = ""
        self.progress_id = ""
        self.document_id = ""
        self.bundles = []
        self.routes = _Signal()
        self.routeRequested = self.routes

    def set_inventory(self, _inventory, _states):
        pass

    def show_comparison(self, comparison):
        self.comparison = comparison

    def set_status(self, message):
        self.status = message

    def begin_progress(self, progress_id, document_id, _profile=None):
        self.progress_id = progress_id
        self.document_id = document_id

    def record_skipped_steps(self, progress_id, steps, _message):
        for step in steps:
            self.store.update(progress_id, step, "skipped")
        return True

    def finish_setup_without_apps(self):
        self.finished_without_apps = True


class _Harness(MainWindowSetupMixin):
    def __init__(self):
        self._platform_profile = PlatformProfile(
            "fedora", 44, "workstation", "Workstation", "x86_64", DesktopEnvironment.KDE,
            SessionType.WAYLAND, DeploymentBackend.DNF5, False,
        )

    def tr(self, text):
        return text

    def _profile_controller(self):
        return object()

    def _review_utility_bundle(self, page, selection):
        page.bundles.append(selection)


class SetupOrchestrationTests(unittest.TestCase):
    def test_missing_local_rpm_source_becomes_a_saved_explicit_skip(self):
        app = SetupApplication("fedora", "blueprint-demo", "blueprint-demo", name="Demo")
        document = SetupDocument("Work", (app,), TweakProfile("Work", "kde", ()))
        with tempfile.TemporaryDirectory() as directory:
            store = SetupProgressStore(Path(directory) / "runs.json")
            page = _Page(store)
            with patch("core.tasks.setup_configurations.SetupProgressStore", return_value=store), \
                    patch("PyQt6.QtWidgets.QMessageBox.question", return_value=QMessageBox.StandardButton.Yes):
                _Harness()._prepare_setup_reviews(
                    page, document.digest, document,
                    (InstalledInventory(), (), DiscoverySnapshot(), (), "kde"),
                )

            record = store.list()[0]

        self.assertEqual(record["steps"][f"app:{app.identity}"]["status"], "skipped")
        self.assertEqual(record["status"], "partial")
        self.assertFalse(page.bundles)

    def test_local_rpm_appstream_record_is_bound_to_exact_setup_identity(self):
        app = SetupApplication("fedora", "blueprint-demo", "blueprint-demo", name="Demo")
        document = SetupDocument("Work", (app,), TweakProfile("Work", "kde", ()))
        record = ApplicationRecord(
            id="rpm-discovered-demo", source="fedora", package_id="blueprint-demo", name="Demo",
            description="Demo package", category="Desktop", curated=False,
            metadata={"repo_id": "fedora", "version": "1.0", "arch": "x86_64", "component_id": "org.example.Demo"},
        )
        discovery = DiscoverySnapshot(records=(record,))
        with tempfile.TemporaryDirectory() as directory:
            store = SetupProgressStore(Path(directory) / "runs.json")
            page = _Page(store)
            with patch("core.tasks.setup_configurations.SetupProgressStore", return_value=store), \
                    patch("PyQt6.QtWidgets.QInputDialog.getItem", side_effect=lambda _p, _t, _l, items, *_a: (items[0], True)):
                _Harness()._prepare_setup_reviews(
                    page, document.digest, document,
                    (InstalledInventory(), (), discovery, (), "kde"),
                )

            run = store.list()[0]

        self.assertEqual(len(page.bundles), 1)
        action = page.bundles[0].bundle.items[0]
        self.assertEqual(action.item_id, app.identity)
        self.assertEqual(run["steps"][f"app:{app.identity}"]["status"], "not_started")

    def test_target_mismatch_does_not_continue_the_active_batch(self):
        app = SetupApplication("flatpak", "org.example.App", "app/org.example.App/x86_64/stable", "office")
        document = SetupDocument("Work", (app,), TweakProfile("Work", "kde", ()))
        with tempfile.TemporaryDirectory() as directory:
            store = SetupProgressStore(Path(directory) / "runs.json")
            step = f"app:{app.identity}"
            progress_id = store.start(document.digest, document.digest, (step,),
                                      target_installations={app.identity: "work"})
            store.update(progress_id, step, "not_started")
            page = _Page(store)
            harness = _Harness()
            with patch("core.tasks.setup_configurations.SetupProgressStore", return_value=store):
                harness._prepare_setup_reviews(
                    page, document.digest, document,
                    (InstalledInventory(), (), DiscoverySnapshot(), ("user",), "kde"),
                    continuation_progress_id=progress_id,
                )
            result = store.list()[0]

        self.assertIn("no longer available", page.status)
        self.assertEqual(result["steps"][step]["status"], "not_started")


if __name__ == "__main__":
    unittest.main()
