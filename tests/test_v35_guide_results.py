"""Setup completion requires actual results; profile proofs bind every selection."""

import tempfile
import json
from copy import deepcopy
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from core.actions.contracts import ActionRun, VerificationDecision
from core.tasks.guide_profile_results import GuideProfileResultStore
from core.tasks.guides import GUIDES_BY_ID, GuideStepProgress, guide_evidence, guide_step_complete
from core.tasks.tweak_profiles import ProfileEntryResult, ProfileResult, ProfileReview, ProfileReviewEntry
from core.tasks.tweaks import BY_ID


class TestSetupCompletion(unittest.TestCase):
    @patch("core.tasks.guides.guide_evidence_exists", return_value=True)
    def test_legacy_writes_stay_v1_and_profile_reference_requires_v2(self, exists):
        from core.tasks.guides import GuideProgressStore

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "guides.json"
            store = GuideProgressStore(path)
            store.select("get-fedora-ready")
            store.update_step("get-fedora-ready", "get-fedora-ready:backup", "reviewed")
            self.assertEqual(json.loads(path.read_text())["schema_version"], 1)
            store.update_step("get-fedora-ready", "get-fedora-ready:profile", "verified",
                              evidence_kind="profile_result", evidence_id="proof-1")
            raw = json.loads(path.read_text())
            self.assertEqual(raw["schema_version"], 2)
            self.assertTrue(store.read().writable)
            self.assertEqual(store.read().steps["get-fedora-ready:backup"].state, "reviewed")
            raw["schema_version"] = 1
            path.write_text(json.dumps(raw))
            with self.assertRaises(ValueError):
                store.read()

    @patch("core.tasks.guides.guide_evidence_exists", return_value=True)
    def test_setup_review_never_completes_change_steps(self, exists):
        guide = GUIDES_BY_ID["get-fedora-ready"]
        for step in guide.steps:
            with self.subTest(step=step.id):
                self.assertEqual(guide_step_complete(step, GuideStepProgress("reviewed", 1)), step.id.endswith(":backup"))
                self.assertTrue(guide_step_complete(step, GuideStepProgress("skipped", 1)))
                self.assertFalse(guide_step_complete(step, None))
                self.assertFalse(guide_step_complete(step, GuideStepProgress("in_progress", 1)))
        exists.assert_not_called()

    @patch("core.tasks.guides.guide_evidence_exists", return_value=False)
    def test_legacy_review_and_backup_remain_acknowledgements(self, exists):
        step = GUIDES_BY_ID["maintain-your-system"].steps[1]
        self.assertTrue(guide_step_complete(step, GuideStepProgress("reviewed", 1)))
        self.assertFalse(guide_step_complete(step, GuideStepProgress("verified", 1, "action_run", "gone")))

    @patch("core.tasks.guides.guide_evidence_exists", return_value=True)
    def test_exact_compatible_result_required(self, exists):
        step = GUIDES_BY_ID["get-fedora-ready"].steps[2]
        self.assertTrue(guide_step_complete(step, GuideStepProgress("verified", 1, "action_run", "run-1")))
        exists.assert_called_once_with("action_run", "run-1", action_ids=("install-application",))
        self.assertFalse(guide_step_complete(step, GuideStepProgress("verified", 1, "profile_result", "proof")))


class TestProfileProof(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.store = GuideProfileResultStore(Path(self.temp.name) / "results.json")
        self.ids = tuple(tweak_id for tweak_id, tweak in BY_ID.items() if tweak.action_id)[:2]
        self.runs = [ActionRun(run_id=f"run-{index}", plan_id=f"plan-{index}", action_id=BY_ID[tweak_id].action_id,
                               correlation_id="test", state="succeeded", completed_at=10, parameters={"value": "true"},
                               verification_result={"success": True}) for index, tweak_id in enumerate(self.ids)]
        self.review = ProfileReview("Test profile", "kde", tuple(ProfileReviewEntry(tweak_id, "Setting", "false", "true", "ready",
                                                                                  action_id=BY_ID[tweak_id].action_id) for tweak_id in self.ids), 1)
        self.result = ProfileResult("succeeded", tuple(ProfileEntryResult(tweak_id, "succeeded", "verified", run.run_id)
                                                      for tweak_id, run in zip(self.ids, self.runs)), "verified")

    @patch("core.tasks.guide_profile_results.ActionRunStore")
    def test_roundtrip_revalidates_every_exact_run(self, runs):
        runs.return_value.list_read_only.return_value = self.runs
        identifier = self.store.save(self.result, self.review, self.ids)
        self.assertEqual(self.store.available()[0][::2], (identifier, 2))
        self.runs[1].parameters["value"] = "changed"
        self.assertEqual(self.store.available(), ())

    @patch("core.tasks.guide_profile_results.ActionRunStore")
    def test_verified_decision_serialization_and_exact_review_value(self, runs):
        self.runs[0].verification_result = VerificationDecision.succeeded("Independent setting readback").to_result(
            action_id=self.runs[0].action_id).to_dict()
        runs.return_value.list_read_only.return_value = self.runs
        self.store.save(self.result, self.review, self.ids)
        self.assertTrue(self.store.available())
        self.runs[1].parameters = {"value": "false"}
        with self.assertRaises(ValueError):
            self.store.save(self.result, self.review, self.ids)
        self.assertEqual(self.store.available(), ())

    @patch("core.tasks.guide_profile_results.ActionRunStore")
    def test_result_must_cover_exact_original_review_and_selection(self, runs):
        runs.return_value.list_read_only.return_value = self.runs
        for selection in ((self.ids[0],), self.ids * 2, ("unknown",)):
            with self.subTest(selection=selection), self.assertRaises(ValueError):
                self.store.save(self.result, self.review, selection)
        shortened = ProfileResult("succeeded", self.result.entries[:1], "partial aggregate")
        with self.assertRaises(ValueError):
            self.store.save(shortened, self.review, (self.ids[0],))
        runs.assert_not_called()

    @patch("core.tasks.guide_profile_results.ActionRunStore")
    def test_missing_failed_and_wrong_action_cannot_be_proof(self, runs):
        for mode in ("missing", "failed", "wrong", "unverified"):
            with self.subTest(mode=mode):
                values = deepcopy(self.runs)
                if mode == "missing":
                    values.pop()
                elif mode == "failed":
                    values[-1].state = "failed"
                elif mode == "wrong":
                    values[-1].action_id = "install-application"
                else:
                    values[-1].verification_result = {"success": False}
                runs.return_value.list_read_only.return_value = values
                with self.assertRaises(ValueError):
                    self.store.save(self.result, self.review, self.ids)

    @patch("core.tasks.guide_profile_results.ActionRunStore")
    def test_partial_cancelled_empty_and_duplicate_result_rejected(self, runs):
        for status in ("failed", "cancelled", "verification_failed", "blocked"):
            with self.subTest(status=status), self.assertRaises(ValueError):
                self.store.save(ProfileResult(status, self.result.entries, "not complete"), self.review, self.ids)
        for entries in ((), self.result.entries * 2,
                        (ProfileEntryResult(self.ids[0], "not_started", "stopped"),),
                        (ProfileEntryResult(self.ids[0], "skipped", "not selected"),)):
            with self.assertRaises(ValueError):
                self.store.save(ProfileResult("succeeded", entries, "no proof"), self.review, self.ids)
        runs.assert_not_called()

    @patch("core.tasks.guide_profile_results.ActionRunStore")
    def test_skipped_settings_do_not_inflate_selection_and_pruning_invalidates(self, runs):
        runs.return_value.list_read_only.return_value = self.runs
        result = ProfileResult("succeeded", (self.result.entries[0], ProfileEntryResult(self.ids[1], "skipped", "not selected")), "done")
        identifier = self.store.save(result, self.review, (self.ids[0],))
        self.assertEqual(self.store.available()[0][::2], (identifier, 1))
        runs.return_value.list_read_only.return_value = []
        self.assertEqual(self.store.available(), ())

    @patch("core.tasks.guide_profile_results.GuideProfileResultStore.available", return_value=(("proof-id", 10.0, 2),))
    def test_guide_profile_candidates_are_aggregate_references(self, available):
        proof = guide_evidence("profile_result")[0]
        self.assertEqual((proof.kind, proof.id), ("profile_result", "proof-id"))
        self.assertIn("2 verified setting", proof.label)

    @patch("core.tasks.guide_profile_results.GuideProfileResultStore.available", side_effect=ValueError("corrupt"))
    def test_corrupt_aggregate_store_offers_no_result(self, available):
        self.assertEqual(guide_evidence("profile_result"), ())

    @patch("core.tasks.guide_profile_results.ActionRunStore")
    def test_malformed_or_stale_records_are_never_offered(self, runs):
        runs.return_value.list_read_only.return_value = self.runs
        self.store.save(self.result, self.review, self.ids)
        original = json.loads(self.store.path.read_text())
        for override in ({"timestamp": 10 ** 400}, {"timestamp": True}, {"timestamp": -1},
                         {"id": "not-a-uuid"}, {"selected": []}, {"selected": ["not-a-reference"]},
                         {"selected": original["results"][0]["selected"] * 2}):
            with self.subTest(override=override):
                record = {**original["results"][0], **override}
                self.store.path.write_text(json.dumps({**original, "results": [record]}))
                self.assertEqual(self.store.available(), ())

    @patch("core.tasks.guide_profile_results.ActionRunStore")
    def test_unknown_schema_and_oversized_store_are_preserved(self, runs):
        runs.return_value.list_read_only.return_value = self.runs
        for content in ('{"schema_id":"loofi.guide-profile-results","schema_version":99,"results":[]}',
                        '{"schema_id":"loofi.guide-profile-results","schema_version":1,"results":{}}', " " * 65537):
            self.store.path.write_text(content)
            with self.assertRaises(ValueError):
                self.store.save(self.result, self.review, self.ids)
            self.assertEqual(self.store.path.read_text(), content)


class TestSetupGuideUI(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from PyQt6.QtWidgets import QApplication

        cls.app = QApplication.instance() or QApplication([])

    @patch("core.tasks.guides.GuideProgressStore")
    def test_shell_keeps_reviewed_setup_changes_pending(self, store):
        from PyQt6.QtGui import QAction
        from PyQt6.QtWidgets import QToolButton
        from core.tasks.guides import GuideProgressSnapshot
        from ui.main_window_guides import GuideNavigationMixin

        guide = GUIDES_BY_ID["get-fedora-ready"]
        entries = {step.id: GuideStepProgress("reviewed", 20) for step in guide.steps}
        store.return_value.read.return_value = GuideProgressSnapshot(guide.id, guide.steps[0].id, entries, 1)
        owner = SimpleNamespace(tr=lambda text: text, _resume_guide_button=QToolButton(),
                                _continue_guide_action=QAction(), _return_to_guide_action=QAction())
        GuideNavigationMixin._set_active_guide(owner, guide.id)
        self.assertEqual(owner._continue_guide_action.data(), guide.steps[1].id)
        self.assertTrue(owner._continue_guide_action.isEnabled())
        store.return_value.read.side_effect = ValueError("corrupt progress")
        GuideNavigationMixin._set_active_guide(owner, guide.id)
        self.assertEqual(owner._continue_guide_action.text(), "Guide progress unavailable")
        self.assertFalse(owner._continue_guide_action.isEnabled())

    def test_panel_explains_review_is_still_pending(self):
        from core.tasks.guides import GuideProgressStore
        from ui.guide_panel import GuidePanel

        with tempfile.TemporaryDirectory() as directory:
            store = GuideProgressStore(Path(directory) / "guides.json")
            panel = GuidePanel(store=store)
            self.addCleanup(panel.close)
            panel.open_guide("get-fedora-ready")
            panel.step_list.setCurrentRow(1)
            panel._set_step_state("reviewed")
            self.assertIn("verified result required", panel.step_list.item(1).text())
            self.assertEqual(store.read().steps["get-fedora-ready:updates"].state, "reviewed")

    @patch("core.tasks.guide_profile_results.GuideProfileResultStore")
    def test_profile_finish_saves_only_successful_aggregate(self, store):
        from ui.tweak_profiles import TweakProfilesMixin

        owner = SimpleNamespace(tr=lambda text: text, _profile_controller=Mock(),
                                _new_utility_operation_adapter=Mock(return_value=Mock()))
        for status in ("cancelled", "failed", "verification_failed", "succeeded"):
            result = ProfileResult(status, (ProfileEntryResult("gnome-battery", "succeeded", "checked", "run-1"),), "result")
            TweakProfilesMixin._finish_tweak_profile(owner, Mock(), result, Mock(), ("gnome-battery",))
        store.return_value.save.assert_called_once()
        self.assertEqual(store.return_value.save.call_args.args[0].status, "succeeded")

    @patch("core.tasks.guide_profile_results.GuideProfileResultStore")
    def test_unavailable_proof_store_does_not_hide_profile_result(self, store):
        from ui.tweak_profiles import TweakProfilesMixin

        store.return_value.save.side_effect = ValueError("unavailable action history")
        result = ProfileResult("succeeded", (), "No selected changes")
        page = Mock()
        TweakProfilesMixin._finish_tweak_profile(SimpleNamespace(tr=lambda text: text), page, result, Mock(), ())
        page.set_profile_result.assert_called_once_with(result)
        page.set_profile_notice.assert_called_once()


class TestGuideStateCompatibility(unittest.TestCase):
    def setUp(self):
        from core.state.inventory import StateInventory
        from core.state.paths import StatePaths

        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        self.inventory = StateInventory(StatePaths(root / "config", root / "data", root / "cache", root / "run"))
        self.path = self.inventory.get("user_guides").path
        self.path.parent.mkdir(parents=True)
        self.payload = {"schema_id": "loofi.user-guides", "schema_version": 1, "revision": 3,
                        "active_guide": "get-fedora-ready", "active_step": "get-fedora-ready:backup", "steps": {}}

    def test_registered_migration_changes_only_version_and_doctor_preserves_v1(self):
        from core.state.doctor import StateDoctor
        from core.state.migrations import registry_for_inventory

        registry = registry_for_inventory(self.inventory)
        self.assertEqual(registry.migrate("loofi.user-guides", self.payload), {**self.payload, "schema_version": 2})
        self.assertEqual(registry.migrate("loofi.user-guides", self.payload, dry_run=True), self.payload)
        self.path.write_text(json.dumps(self.payload))
        self.path.chmod(0o600)
        before = self.path.read_bytes()
        findings = StateDoctor(self.inventory).run()["findings"]
        self.assertEqual([finding for finding in findings if finding["domain"] == "user_guides"], [])
        self.assertEqual(self.path.read_bytes(), before)

    def test_v1_v2_backups_restore_exact_progress_and_future_version_is_rejected(self):
        from core.state.backup import InvalidStateArchive, StateArchiveService

        service = StateArchiveService(self.inventory)
        archive = Path(self.temp.name) / "guides.zip"
        for version in (1, 2):
            with self.subTest(version=version):
                self.path.write_text(json.dumps({**self.payload, "schema_version": version}))
                before = self.path.read_bytes()
                manifest = service.backup(archive, ["user_guides"])
                self.assertEqual(manifest["entries"][0]["schema_version"], version)
                self.path.write_text(json.dumps({**self.payload, "revision": 4}))
                plan = service.plan_restore(archive)
                service.apply_restore(archive, plan["plan_id"])
                self.assertEqual(self.path.read_bytes(), before)
        self.path.write_text(json.dumps({**self.payload, "schema_version": 99}))
        service.backup(archive, ["user_guides"])
        with self.assertRaises(InvalidStateArchive):
            service.plan_restore(archive)

    @patch("core.state.paths.StatePaths.from_environment")
    def test_v2_guide_backup_restores_aggregate_and_exact_action_evidence(self, paths):
        from core.actions.stores import ActionRunStore
        from core.state.backup import StateArchiveService
        from core.state.doctor import StateDoctor
        from core.tasks.guides import GuideProgressStore, guide_evidence_exists

        paths.return_value = self.inventory.paths
        domain = self.inventory.get("guide_profile_results")
        self.assertEqual((domain.owner, domain.schema_id, domain.schema_version, domain.sensitivity),
                         ("guides", "loofi.guide-profile-results", 1, "private"))
        tweak_id = "gnome-mouse-left-handed"
        action_id = BY_ID[tweak_id].action_id
        run = ActionRun("profile-run-1", "profile-plan-1", action_id, "guide-proof", parameters={"value": "true"},
                        state="succeeded", completed_at=10, verification_result=VerificationDecision.succeeded(
                            "Independent readback").to_result(action_id=action_id).to_dict())
        run_store = ActionRunStore()
        run_store.save(run)
        review = ProfileReview("Selected settings", "gnome", (ProfileReviewEntry(tweak_id, "Setting", "false", "true", "ready",
                                                                               action_id=action_id),), 1)
        result = ProfileResult("succeeded", (ProfileEntryResult(tweak_id, "succeeded", "Verified", run.run_id),), "Verified")
        proof_store = GuideProfileResultStore()
        proof_id = proof_store.save(result, review, (tweak_id,))
        guide_store = GuideProgressStore()
        guide_store.update_step("get-fedora-ready", "get-fedora-ready:profile", "verified",
                                evidence_kind="profile_result", evidence_id=proof_id)
        self.assertTrue(guide_evidence_exists("profile_result", proof_id))
        proof_payload = json.loads(proof_store.path.read_text())
        self.assertEqual((proof_payload["schema_id"], proof_payload["schema_version"]), (domain.schema_id, domain.schema_version))
        findings = StateDoctor(self.inventory).run()["findings"]
        self.assertEqual([finding for finding in findings if finding["domain"] in {"user_guides", "guide_profile_results"}], [])
        service = StateArchiveService(self.inventory)
        archive = Path(self.temp.name) / "guide-proof.zip"
        domains = ["user_guides", "guide_profile_results", "action_runs"]
        manifest = service.backup(archive, domains)
        self.assertEqual({entry["domain"] for entry in manifest["entries"]}, set(domains))
        before = {identifier: self.inventory.get(identifier).path.read_bytes() for identifier in domains}
        for identifier in domains:
            self.inventory.get(identifier).path.unlink()
        self.assertFalse(guide_evidence_exists("profile_result", proof_id))
        plan = service.plan_restore(archive)
        service.apply_restore(archive, plan["plan_id"])
        for identifier in domains:
            self.assertEqual(self.inventory.get(identifier).path.read_bytes(), before[identifier])
        self.assertTrue(guide_evidence_exists("profile_result", proof_id))
        step = GUIDES_BY_ID["get-fedora-ready"].steps[-1]
        self.assertTrue(guide_step_complete(step, guide_store.read().steps[step.id]))
        run_store.path.unlink()
        self.assertFalse(guide_evidence_exists("profile_result", proof_id))
