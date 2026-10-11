"""Typed, local, read-only guidance and progress contracts."""

from __future__ import annotations

import json
import os
import stat
import tempfile
import threading
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from core.state.inventory import StateInventory
from core.state.paths import StatePaths
from core.tasks.guides import (
    GUIDE_SCHEMA_ID,
    GUIDE_SCHEMA_VERSION,
    GUIDES,
    GUIDES_BY_ID,
    GuideProgressStore,
    GuideTarget,
    UnsupportedFutureGuideSchema,
    guide_evidence,
    guide_progress_payload,
)


class GuideStoreCase(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        root = Path(self.temp.name)
        self.paths = StatePaths(root / "config", root / "data", root / "cache", root / "run")
        self.inventory = StateInventory(self.paths)
        self.path = self.inventory.get("user_guides").path
        self.store = GuideProgressStore(self.path)

    def tearDown(self):
        self.temp.cleanup()


class TestGuideDefinitions(GuideStoreCase):
    def test_four_stable_guide_contracts_have_only_inert_navigation_targets(self):
        self.assertEqual(
            {guide.id for guide in GUIDES},
            {"make-fedora-yours", "choose-and-manage-apps", "maintain-your-system", "solve-a-problem"},
        )
        step_ids = [step.id for guide in GUIDES for step in guide.steps]
        self.assertEqual(len(step_ids), len(set(step_ids)))
        self.assertTrue(all(isinstance(step.target, GuideTarget) for guide in GUIDES for step in guide.steps))
        for guide in GUIDES:
            serialized = guide.to_dict()
            self.assertNotIn("command", json.dumps(serialized).casefold())
            self.assertFalse(any(callable(value) for step in guide.steps for value in step.target.to_dict().values()))

    def test_guide_state_is_registered_at_the_xdg_data_path(self):
        domain = self.inventory.get("user_guides")
        self.assertEqual(domain.path, self.paths.data / "guides.json")
        self.assertEqual((domain.schema_id, domain.schema_version, domain.sensitivity), (GUIDE_SCHEMA_ID, GUIDE_SCHEMA_VERSION, "private"))
        self.assertEqual(self.store.path, domain.path)

    def test_typed_target_rejects_unknown_context_and_unsafe_identifiers(self):
        with self.assertRaises(ValueError):
            GuideTarget("health", context=(("command", "dnf install"),))
        with self.assertRaises(ValueError):
            GuideTarget("health", tweak_id="../../shell")


class TestGuideProgressPersistence(GuideStoreCase):
    def test_progress_distinguishes_reviewed_skipped_and_verified_evidence(self):
        guide = GUIDES_BY_ID["make-fedora-yours"]
        reviewed = guide.steps[0]
        verified = guide.steps[2]
        with patch("core.tasks.guides.guide_evidence_exists", return_value=True):
            self.store.select(guide.id, reviewed.id)
            self.store.update_step(guide.id, reviewed.id, "reviewed")
            self.store.update_step(guide.id, verified.id, "verified", evidence_kind="action_run", evidence_id="run-123")

        snapshot = self.store.read()
        self.assertEqual(snapshot.steps[reviewed.id].state, "reviewed")
        self.assertEqual(snapshot.steps[verified.id].state, "verified")
        self.assertEqual((snapshot.steps[verified.id].evidence_kind, snapshot.steps[verified.id].evidence_id), ("action_run", "run-123"))
        self.assertEqual(json.loads(self.path.read_text())["schema_version"], GUIDE_SCHEMA_VERSION)
        self.assertEqual(stat.S_IMODE(self.path.stat().st_mode), 0o600)
        self.assertEqual(stat.S_IMODE(self.path.parent.stat().st_mode), 0o700)

    def test_clearing_resume_pointer_keeps_step_history(self):
        step = GUIDES_BY_ID["choose-and-manage-apps"].steps[0]
        self.store.select("choose-and-manage-apps", step.id)
        self.store.update_step("choose-and-manage-apps", step.id, "skipped")

        snapshot = self.store.clear_active()

        self.assertEqual((snapshot.active_guide, snapshot.active_step), ("", ""))
        self.assertEqual(snapshot.steps[step.id].state, "skipped")

    def test_concurrent_writes_keep_all_step_updates(self):
        steps = [step for guide in GUIDES for step in guide.steps][:8]
        barrier = threading.Barrier(len(steps))
        errors: list[BaseException] = []

        def update(index: int) -> None:
            step = steps[index]
            guide_id = step.id.split(":", 1)[0]
            try:
                barrier.wait(timeout=3)
                self.store.update_step(guide_id, step.id, "reviewed")
            except BaseException as exc:  # surfaced in the parent assertion
                errors.append(exc)

        threads = [threading.Thread(target=update, args=(index,)) for index in range(len(steps))]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=5)

        self.assertFalse(any(thread.is_alive() for thread in threads))
        self.assertEqual(errors, [])
        snapshot = self.store.read()
        self.assertEqual(snapshot.revision, len(steps))
        self.assertEqual({key for key, value in snapshot.steps.items() if value.state == "reviewed"}, {step.id for step in steps})

    def test_corrupt_or_unknown_step_state_is_not_rewritten(self):
        original = b'{"schema_id":"loofi.user-guides","schema_version":1,"steps":{"future-step":{}}}'
        self.path.parent.mkdir(parents=True)
        self.path.write_bytes(original)

        with self.assertRaises(ValueError):
            self.store.read()
        with self.assertRaises(ValueError):
            self.store.select("make-fedora-yours")
        self.assertEqual(self.path.read_bytes(), original)

    def test_non_finite_timestamp_is_corrupt_and_never_rewritten(self):
        step = GUIDES_BY_ID["make-fedora-yours"].steps[0]
        for timestamp in (float("nan"), float("inf"), float("-inf"), 10**400):
            with self.subTest(timestamp=timestamp):
                self.path.parent.mkdir(parents=True, exist_ok=True)
                original = json.dumps({
                    "schema_id": GUIDE_SCHEMA_ID,
                    "schema_version": GUIDE_SCHEMA_VERSION,
                    "revision": 1,
                    "active_guide": "make-fedora-yours",
                    "active_step": step.id,
                    "steps": {step.id: {"state": "reviewed", "updated_at": timestamp}},
                }).encode()
                self.path.write_bytes(original)

                with self.assertRaises(ValueError):
                    self.store.read()
                with self.assertRaises(ValueError):
                    self.store.select("make-fedora-yours")
                self.assertEqual(self.path.read_bytes(), original)

    def test_future_schema_stays_read_only_and_byte_for_byte_unchanged(self):
        self.path.parent.mkdir(parents=True)
        original = b'{"schema_id":"loofi.user-guides","schema_version":99,"active_guide":"future","future_data":[1,2]}'
        self.path.write_bytes(original)

        snapshot = self.store.read()
        self.assertFalse(snapshot.writable)
        self.assertEqual(snapshot.reason_code, "future-schema-read-only")
        with self.assertRaises(UnsupportedFutureGuideSchema):
            self.store.select("make-fedora-yours")
        self.assertEqual(self.path.read_bytes(), original)

    def test_verified_link_requires_current_exact_evidence_and_missing_history_stays_missing(self):
        step = GUIDES_BY_ID["make-fedora-yours"].steps[2]
        with patch("core.tasks.guides.guide_evidence_exists", return_value=True):
            self.store.update_step("make-fedora-yours", step.id, "verified", evidence_kind="action_run", evidence_id="run-123")
        with patch("core.tasks.guides.guide_evidence_exists", return_value=False):
            payload = guide_progress_payload("make-fedora-yours", self.store.read())
        saved = next(item for item in payload["steps"] if item["id"] == step.id)
        self.assertEqual(saved["status"], "evidence_missing")
        self.assertFalse(saved["evidence_available"])
        with patch("core.tasks.guides.guide_evidence_exists", return_value=False), self.assertRaises(ValueError):
            self.store.update_step("make-fedora-yours", step.id, "verified", evidence_kind="action_run", evidence_id="run-missing")

    def test_unavailable_state_write_does_not_modify_existing_progress(self):
        self.path.parent.mkdir(parents=True)
        self.path.write_text(json.dumps({
            "schema_id": GUIDE_SCHEMA_ID,
            "schema_version": GUIDE_SCHEMA_VERSION,
            "revision": 0,
            "active_guide": "",
            "active_step": "",
            "steps": {},
        }))
        before = self.path.read_bytes()
        with patch("core.tasks.guides.atomic_write_json", side_effect=OSError("disk full")):
            with self.assertRaises(OSError):
                self.store.select("make-fedora-yours")
        self.assertEqual(self.path.read_bytes(), before)


class TestGuideEvidence(unittest.TestCase):
    def test_only_successful_terminal_operations_are_linkable(self):
        succeeded = SimpleNamespace(run_id="run-ok", action_id="install-app", state="succeeded", completed_at=30.0, started_at=20.0)
        failed = SimpleNamespace(run_id="run-failed", action_id="install-app", state="failed", completed_at=40.0, started_at=35.0)
        store = SimpleNamespace(list_read_only=lambda **_kwargs: [succeeded, failed])
        with patch("core.actions.stores.ActionRunStore", return_value=store):
            evidence = guide_evidence("action_run")
        self.assertEqual([item.id for item in evidence], ["run-ok"])

    def test_old_completed_diagnostic_remains_a_historical_result_not_current_health(self):
        old_session = SimpleNamespace(session_id="session-old", profile_id="storage_pressure", state="completed", completed_at=10.0, started_at=5.0)
        snapshot = SimpleNamespace(sessions=(old_session,))
        with patch("core.troubleshooting.storage.TroubleshootingSessionStore") as store:
            store.return_value.read.return_value = snapshot
            evidence = guide_evidence("troubleshooting_session")
        self.assertEqual([item.id for item in evidence], ["session-old"])
        self.assertLess(evidence[0].timestamp, 60.0)


if __name__ == "__main__":
    unittest.main()
