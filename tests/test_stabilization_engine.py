"""Corruption preservation and structured multi-device firmware evidence."""

import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock

from core.actions import ActionPlan, ActionPlanStore, ActionRun, PolicyDecision
from core.actions.assurance import _preflight_firmware_update, _verify_firmware_update
from core.actions.firmware_evidence import candidates, history_status
from core.executor.action_result import ActionResult


def plan(facts=None):
    return ActionPlan("plan", "update-firmware", {}, "44", "digest", ["fwupdmgr", "update", "-y"],
                      PolicyDecision(True, "ok", "Ready", facts=facts or {}), "high", True,
                      "explicit-no-rollback", "Review firmware history.", False)


def device(identity="system-firmware", version="1.2.3", target="1.2.4", state=None):
    record = {
        "DeviceId": identity,
        "Guid": ["11111111-1111-1111-1111-111111111111", identity + "-guid"],
        "Version": version,
        "Modified": 200,
        "Releases": [{
            "Version": target, "Checksum": ["a" * 64, "b" * 40],
            "Name": "Vendor Firmware", "RemoteId": "lvfs",
        }],
    }
    if state is not None:
        record["UpdateState"] = state
    return record


class TestPlanCorruption(unittest.TestCase):
    def test_invalid_documents_and_records_never_overwrite_original_or_backup(self):
        valid = plan().to_dict()
        invalid_records = [None, {}, {**valid, "parameters": []}, {**valid, "preview": "fwupdmgr"},
                           {**valid, "policy_decision": []}, {**valid, "state_history": [None]},
                           {**valid, "expires_at": float("nan")}, {**valid, "risk_level": "invalid"},
                           {**valid, "finding_context": "invalid"}, {**valid, "plan_id": ""}]
        documents = ["{broken", "[]", '{"schema_version":4}', '{"schema_version":4,"plans":{}}']
        documents += [json.dumps({"schema_version": version, "plans": [valid, item]})
                      for version in (1, 2, 3, 4) for item in invalid_records]
        for content in documents:
            for operation in ("save", "list", "list_read_only"):
                with self.subTest(content=content, operation=operation), tempfile.TemporaryDirectory() as root:
                    path = Path(root) / "plans.json"
                    backup = path.with_suffix(".json.lkg")
                    path.write_text(content)
                    backup.write_bytes(b"previous valid backup")
                    store = ActionPlanStore(path)
                    with self.assertRaises(ValueError):
                        getattr(store, operation)(plan()) if operation == "save" else getattr(store, operation)()
                    self.assertEqual(path.read_bytes(), content.encode())
                    self.assertEqual(backup.read_bytes(), b"previous valid backup")

    def test_missing_store_can_be_created(self):
        with tempfile.TemporaryDirectory() as root:
            store = ActionPlanStore(Path(root) / "plans.json")
            store.save(plan())
            self.assertEqual(store.list()[0].plan_id, "plan")


class TestFirmwareEvidence(unittest.TestCase):
    def setUp(self):
        self.updates = {"Devices": [device(), device("usb-dock", "4.0", "4.1")]}
        self.runtime = Mock()
        self.runtime.boot_id.return_value = "boot-a"
        self.runtime.execute_read_only.return_value = ActionResult.ok("updates", stdout=json.dumps(self.updates))
        self.decision = _preflight_firmware_update({}, self.runtime)
        self.plan = plan(self.decision.facts)
        self.run = ActionRun("run", "plan", "update-firmware", "correlation", execution_boot_id="boot-a", started_at=100)

    def verify(self, history):
        self.runtime.execute_read_only.return_value = ActionResult.ok("history", stdout=json.dumps(history))
        return _verify_firmware_update(self.run, self.plan, self.runtime)

    def test_candidate_uses_target_release_and_guid_list(self):
        self.assertTrue(self.decision.allowed)
        self.assertEqual(self.decision.facts["firmware_evidence_version"], 1)
        record = self.decision.facts["devices"][0]
        self.assertEqual(record["target_version"], "1.2.4")
        self.assertEqual(record["current_version"], "1.2.3")
        self.assertIsInstance(record["guids"], list)
        self.assertEqual(record["checksums"], ["a" * 64, "b" * 40])
        reordered = copy.deepcopy(self.updates)
        reordered["Devices"].reverse()
        reordered["Devices"][0]["Guid"].reverse()
        self.assertEqual(candidates(reordered), self.decision.facts["devices"])

    def test_each_device_must_have_successful_matching_release(self):
        history = copy.deepcopy(self.updates)
        for record in history["Devices"]:
            record["UpdateState"] = 2
        self.assertEqual(self.verify(history).state, "succeeded")
        history["Devices"][1]["UpdateState"] = 3
        self.assertEqual(self.verify(history).state, "failed")

    def test_strings_from_other_devices_cannot_complete_evidence(self):
        history = {"Devices": [device("unrelated", target="1.2.4", state=2)], "message": json.dumps(self.updates)}
        self.assertEqual(self.verify(history).state, "awaiting_reboot")
        self.runtime.boot_id.return_value = "boot-b"
        self.assertEqual(self.verify(history).state, "failed")

    def test_pending_unknown_missing_or_checksum_mismatch_never_succeed(self):
        for state in (0, 1, 4, "pending", "needs-reboot", "unknown", None):
            with self.subTest(state=state):
                history = copy.deepcopy(self.updates)
                for record in history["Devices"]:
                    record["UpdateState"] = state
                self.assertEqual(self.verify(history).state, "awaiting_reboot")
        history = copy.deepcopy(self.updates)
        for record in history["Devices"]:
            record["UpdateState"] = 2
        history["Devices"][0]["Releases"][0]["Checksum"] = ["different"]
        self.assertEqual(self.verify(history).state, "awaiting_reboot")

    def test_newer_failed_attempt_overrides_old_success(self):
        record = self.decision.facts["devices"][0]
        first = device(state=2)
        first["Modified"] = 100
        second = device(state=5)
        second["Modified"] = 200
        self.assertEqual(history_status(record, {"Devices": [first, second]}, started_at=100), "failed")

    def test_old_or_undated_success_cannot_verify_the_current_run(self):
        for modified in (1, 99, None, "invalid", float("nan")):
            with self.subTest(modified=modified):
                history = copy.deepcopy(self.updates)
                for record in history["Devices"]:
                    record["UpdateState"] = 2
                    record["Modified"] = modified
                self.assertEqual(self.verify(history).state, "awaiting_reboot")
                self.runtime.boot_id.return_value = "boot-b"
                self.assertEqual(self.verify(history).state, "failed")
                self.runtime.boot_id.return_value = "boot-a"

    def test_missing_or_unchanged_current_version_blocks_preflight(self):
        for current in (None, "", "1.2.4"):
            with self.subTest(current=current):
                broken = device(version=current)
                self.runtime.execute_read_only.return_value = ActionResult.ok("updates", stdout=json.dumps({"Devices": [broken]}))
                self.assertFalse(_preflight_firmware_update({}, self.runtime).allowed)

    def test_singular_release_and_string_success_are_supported(self):
        history = copy.deepcopy(self.updates)
        for record in history["Devices"]:
            record["Release"] = record.pop("Releases")[0]
            record["UpdateState"] = "success"
        self.assertEqual(self.verify(history).state, "succeeded")

    def test_old_empty_or_invalid_facts_require_new_review(self):
        for facts in ({}, {"devices": [{"guid": "GUID-1", "version": "1.2.4"}]},
                      {"firmware_evidence_version": 1, "devices": []}):
            with self.subTest(facts=facts):
                self.plan = plan(facts)
                result = self.verify(self.updates)
                self.assertEqual(result.state, "failed")
                self.assertTrue(result.data["review_required"])

    def test_incomplete_candidate_blocks_the_entire_update(self):
        for broken in ({"Guid": ["guid"], "Version": "1"}, {"Releases": [{"Version": "2"}]},
                       {"DeviceId": "id", "Releases": [{}]}):
            with self.subTest(broken=broken):
                self.runtime.execute_read_only.return_value = ActionResult.ok("updates", stdout=json.dumps({"Devices": [device(), broken]}))
                self.assertFalse(_preflight_firmware_update({}, self.runtime).allowed)

    def test_query_error_cannot_verify(self):
        self.runtime.execute_read_only.return_value = ActionResult.fail("unavailable")
        self.assertEqual(_verify_firmware_update(self.run, self.plan, self.runtime).state, "failed")
