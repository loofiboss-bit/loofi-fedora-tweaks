"""Local AppStream discovery and exact source-bound install handoff."""
import io
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch
from pathlib import Path

from core.catalog_models import FedoraVariant
from core.tasks.applications import ApplicationCatalog, ApplicationContext
from services.software.application_discovery import ApplicationDiscoveryCatalog, ApplicationDiscoveryService, DiscoverySnapshot, MetadataSource

XML = b'''<components origin="untrusted"><component type="desktop-application"><id>org.example.Editor</id><name>Editor</name><summary>Edit files</summary><pkgname>editor</pkgname><bundle type="flatpak">app/org.example.Editor/x86_64/stable</bundle><releases><release version="2"/></releases></component></components>'''


class TestApplicationDiscovery(unittest.TestCase):
    @patch("pathlib.Path.stat", return_value=SimpleNamespace(st_mtime=1000))
    @patch("builtins.open")
    def test_flatpak_retains_remote_installation_and_ref(self, opener, _stat):
        opener.side_effect = lambda *_a, **_k: io.BytesIO(XML)
        reader = ApplicationDiscoveryService([MetadataSource(Path("index.xml"), "flatpak", "private", "office")])
        snapshot = reader.snapshot()
        self.assertEqual(snapshot.status, "available")
        record = snapshot.records[0]
        catalog = ApplicationDiscoveryCatalog(ApplicationCatalog(), snapshot.records)
        context = ApplicationContext(FedoraVariant.TRADITIONAL, frozenset({"dnf5"}), online=True)
        item = catalog.build_selection([record.id], context=context).bundle.items[0]
        self.assertEqual(dict(item.parameters), {"source": "flatpak", "package_id": "app/org.example.Editor/x86_64/stable", "installation": "office", "remote": "private"})
        self.assertIn("private", item.metadata["source_label"])

    @patch("services.software.application_discovery.SystemManager.get_package_manager", return_value="dnf5")
    @patch("services.software.application_discovery.SystemManager.is_atomic", return_value=False)
    @patch("pathlib.Path.stat", return_value=SimpleNamespace(st_mtime=1000))
    @patch("builtins.open")
    def test_rpm_identity_comes_from_cache_not_appstream_origin(self, opener, _stat, _atomic, _manager):
        opener.side_effect = lambda *_a, **_k: io.BytesIO(XML)
        runner = Mock(return_value=SimpleNamespace(returncode=0, stdout="editor\tfedora\t2-1\tx86_64\n"))
        snapshot = ApplicationDiscoveryService([MetadataSource(Path("index.xml"), "fedora")], runner=runner).snapshot()
        self.assertEqual(snapshot.records[0].metadata["repo_id"], "fedora")
        catalog = ApplicationDiscoveryCatalog(ApplicationCatalog(), snapshot.records)
        selection = catalog.build_selection([snapshot.records[0].id], context=ApplicationContext(FedoraVariant.TRADITIONAL, frozenset({"dnf5"})))
        self.assertEqual(selection.bundle.items[0].parameters["package_id"], "editor-2-1.x86_64")
        self.assertIn("--cacheonly", runner.call_args.args[0])
        self.assertEqual(runner.call_args.kwargs["timeout"], 20)

    @patch("builtins.open")
    def test_entities_are_rejected_and_not_treated_as_empty_search(self, opener):
        opener.side_effect = lambda *_a, **_k: io.BytesIO(b'<!DOCTYPE x [<!ENTITY secret SYSTEM "file:///etc/passwd">]><components/>')
        snapshot = ApplicationDiscoveryService([MetadataSource(Path("index.xml"), "flatpak", "flathub", "user")]).snapshot()
        self.assertEqual(snapshot.status, "missing")
        self.assertTrue(snapshot.issues)

    @patch("builtins.open")
    def test_utf16_external_entities_are_rejected(self, opener):
        opener.side_effect = lambda *_a, **_k: io.BytesIO('<!DOCTYPE x [<!ENTITY secret SYSTEM "file:///etc/passwd">]><components><component>&secret;</component></components>'.encode("utf-16"))
        snapshot = ApplicationDiscoveryService([MetadataSource(Path("index.xml"), "flatpak", "flathub", "user")]).snapshot()
        self.assertEqual(snapshot.status, "missing")
        self.assertTrue(snapshot.issues)

    def test_cancel_does_not_return_success(self):
        snapshot = ApplicationDiscoveryService([]).snapshot(cancelled=lambda: True)
        self.assertEqual(snapshot.status, "cancelled")

    @patch("pathlib.Path.stat", return_value=SimpleNamespace(st_mtime=1000))
    @patch("builtins.open")
    def test_flatpak_installed_state_is_scoped(self, opener, _stat):
        opener.side_effect = lambda *_a, **_k: io.BytesIO(XML)
        snapshot = ApplicationDiscoveryService([MetadataSource(Path("index.xml"), "flatpak", "flathub", "user")]).snapshot()
        record = snapshot.records[0]
        context = ApplicationContext(FedoraVariant.TRADITIONAL, frozenset({"dnf5"}), installed_ids=frozenset({"org.example.Editor"}))
        catalog = ApplicationDiscoveryCatalog(ApplicationCatalog(), snapshot.records, installed_identities=frozenset({("system", record.metadata["ref"])}))
        self.assertTrue(catalog.eligibility(record, context).selectable)


class TestDiscoveryUi(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from PyQt6.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication([])

    def test_refresh_cancel_retains_previous_snapshot_and_metadata_state(self):
        from ui.install_workflow import InstallWorkflowPage
        page = InstallWorkflowPage()
        first = DiscoverySnapshot(checked_at="now", status="missing")
        page._apply_discovery(first)
        page._apply_discovery(DiscoverySnapshot(status="cancelled"))
        self.assertIs(page._discovery_snapshot, first)
        self.assertIn("cancelled", page.discovery_status.text())
        self.assertTrue(page.cleanup())

    def test_discovered_choices_are_reachable_bounded_and_keep_selection_during_search(self):
        from core.tasks.applications import ApplicationRecord
        from ui.install_workflow import InstallWorkflowPage
        records = tuple(ApplicationRecord(
            f"candidate-{index}", f"Editor {index}", "Edit files", "Utilities", "fedora", f"editor{index}", curated=False,
            metadata={"repo_id": "fedora", "version": "2-1", "arch": "x86_64", "component_id": f"org.example.Editor{index}"},
        ) for index in range(150))
        page = InstallWorkflowPage(context=ApplicationContext(FedoraVariant.TRADITIONAL, frozenset({"dnf5"})))
        page._apply_discovery(DiscoverySnapshot(records=records, checked_at="now", status="available"))
        page.discovery_toggle.setChecked(True)
        self.assertLessEqual(page.application_list.count(), 100)
        page.search_input.setText("Editor 149")
        self.assertIn("candidate-149", page._rows)
        page._row_checks["candidate-149"].setChecked(True)
        page.search_input.setText("Firefox")
        self.assertIn("candidate-149", page.selected_application_ids())
        selection = page.review_selection()
        self.assertEqual(selection.bundle.items[0].parameters["package_id"], "editor149-2-1.x86_64")
        self.assertTrue(page.cleanup())

    def test_discovery_is_reachable_without_automatic_remote_fetch(self):
        from ui.install_workflow import InstallWorkflowPage
        service = Mock()
        page = InstallWorkflowPage(discovery_service=service)
        self.assertFalse(page.discovery_toggle.isChecked())
        service.snapshot.assert_not_called()
        self.assertIn("local", page.discovery_refresh.text())
        self.assertTrue(page.cleanup())


class TestExactApplicationReview(unittest.TestCase):
    def _owner(self):
        from ui.application_review import ApplicationReviewMixin
        owner = SimpleNamespace(
            _utility_operation_adapter=None, _set_utility_notice=Mock(),
            _review_health_action=Mock(return_value=True), _utility_bundle_finished=Mock(),
        )
        for name in ("_continue_application_reviews", "_application_item_finished", "_cancel_application_reviews", "_finish_application_reviews"):
            method = getattr(ApplicationReviewMixin, name)
            setattr(owner, name, lambda *args, _method=method: _method(owner, *args))
        return owner

    def _selection(self):
        context = ApplicationContext(FedoraVariant.TRADITIONAL, frozenset({"dnf5"}))
        return ApplicationCatalog().build_selection(["git", "ripgrep"], context=context)

    def test_selected_apps_prepare_each_fresh_review_without_execute_bundle(self):
        from ui.application_review import ApplicationReviewMixin
        owner = self._owner()
        selection = self._selection()
        page = object()
        self.assertTrue(ApplicationReviewMixin._start_utility_bundle(owner, page, selection))
        owner._review_health_action.assert_called_once_with(page, "install-application", {"source": "fedora", "package_id": "git"})
        self.assertEqual(len(owner._application_review_state["remaining"]), 1)
        # Calling continue before completion cannot start the next mutation.
        self.assertFalse(owner._continue_application_reviews(page))
        self.assertEqual(owner._review_health_action.call_count, 1)

    def test_cancel_skips_remaining_without_installing(self):
        from ui.application_review import ApplicationReviewMixin
        owner = self._owner()
        page = object()
        ApplicationReviewMixin._start_utility_bundle(owner, page, self._selection())
        owner._cancel_application_reviews(page)
        outcome = owner._utility_bundle_finished.call_args.args[1]
        self.assertEqual(len(outcome.items), 2)
        self.assertTrue(all(item.skipped for item in outcome.items))
        self.assertIsNone(owner._application_review_state)
        self.assertEqual(owner._review_health_action.call_count, 1)

    def test_ticket_result_preserves_item_identity_and_allows_fresh_next_review(self):
        from ui.application_review import ApplicationReviewMixin
        owner = self._owner()
        page = object()
        ApplicationReviewMixin._start_utility_bundle(owner, page, self._selection())
        ticket = SimpleNamespace(plan=SimpleNamespace(action_id="install-application", parameters={"source": "fedora", "package_id": "git", "normalized": True}))
        outcome = SimpleNamespace(status="succeeded", message="Verified", plan_id="p", run_id="r", correlation_id="c", data={})
        owner._application_item_finished(page, ticket, outcome)
        self.assertTrue(owner._continue_application_reviews(page))
        self.assertEqual(owner._review_health_action.call_count, 2)
        self.assertEqual(owner._review_health_action.call_args.args[2]["package_id"], "ripgrep")


class TestRpmAppstreamAvailability(unittest.TestCase):
    @patch("builtins.open")
    def test_only_safe_real_package_catalog_can_verify_rpm_refresh(self, opener):
        from services.software.application_discovery import rpm_appstream_catalog_available
        for payload in (b"<components/>", b"<not-appstream/>", b"<components>",
                        b'<!DOCTYPE x [<!ENTITY a "x">]><components/>',
                        b'<components><component type="desktop-application"><id>x</id><name>App</name><pkgname>--option</pkgname></component></components>', XML):
            with self.subTest(payload=payload):
                opener.side_effect = lambda *_a, _payload=payload, **_k: io.BytesIO(_payload)
                self.assertEqual(rpm_appstream_catalog_available([Path("catalog.xml")]), payload == XML)
        self.assertFalse(rpm_appstream_catalog_available([]))

    @patch("services.software.application_discovery.SystemManager.is_atomic", return_value=False)
    @patch("services.software.application_discovery.rpm_catalog_paths", return_value=())
    @patch("pathlib.Path.glob")
    @patch("pathlib.Path.stat", return_value=SimpleNamespace(st_mtime=1000))
    @patch("services.software.application_discovery.gzip.open")
    def test_flatpak_results_do_not_conceal_missing_rpm_catalog(self, opener, _stat, glob, _paths, _atomic):
        opener.side_effect = lambda *_a, **_k: io.BytesIO(XML)
        glob.side_effect = lambda pattern: [Path("flatpak.xml.gz")] if pattern == "*/active/appstream.xml.gz" else []
        runner = Mock(return_value=SimpleNamespace(returncode=0, stdout="flathub\n"))
        snapshot = ApplicationDiscoveryService(runner=runner).snapshot()
        self.assertEqual(snapshot.status, "partial")
        self.assertTrue(snapshot.records)
        self.assertTrue(all(record.source == "flatpak" for record in snapshot.records))
        self.assertEqual(len(snapshot.issues), 1)
        self.assertIn("RPM AppStream catalog is missing", snapshot.issues[0])
        self.assertIn(("fedora", "", ""), snapshot.refresh_targets)
