"""Closed optional setup, source trust and stale-review regression tests."""
from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from core.actions.setup_sources import setup_source_definitions
from core.executor.action_result import ActionResult
from core.fedora_release_policy import FEDORA_RELEASE_POLICY
from core.tasks.guides import GUIDES_BY_ID
from services.software.setup_sources import (
    DEFINITION_VERSION, SOURCES, SetupSourceService, SourcePreview, preview_from_facts, source_digest, validate_helper_args,
)
from services.software import setup_sources_helper as helper
from PyQt6.QtWidgets import QApplication
from ui.software_sources import SoftwareSourcesWidget


def snapshot(source="rpmfusion-free", scope="system", state="absent"):
    evidence = {"source_id": source, "scope": scope, "definition_version": DEFINITION_VERSION, "state": state}
    return SourcePreview(source, scope, True, state, source_digest(evidence), evidence=evidence)


class TestSetupContracts(unittest.TestCase):
    @patch("services.software.installed_applications.InstalledApplicationService._probe")
    def test_source_client_rejects_a_different_source_or_scope(self, probe):
        for returned in (snapshot("flathub", "user"), snapshot("rpmfusion-nonfree", "system")):
            probe.return_value = ActionResult(True, "", 0, stdout=json.dumps(returned.to_dict()))
            actual = SetupSourceService().preview("rpmfusion-free", "system")
            self.assertFalse(actual.available)
            self.assertEqual((actual.source_id, actual.scope), ("rpmfusion-free", "system"))

    def test_source_review_json_round_trip_and_installed_privileged_vector(self):
        reviewed = preview_from_facts(json.loads(json.dumps(snapshot().to_dict())))
        self.assertEqual(reviewed.apply_vector()[0], "/usr/bin/loofi-setup-sources")
        self.assertIn(reviewed.digest, reviewed.apply_vector())

    def test_rejects_changed_trust_and_legacy_source_evidence(self):
        payload = snapshot().to_dict()
        payload["definition"]["key_sha256"] = "0" * 64
        with self.assertRaises(ValueError):
            preview_from_facts(payload)
        with self.assertRaises(ValueError):
            preview_from_facts({})

    def test_rejects_tampered_source_scope_or_snapshot(self):
        for key, value in (("scope", "user"), ("digest", "0" * 64), ("state", "enabled")):
            payload = snapshot().to_dict()
            payload[key] = value
            with self.assertRaises(ValueError):
                preview_from_facts(payload)

    def test_closed_helper_arguments_reject_options_urls_and_unsupported_scopes(self):
        self.assertTrue(validate_helper_args(["preview", "--source-id", "flathub", "--scope", "user"]))
        self.assertTrue(validate_helper_args(snapshot().apply_vector()[1:]))
        self.assertFalse(validate_helper_args(["apply", "--source-id", "https://evil.invalid", "--scope", "system"]))
        self.assertFalse(validate_helper_args(["preview", "--source-id", "rpmfusion-free", "--scope", "user"]))
        self.assertFalse(validate_helper_args([*snapshot().apply_vector()[1:], "--key", "/tmp/key"]))

    def test_no_source_or_scope_is_defaulted_by_action_contracts(self):
        actions = {item.id: item for item in setup_source_definitions()}
        for action_id in ("enable-flathub", "enable-rpm-fusion"):
            self.assertFalse(actions[action_id].parameter_validator({}).allowed)
        self.assertFalse(actions["enable-flathub"].parameter_validator({"scope": "system", "url": "bad"}).allowed)

    def test_setup_guide_backup_cannot_be_verified_as_a_working_backup(self):
        guide = GUIDES_BY_ID["get-fedora-ready"]
        self.assertEqual(len(guide.steps), 6)
        self.assertEqual(guide.steps[0].evidence_kinds, ())
        self.assertEqual(guide.steps[3].evidence_action_ids, ("enable-flathub", "enable-rpm-fusion"))
        self.assertEqual(guide.steps[4].evidence_action_ids, ("install-multimedia-codecs",))

    @patch("core.actions.setup_sources.SetupSourceService")
    def test_codecs_require_a_separately_verified_source(self, service):
        service.return_value.preview.return_value = snapshot(state="absent")
        runtime = Mock()
        runtime.is_atomic.return_value = False
        runtime.package_manager.return_value = "dnf5"
        action = next(item for item in setup_source_definitions() if item.id == "install-multimedia-codecs")
        self.assertEqual(action.preflight_checker({}, runtime).reason_code, "codec_source_required")

    @patch("core.actions.setup_sources.SetupSourceService")
    def test_existing_source_is_honest_noop_not_an_overwrite(self, service):
        service.return_value.preview.return_value = snapshot("flathub", "user", "enabled")
        action = next(item for item in setup_source_definitions() if item.id == "enable-flathub")
        decision = action.preflight_checker({"scope": "user"}, Mock())
        self.assertFalse(decision.allowed)
        self.assertEqual(decision.reason_code, "source_already_enabled")

    @patch("services.software.rpm_transactions.RpmTransactionService")
    @patch("core.actions.setup_sources.SetupSourceService")
    def test_codec_replacements_need_separate_consent_even_for_malformed_solver_result(self, service, transactions):
        service.return_value.preview.return_value = snapshot(state="enabled")
        transactions.return_value.preview.return_value = SimpleNamespace(available=True, operations=({"action": "Remove", "name": "ffmpeg-free"},))
        runtime = Mock()
        runtime.is_atomic.return_value = False
        runtime.package_manager.return_value = "dnf5"
        action = next(item for item in setup_source_definitions() if item.id == "install-multimedia-codecs")
        decision = action.preflight_checker({"removal_consent": False}, runtime)
        self.assertFalse(decision.allowed)
        self.assertEqual(decision.reason_code, "codec_removal_consent_required")

    def test_rpm_source_and_codecs_fail_closed_on_atomic(self):
        runtime = Mock()
        runtime.is_atomic.return_value = True
        for action in setup_source_definitions():
            if action.id == "enable-flathub":
                continue
            parameters = {"source_id": "rpmfusion-free"} if action.id == "enable-rpm-fusion" else {}
            self.assertEqual(action.preflight_checker(parameters, runtime).reason_code, "unsupported_backend")


class TestSetupHelper(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        for name in ("REPO_DIR", "KEY_DIR"):
            patcher = patch.object(helper, name, self.root)
            patcher.start()
            self.addCleanup(patcher.stop)

    @patch.object(helper.Path, "exists", return_value=False)
    @patch.object(helper.Path, "is_symlink", return_value=False)
    @patch.object(helper, "_flatpak_installation")
    def test_preview_never_initializes_a_brand_new_flatpak_installation(self, installation, _symlink, _exists):
        self.assertEqual(helper._flatpak_state("user"), ("absent", {"remotes": []}))
        self.assertEqual(helper._flatpak_state("system"), ("absent", {"remotes": []}))
        installation.assert_not_called()

    @unittest.skipUnless(helper._GLIB_ERRORS, "PyGObject is optional")
    @patch.object(helper, "_flatpak_state")
    def test_optional_glib_errors_are_sanitized(self, flatpak_state):
        flatpak_state.side_effect = helper._GLIB_ERRORS[0]("private repository error")
        observed = helper.inspect_source("flathub", "user")
        self.assertFalse(observed.available)
        self.assertNotIn("private repository", json.dumps(observed.to_dict()))

    @patch.object(helper, "_fingerprints")
    @patch.object(helper, "_fetch")
    def test_key_rotation_is_blocked_before_any_import(self, fetch, fingerprints):
        fetch.return_value = b"unexpected key"
        with self.assertRaises(ValueError):
            helper._key("rpmfusion-free")
        fingerprints.assert_not_called()

    @patch.object(helper, "inspect_source")
    @patch.object(helper, "_key", return_value=b"key")
    @patch.object(helper.os, "geteuid", return_value=1000)
    def test_user_scope_cannot_activate_system_sources(self, _uid, fetch_key, inspect):
        with self.assertRaises(ValueError):
            helper.apply_source("rpmfusion-free", "system", "0" * 64)
        fetch_key.assert_not_called()
        inspect.assert_not_called()

    @patch.object(helper.os, "geteuid", return_value=0)
    def test_root_scope_cannot_change_the_root_users_flatpak_installation(self, _uid):
        with self.assertRaises(ValueError):
            helper.apply_source("flathub", "user", "0" * 64)

    @patch.object(helper, "_flatpak_installation")
    @patch.object(helper, "inspect_source")
    @patch.object(helper, "_key", return_value=b"pinned key")
    @patch.object(helper.os, "geteuid", return_value=1000)
    def test_stale_review_cannot_modify_remote_configuration(self, _uid, _key, inspect, installation):
        with tempfile.TemporaryDirectory() as directory:
            installation.return_value.get_path.return_value.get_path.return_value = directory
            inspect.return_value = snapshot("flathub", "user")
            with self.assertRaises(ValueError):
                helper.apply_source("flathub", "user", "0" * 64)
            installation.return_value.modify_remote.assert_not_called()

    @patch.object(helper, "_fingerprints", return_value=SOURCES["rpmfusion-free"].fingerprints)
    @patch.dict("sys.modules", {"rpm": SimpleNamespace(TransactionSet=Mock(return_value=SimpleNamespace(dbMatch=Mock(return_value=[
        {"version": SOURCES["rpmfusion-free"].fingerprints[0][-8:], "description": "pinned key"},
    ]))))})
    def test_rpm_import_readback_checks_the_full_fingerprint_not_only_the_key_id(self, fingerprints):
        self.assertTrue(helper._rpm_key_imported("rpmfusion-free"))
        fingerprints.assert_called_once_with(b"pinned key")

    @patch.object(helper, "_fingerprints", return_value=("0" * 40,))
    @patch.dict("sys.modules", {"rpm": SimpleNamespace(TransactionSet=Mock(return_value=SimpleNamespace(dbMatch=Mock(return_value=[
        {"version": SOURCES["rpmfusion-free"].fingerprints[0][-8:], "description": "different key"},
    ]))))})
    def test_short_key_id_collision_is_not_accepted(self, _fingerprints):
        self.assertFalse(helper._rpm_key_imported("rpmfusion-free"))

    @patch.object(helper, "_rpm_key_imported", return_value=True)
    @patch.dict(helper.SOURCES, {"rpmfusion-free": replace(SOURCES["rpmfusion-free"], key_sha256=hashlib.sha256(b"trusted").hexdigest())})
    @patch.object(helper.SystemManager, "get_platform_profile", return_value=SimpleNamespace(fedora_version=FEDORA_RELEASE_POLICY.stable_release))
    @patch.object(helper.SystemManager, "get_package_manager", return_value="dnf5")
    @patch.object(helper.SystemManager, "is_atomic", return_value=False)
    def test_existing_trusted_rpmfusion_configuration_is_preserved(self, _atomic, _manager, _profile, _imported):
        key = self.root / "key"
        key.write_bytes(b"trusted")
        config = self.root / "existing.repo"
        template = helper._rpm_configuration("rpmfusion-free")
        template = template.replace(str(helper.KEY_DIR / "RPM-GPG-KEY-loofi-rpmfusion-free"), str(key))
        config.write_text(template)
        original = config.read_bytes()
        state, _facts = helper._rpm_state("rpmfusion-free")
        self.assertEqual(state, "enabled")
        self.assertEqual(config.read_bytes(), original)

    @patch.object(helper, "_rpm_key_imported", return_value=True)
    @patch.dict(helper.SOURCES, {"rpmfusion-free": replace(SOURCES["rpmfusion-free"], key_sha256=hashlib.sha256(b"trusted").hexdigest())})
    @patch.object(helper.SystemManager, "get_platform_profile", return_value=SimpleNamespace(fedora_version=FEDORA_RELEASE_POLICY.stable_release))
    @patch.object(helper.SystemManager, "get_package_manager", return_value="dnf5")
    @patch.object(helper.SystemManager, "is_atomic", return_value=False)
    def test_known_braced_dnf_variables_preserve_equivalent_managed_config(self, _atomic, _manager, _profile, _imported):
        key = self.root / f"release-key-{FEDORA_RELEASE_POLICY.stable_release}"
        key.write_bytes(b"trusted")
        template = helper._rpm_configuration("rpmfusion-free")
        template = template.replace(str(helper.KEY_DIR / "RPM-GPG-KEY-loofi-rpmfusion-free"), str(self.root / "release-key-$releasever"))
        braced = template.replace("$releasever", "${releasever}").replace("$basearch", "${basearch}")
        config = self.root / "managed.repo"
        config.write_text(braced)
        self.assertEqual(helper._rpm_state("rpmfusion-free")[0], "enabled")
        self.assertEqual(config.read_text(), braced)
        config.write_text(braced.replace("${releasever}", "${unknown_release}"))
        self.assertEqual(helper._rpm_state("rpmfusion-free")[0], "conflict")

    def test_atomic_configuration_write_never_overwrites_or_follows_symlinks(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "source.repo"
            helper._exclusive_write(path, b"original")
            with self.assertRaises(FileExistsError):
                helper._exclusive_write(path, b"replacement")
            self.assertEqual(path.read_bytes(), b"original")
            link = Path(directory) / "link.repo"
            link.symlink_to(path)
            with self.assertRaises(FileExistsError):
                helper._exclusive_write(link, b"replacement")
            self.assertEqual(path.read_bytes(), b"original")


class TestOptionalSetupWidget(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.service = Mock()
        self.widget = SoftwareSourcesWidget(service=self.service)
        self.addCleanup(self.widget.deleteLater)

    def test_nothing_is_preselected_and_construction_does_not_probe(self):
        self.assertFalse(self.widget.setup_source.currentData())
        self.assertFalse(self.widget.setup_scope.currentData())
        self.assertFalse(self.widget.codec_consent.isChecked())
        self.assertFalse(self.widget.setup_review.isEnabled())
        self.service.sources_snapshot.assert_not_called()

    def test_changing_sources_requires_fresh_explicit_scope(self):
        self.widget.setup_source.setCurrentIndex(1)
        self.assertFalse(self.widget.setup_scope.currentData())
        self.widget.setup_scope.setCurrentIndex(1)
        self.assertTrue(self.widget.setup_review.isEnabled())
        emitted = Mock()
        self.widget.actionReviewRequested.connect(emitted)
        self.widget.setup_review.click()
        emitted.assert_called_once_with("enable-flathub", {"scope": "user"})
        self.widget.setup_source.setCurrentIndex(2)
        self.assertFalse(self.widget.setup_scope.currentData())
        self.assertFalse(self.widget.setup_review.isEnabled())

    def test_codecs_are_a_separate_review_with_no_default_removal_consent(self):
        emitted = Mock()
        self.widget.actionReviewRequested.connect(emitted)
        self.widget.codec_review.click()
        emitted.assert_called_once_with("install-multimedia-codecs", {"removal_consent": False})

    def test_metadata_download_is_a_separate_explicit_action_before_codecs(self):
        emitted = Mock()
        self.widget.actionReviewRequested.connect(emitted)
        self.widget.metadata_review.click()
        emitted.assert_called_once_with("refresh-application-metadata", {"source": "fedora"})
        self.assertIn("before creating a fresh codec review", self.widget.codec_help.text())


if __name__ == "__main__":
    unittest.main()
