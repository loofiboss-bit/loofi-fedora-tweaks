"""Partial local discovery must preserve usable choices and source identity."""
import io
import subprocess
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from core.catalog_models import FedoraVariant
from core.tasks.applications import ApplicationCatalog, ApplicationContext
from services.software.application_discovery import ApplicationDiscoveryCatalog, ApplicationDiscoveryService, MetadataSource
from test_application_discovery import XML


class ApplicationDiscoveryFailureTests(unittest.TestCase):
    @patch("builtins.open")
    def test_missing_or_malformed_metadata_is_unknown_with_issue(self, opener):
        for failure in (FileNotFoundError("private missing path"), io.BytesIO(b"<components><component>")):
            with self.subTest(failure=type(failure).__name__):
                if isinstance(failure, Exception):
                    opener.side_effect = failure
                else:
                    opener.side_effect = None
                    opener.return_value = failure
                snapshot = ApplicationDiscoveryService([MetadataSource(Path("broken.xml"), "flatpak", "flathub", "user")]).snapshot()
                self.assertEqual(snapshot.status, "missing")
                self.assertEqual(snapshot.records, ())
                self.assertEqual(snapshot.issues, ("Could not read broken.xml.",))
                self.assertEqual(snapshot.metadata_updated_at, "")
                self.assertTrue(snapshot.checked_at)

    @patch("pathlib.Path.stat", return_value=SimpleNamespace(st_mtime=1000))
    @patch("builtins.open")
    def test_valid_source_survives_a_later_malformed_source(self, opener, _stat):
        opener.side_effect = lambda path, *_args: io.BytesIO(XML if path.name == "good.xml" else b"<malformed")
        snapshot = ApplicationDiscoveryService([
            MetadataSource(Path("good.xml"), "flatpak", "trusted", "user"),
            MetadataSource(Path("bad.xml"), "flatpak", "broken", "system"),
        ]).snapshot()
        self.assertEqual(snapshot.status, "partial")
        self.assertEqual(len(snapshot.records), 1)
        self.assertEqual(snapshot.records[0].metadata["remote"], "trusted")
        self.assertEqual(snapshot.issues, ("Could not read bad.xml.",))
        self.assertTrue(snapshot.metadata_updated_at)

    @patch("services.software.application_discovery.MAX_XML_BYTES", 8)
    @patch("builtins.open")
    def test_oversized_xml_is_rejected_after_a_bounded_read(self, opener):
        stream = Mock()
        stream.read.return_value = b"x" * 9
        opener.return_value.__enter__.return_value = stream
        snapshot = ApplicationDiscoveryService([MetadataSource(Path("large.xml"), "flatpak", "flathub", "user")]).snapshot()
        stream.read.assert_called_once_with(9)
        self.assertEqual(snapshot.status, "missing")
        self.assertEqual(snapshot.issues, ("Could not read large.xml.",))

    @patch("services.software.application_discovery.MAX_COMPONENTS", 1)
    @patch("pathlib.Path.stat", return_value=SimpleNamespace(st_mtime=1000))
    @patch("builtins.open")
    def test_component_bound_retains_first_choice_and_marks_partial(self, opener, _stat):
        first_component = XML.split(b"<component ", 1)[1].split(b"</components>", 1)[0]
        second_component = first_component.replace(b"org.example.Editor", b"org.example.Viewer")
        xml = b"<components><component " + first_component + b"<component " + second_component + b"</components>"
        opener.side_effect = lambda *_args: io.BytesIO(xml)
        snapshot = ApplicationDiscoveryService([MetadataSource(Path("bounded.xml"), "flatpak", "flathub", "user")]).snapshot()
        self.assertEqual(snapshot.status, "partial")
        self.assertEqual(len(snapshot.records), 1)
        self.assertEqual(snapshot.records[0].package_id, "org.example.Editor")
        self.assertEqual(snapshot.issues, ("The component limit was reached for bounded.xml.",))

    @patch("services.software.application_discovery.gzip.open")
    def test_truncated_gzip_is_reported_without_losing_control(self, opener):
        opener.return_value.__enter__.return_value.read.side_effect = EOFError("compressed file ended prematurely")
        snapshot = ApplicationDiscoveryService([MetadataSource(Path("truncated.xml.gz"), "flatpak", "flathub", "user")]).snapshot()
        self.assertEqual(snapshot.status, "missing")
        self.assertEqual(snapshot.issues, ("Could not read truncated.xml.gz.",))

    @patch("services.software.application_discovery.SystemManager.get_package_manager", return_value="dnf5")
    @patch("services.software.application_discovery.SystemManager.is_atomic", return_value=False)
    @patch("pathlib.Path.stat", return_value=SimpleNamespace(st_mtime=1000))
    @patch("builtins.open")
    def test_failed_or_timed_out_rpm_cache_keeps_flatpak_choices(self, opener, _stat, _atomic, _manager):
        opener.side_effect = lambda *_args: io.BytesIO(XML)
        for failure in (SimpleNamespace(returncode=1, stdout="private backend error"), subprocess.TimeoutExpired("dnf5", 20)):
            for with_flatpak in (True, False):
                with self.subTest(failure=type(failure).__name__, with_flatpak=with_flatpak):
                    runner = Mock()
                    if isinstance(failure, Exception):
                        runner.side_effect = failure
                    else:
                        runner.return_value = failure
                    sources = [MetadataSource(Path("rpm.xml"), "fedora")]
                    if with_flatpak:
                        sources.append(MetadataSource(Path("flatpak.xml"), "flatpak", "flathub", "user"))
                    snapshot = ApplicationDiscoveryService(sources, runner=runner).snapshot()
                    self.assertEqual(snapshot.status, "partial" if with_flatpak else "missing")
                    self.assertEqual(len(snapshot.records), 1 if with_flatpak else 0)
                    self.assertEqual(snapshot.issues, ("RPM metadata could not be matched to the local DNF5 cache.",))
                    if with_flatpak:
                        self.assertEqual(snapshot.records[0].source, "flatpak")
                    self.assertIn("--cacheonly", runner.call_args.args[0])
                    self.assertEqual(runner.call_args.kwargs["timeout"], 20)

    @patch("services.software.application_discovery.SystemManager.get_package_manager", return_value="dnf5")
    @patch("services.software.application_discovery.SystemManager.is_atomic", return_value=False)
    @patch("pathlib.Path.stat", return_value=SimpleNamespace(st_mtime=1000))
    @patch("builtins.open")
    def test_same_app_keeps_distinct_repo_remote_and_scope_choices(self, opener, _stat, _atomic, _manager):
        opener.side_effect = lambda *_args: io.BytesIO(XML)
        runner = Mock(return_value=SimpleNamespace(returncode=0, stdout=(
            "editor\tfedora\t0:2.0~rc1-1\tx86_64\neditor\tupdates\t0:2.0^snapshot-2\tx86_64\n")))
        sources = [MetadataSource(Path("rpm.xml"), "fedora"),
                   MetadataSource(Path("user.xml"), "flatpak", "flathub", "user"),
                   MetadataSource(Path("system.xml"), "flatpak", "private", "system")]
        snapshot = ApplicationDiscoveryService(sources, runner=runner).snapshot()
        self.assertEqual(snapshot.status, "available")
        self.assertEqual(len(snapshot.records), 4)
        self.assertEqual(len({item.id for item in snapshot.records}), 4)
        catalog = ApplicationDiscoveryCatalog(ApplicationCatalog(), snapshot.records)
        context = ApplicationContext(FedoraVariant.TRADITIONAL, frozenset({"dnf5"}), online=True)
        actual = []
        for record in snapshot.records:
            selection = catalog.build_selection([record.id], context=context)
            self.assertEqual(len(selection.bundle.items), 1)
            item = selection.bundle.items[0]
            self.assertEqual(item.action_id, "install-application")
            actual.append(dict(item.parameters))
        self.assertCountEqual(actual, [
            {"source": "fedora", "package_id": "editor-0:2.0~rc1-1.x86_64", "repo_id": "fedora", "component_id": "org.example.Editor"},
            {"source": "fedora", "package_id": "editor-0:2.0^snapshot-2.x86_64", "repo_id": "updates", "component_id": "org.example.Editor"},
            {"source": "flatpak", "package_id": "app/org.example.Editor/x86_64/stable", "installation": "user", "remote": "flathub"},
            {"source": "flatpak", "package_id": "app/org.example.Editor/x86_64/stable", "installation": "system", "remote": "private"},
        ])
        second = ApplicationDiscoveryService(list(reversed(sources)), runner=runner).snapshot()
        self.assertEqual({record.id for record in second.records}, {record.id for record in snapshot.records})

    @patch("services.software.application_discovery.SystemManager.is_atomic", return_value=False)
    @patch("pathlib.Path.home", return_value=Path("/fixture/home"))
    @patch("pathlib.Path.glob", return_value=[])
    def test_configured_missing_cache_retains_refresh_target_and_remote_probe_failure(self, glob, _home, _atomic):
        def run(vector, **_kwargs):
            if "--system" in vector:
                return SimpleNamespace(returncode=0, stdout="flathub\n")
            raise subprocess.TimeoutExpired("flatpak", 20)

        snapshot = ApplicationDiscoveryService(runner=Mock(side_effect=run)).snapshot()
        self.assertEqual(snapshot.status, "missing")
        self.assertEqual(snapshot.records, ())
        self.assertEqual(snapshot.refresh_targets, (("fedora", "", ""), ("flatpak", "system", "flathub")))
        self.assertEqual(snapshot.issues, (
            "Local RPM AppStream catalog is missing. Review installation of appstream-data; refreshing DNF metadata alone cannot supply it.",
            "Local AppStream metadata is missing for system / flathub.",
            "Configured Flatpak remotes could not be read for user.",
        ))
        self.assertTrue(any(call.args == ("*/active/appstream.xml.gz",) for call in glob.call_args_list))
