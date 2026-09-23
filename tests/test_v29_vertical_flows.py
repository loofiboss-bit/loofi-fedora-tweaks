"""Contracts for the v29 Install, Tune, Fix, and Update journeys."""

from __future__ import annotations

import os
import sys
import unittest
from types import SimpleNamespace

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "loofi-fedora-tweaks"))

from core.catalog_models import CapabilityState, FedoraVariant  # noqa: E402
from core.tasks import (  # noqa: E402
    ApplicationCatalog,
    ApplicationContext,
    FixCatalog,
    TaskContext,
    TuneCatalog,
    UpdateOverviewState,
    UpdateSourceState,
    build_install_bundle,
    build_tune_bundle,
    update_cta,
)


class TestV29InstallCatalog(unittest.TestCase):
    def test_catalog_is_curated_and_atomic_is_flatpak_first(self) -> None:
        catalog = ApplicationCatalog()
        atomic = ApplicationContext(FedoraVariant.ATOMIC, frozenset({"fedora", "rpm-ostree"}))
        records = catalog.all(context=atomic)
        self.assertEqual(records[0].source, "flatpak")
        self.assertIn("Flatpak", records[0].source_label)
        rpm = catalog.eligibility("git", atomic)
        self.assertEqual(rpm.state, "advanced")
        self.assertTrue(rpm.requires_reboot)

    def test_selection_is_independent_action_bundle_and_fail_closed(self) -> None:
        context = ApplicationContext(FedoraVariant.TRADITIONAL, frozenset({"fedora", "dnf5"}))
        bundle = build_install_bundle(("firefox", "git"), context=context)
        self.assertTrue(bundle.continue_on_error)
        self.assertEqual([item.parameters["source"] for item in bundle.items], ["flatpak", "fedora"])
        unknown = ApplicationContext()
        with self.assertRaises(ValueError):
            build_install_bundle(("firefox",), context=unknown)


class TestV29TuneCatalog(unittest.TestCase):
    def test_atomic_profile_omits_traditional_package_cache(self) -> None:
        catalog = TuneCatalog()
        context = TaskContext(FedoraVariant.ATOMIC, frozenset({"fedora", "rpm-ostree"}))
        selection = catalog.build_selection("tune:recommended", context=context)
        self.assertEqual(selection.task_ids, ("tune:storage-trim",))
        self.assertIn("tune:package-cache", selection.omitted)
        self.assertEqual(selection.bundle.execution_policy, "stop_on_error")

    def test_unknown_context_never_builds_mutation_bundle(self) -> None:
        with self.assertRaises(ValueError):
            build_tune_bundle("tune:minimal", context=TaskContext())


class TestV29FixAndUpdateContracts(unittest.TestCase):
    def test_fix_is_symptom_first_and_has_no_fix_all(self) -> None:
        catalog = FixCatalog()
        self.assertTrue(catalog.search("slow"))
        self.assertNotIn("fix-all", {item.id for item in catalog.symptoms()})
        options = catalog.repair_options(navigation_route="settings:repair")
        self.assertEqual(len(options), 1)
        self.assertEqual(options[0].kind, "navigation")

    def test_update_cta_tracks_freshness_and_reboot(self) -> None:
        state = UpdateOverviewState()
        self.assertEqual(update_cta(state.source("system")).label, "Check")
        available = UpdateSourceState("system", "available", 3, checked_at="now", stale=False)
        self.assertEqual(update_cta(available).label, "Update")
        reboot = UpdateSourceState("system", "awaiting_reboot", 3, stale=False, reboot_required=True)
        self.assertEqual(update_cta(reboot).label, "Continue")
        verifying = UpdateSourceState("flatpak", "verifying", 1, stale=False)
        self.assertEqual(update_cta(verifying).label, "Verify")
        self.assertEqual(state.to_dict()["sources"][0]["source"], "system")


class TestV29VerticalWorkflowWidgets(unittest.TestCase):
    """Smoke the Qt adapters without allowing a widget to execute a mutation."""

    @classmethod
    def setUpClass(cls):
        from PyQt6.QtWidgets import QApplication

        cls.app = QApplication.instance() or QApplication([])

    def _dispose(self, widget):
        widget.close()
        widget.deleteLater()
        self.app.processEvents()

    def test_install_widget_filters_reviews_and_renders_results(self):
        from PyQt6.QtCore import Qt
        from ui.install_workflow import InstallWorkflowPage

        context = ApplicationContext(
            FedoraVariant.TRADITIONAL,
            frozenset({"fedora", "dnf5"}),
            online=True,
        )
        page = InstallWorkflowPage(context=context)
        self.addCleanup(self._dispose, page)
        self.assertGreater(page.application_list.count(), 0)

        page.search_input.setText("video")
        self.app.processEvents()
        self.assertTrue(all("video" in item.text().casefold() or "vlc" in item.text().casefold() or "kdenlive" in item.text().casefold() for item in [page.application_list.item(index) for index in range(page.application_list.count())]))
        page.search_input.clear()
        page.category_filter.setCurrentText("Development")
        self.app.processEvents()
        self.assertTrue(page._rows)
        self.assertTrue(all(record.category == "Development" for record, _eligibility, _item in page._rows.values()))
        self.assertTrue(page.focus_task("install:flatpaks"))
        self.assertTrue(page.focus_task("install:applications"))
        self.assertFalse(page.focus_task("install:missing"))

        page.category_filter.setCurrentIndex(0)
        item = page._rows["firefox"][2]
        item.setCheckState(Qt.CheckState.Checked)
        self.app.processEvents()
        selection = page.review_selection()
        self.assertIsNotNone(selection)
        self.assertEqual(selection.count, 1)
        self.assertIs(page.last_bundle, selection.bundle)

        outcome = SimpleNamespace(
            items=(SimpleNamespace(status="succeeded", action_id="install-application", item_id="firefox", message="Installed"),)
        )
        page.set_results(outcome)
        self.assertFalse(page.results_card.isHidden())
        self.assertEqual(page.results_list.count(), 1)
        page.set_results(SimpleNamespace(items=()))
        self.assertTrue(page.results_card.isHidden())

        page.set_context(None)
        self.assertIsNone(page.review_selection())
        page.set_context(context)
        page._rows["firefox"][2].setCheckState(Qt.CheckState.Checked)
        page.catalog.build_selection = lambda *_args, **_kwargs: (_ for _ in ()).throw(ValueError("invalid review"))
        self.assertIsNone(page.review_selection())

    def test_tune_widget_edits_profile_and_keeps_missing_context_inert(self):
        from PyQt6.QtCore import Qt
        from ui.tune_workflow import TuneWorkflowPage

        context = TaskContext(FedoraVariant.TRADITIONAL, frozenset({"fedora", "dnf5"}))
        page = TuneWorkflowPage(context=context)
        self.addCleanup(self._dispose, page)
        self.assertGreaterEqual(page.profile_selector.count(), 3)
        self.assertGreater(page.operation_list.count(), 0)

        task_id = next(iter(page._rows))
        page._rows[task_id][2].setCheckState(Qt.CheckState.Checked)
        self.app.processEvents()
        selection = page.review_selection()
        self.assertIsNotNone(selection)
        self.assertEqual(selection.task_ids, (task_id,))
        self.assertIs(page.last_selection, selection)

        page.profile_selector.setCurrentIndex(1)
        self.app.processEvents()
        self.assertTrue(page.focus_task("tune"))
        self.assertTrue(page.focus_task("tune:desktop"))
        self.assertFalse(page.focus_task("tune:missing"))
        page.set_results(SimpleNamespace(items=(SimpleNamespace(status="succeeded", action_id="tune-task", message="Verified"),)))
        self.assertEqual(page.results_list.count(), 1)
        page.set_context(None)
        self.assertFalse(page.review_button.isEnabled())
        self.assertIsNone(page.review_selection())
        page.profile_selector.setCurrentIndex(-1)
        self.app.processEvents()
        self.assertIsNone(page.profile)
        page.set_context(TaskContext())
        self.assertFalse(page.review_button.isEnabled())

    def test_update_widget_exposes_one_state_driven_button_per_source(self):
        from ui.update_workflow import UpdateWorkflowPage

        page = UpdateWorkflowPage()
        self.addCleanup(self._dispose, page)
        self.assertEqual(set(page._cards), {"system", "flatpak", "firmware"})
        requests = []
        page.sourceActionRequested.connect(lambda source, action: requests.append((source, action)))
        page.source_button("system").click()
        self.assertEqual(requests[-1], ("system", "check"))

        page.set_source(UpdateSourceState("system", "available", 2, stale=False, message="Two updates"))
        self.assertEqual(page.source_button("system").text(), "Update")
        page.source_button("system").click()
        self.assertEqual(requests[-1], ("system", "update"))

        page.set_source(UpdateSourceState("system", "awaiting_reboot", 2, stale=False, reboot_required=True))
        self.assertEqual(page.source_button("system").text(), "Continue")
        page.set_source(UpdateSourceState("system", "verification_failed", 2, stale=False))
        self.assertEqual(page.source_button("system").text(), "Verify")
        page.set_source(UpdateSourceState("system", "unsupported"))
        self.assertFalse(page.source_button("system").isEnabled())
        before = len(requests)
        page.source_button("system").click()
        self.assertEqual(len(requests), before)
        self.assertEqual(page.source_state("flatpak").source, "flatpak")

    def test_update_widget_projects_checks_outcomes_and_focus(self):
        from ui.update_workflow import UpdateWorkflowPage

        page = UpdateWorkflowPage()
        self.addCleanup(self._dispose, page)
        page.set_notice("info", "Ready", "The source cards are ready.")
        self.assertFalse(page.start_check("unknown"))
        self.assertTrue(page.focus_task("update:overview"))
        self.assertTrue(page.focus_task("firmware"))
        self.assertFalse(page.focus_task("update:unknown"))

        page.apply_outcome("system", SimpleNamespace(status="succeeded", run_id="run-system", message="System updated"))
        self.assertEqual(page.source_state("system").status, "succeeded")
        page.apply_outcome("flatpak", SimpleNamespace(status="awaiting_reboot", run_id="run-flatpak", message="Reboot to continue"))
        self.assertEqual(page.source_state("flatpak").status, "awaiting_reboot")
        page.apply_outcome("firmware", SimpleNamespace(status="verification_failed", run_id="run-fw", message="Verify manually"))
        self.assertEqual(page.source_state("firmware").status, "verification_failed")
        page.apply_outcome("system", SimpleNamespace(status="failed", message="The update failed"))
        self.assertEqual(page.source_state("system").status, "failed")
        page.apply_outcome("unknown", SimpleNamespace(status="succeeded"))
        page.cleanup()

    def test_cancelled_update_marks_only_its_source_stale(self):
        from core.tasks import UpdateSourceState
        from ui.update_workflow import UpdateWorkflowPage

        page = UpdateWorkflowPage()
        self.addCleanup(self._dispose, page)
        system = UpdateSourceState(
            "system",
            "available",
            4,
            checked_at="2026-09-23T10:00:00Z",
            stale=False,
            run_id="system-run-old",
        )
        flatpak = UpdateSourceState("flatpak", "up_to_date", checked_at="2026-09-23T10:01:00Z", stale=False)
        page.set_source(system)
        page.set_source(flatpak)

        page.apply_outcome("system", SimpleNamespace(status="cancelled", message="Stopped before completion."))

        self.assertEqual(page.source_state("system").status, "cancelled")
        self.assertTrue(page.source_state("system").stale)
        self.assertEqual(page.source_state("system").run_id, "system-run-old")
        self.assertEqual(page.source_state("flatpak"), flatpak)

    def test_update_continue_verifies_existing_run_without_rerunning(self):
        from ui.main_window_utility import MainWindowUtilityMixin

        shell = MainWindowUtilityMixin()
        calls = []
        shell._start_utility_update = lambda page, source, action, run_id="": calls.append((page, source, action, run_id))
        page = SimpleNamespace(source_state=lambda _source: SimpleNamespace(run_id="run-after-reboot"))
        shell._handle_update_source_action(page, "system", "continue")
        self.assertEqual(calls, [(page, "system", "verify", "run-after-reboot")])

    def test_fix_widget_uses_the_existing_symptom_surface(self):
        from ui.fix_workflow import FixWorkflowPage

        page = FixWorkflowPage(history=SimpleNamespace(latest=lambda: (None, "")))
        self.addCleanup(self._dispose, page)
        self.assertEqual(page.objectName(), "fixWorkflowPage")
        self.assertEqual(page.profile_selector.count(), 8)
        self.assertEqual(page.next_step_button.text(), "Open safe next step")
        self.assertTrue(page.focus_task("fix:system-slow"))
        self.assertTrue(page.focus_task("fix"))
        self.assertFalse(page.focus_task("fix:missing"))


if __name__ == "__main__":
    unittest.main()
