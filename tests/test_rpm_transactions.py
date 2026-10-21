"""Exact RPM review, drift protection and independent inventory readback."""
import json
import unittest
from dataclasses import replace
from unittest.mock import Mock, patch

from core.actions.contracts import PolicyDecision
from core.executor.action_result import ActionResult
from core.executor.command_policy import CommandValidationError, validate_command
from services.software.rpm_transactions import (
    CODEC_PACKAGES, HELPER, RpmTransactionPreview, RpmTransactionService, evidence_digest,
    parse_args, preview_from_facts, request_args, validate_helper_args, verify_preview,
)
from services.software.rpm_transaction_helper import main, validate_operations


def operation(name="fixture", action="Install", version="1"):
    return {"action": action, "name": name, "nevra": f"{name}-0:{version}-1.noarch", "repo_id": "fixture" if action == "Install" else "@System", "checksum": "a" * 64 if action == "Install" else ""}


def preview(**changes):
    result = replace(RpmTransactionPreview(True, "", packages=("fixture",), operations=(operation(),),
                                           installed=("unrelated-0:1-1.noarch",), repository_digest="c" * 64), **changes)
    return replace(result, digest=evidence_digest(result.to_dict()))


class RpmReviewTests(unittest.TestCase):
    def test_request_is_closed_and_roundtrips(self):
        snapshot = preview()
        args = snapshot.apply_vector()[1:]
        self.assertTrue(validate_helper_args(args))
        self.assertEqual(parse_args(args), ("apply", "install", ("fixture",), "", False, snapshot.digest))
        for unsafe in ("--nogpgcheck", "https://example.invalid/a.rpm", "foo*", "$(whoami)", "a/b", "a\n"):
            with self.subTest(unsafe=unsafe), self.assertRaises(ValueError):
                request_args("install", (unsafe,))

    def test_extra_paths_modes_duplicates_and_options_are_rejected(self):
        for args in (["shell"], ["preview", "--operation", "install", "--package", "fixture", "--installroot", "/"],
                     ["apply", "--operation", "install", "--package", "fixture"],
                     ["preview", "--operation", "remove", "--package", "fixture", "--package", "fixture"]):
            self.assertFalse(validate_helper_args(args))

    def test_codec_recipe_and_separate_consent_are_closed(self):
        self.assertTrue(validate_helper_args(["preview", *request_args("codecs", CODEC_PACKAGES, allow_replacements=True)]))
        with self.assertRaises(ValueError):
            request_args("codecs", ("arbitrary-driver",), allow_replacements=True)
        with self.assertRaises(ValueError):
            request_args("install", ("fixture",), allow_replacements=True)

    def test_persisted_evidence_is_versioned_and_digest_bound(self):
        snapshot = preview()
        self.assertEqual(preview_from_facts(snapshot.to_dict()), snapshot)
        for key, value in (("evidence_version", 2), ("installed", []), ("repo_id", "different"), ("digest", "0" * 64)):
            payload = snapshot.to_dict()
            payload[key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                preview_from_facts(payload)

    def test_no_generic_downgrade_or_unrelated_erase(self):
        for action in ("Downgrade", "Reason Change", "Remove"):
            with self.subTest(action=action), self.assertRaises(ValueError):
                validate_operations("install", ("fixture",), (operation(action=action),), False)
        with self.assertRaises(ValueError):
            validate_operations("install", ("fixture",), (operation(), operation("other", "Replaced")), False)

    def test_protected_components_cannot_be_removed(self):
        for name in ("loofi-fedora-tweaks", "dnf5", "plasma-workspace", "polkit", "kernel-core", "shim-x64"):
            with self.subTest(name=name), self.assertRaises(ValueError):
                validate_operations("remove", (name,), (operation(name, "Remove"),), False)

    def test_reviewed_same_architecture_upgrades_preserve_protected_components(self):
        old = operation("glibc", "Replaced", "1")
        new = operation("glibc", "Upgrade", "2")
        validate_operations("install", ("fixture",), (old, new, operation()), False)
        foreign_arch = {**new, "nevra": new["nevra"].replace("noarch", "x86_64")}
        with self.assertRaises(ValueError):
            validate_operations("install", ("fixture",), (old, foreign_arch, operation()), False)

    def test_existing_codec_upgrade_does_not_require_erasure_consent(self):
        name = "gstreamer1-plugins-bad-freeworld"
        validate_operations("codecs", CODEC_PACKAGES, (operation(name, "Replaced", "1"), operation(name, "Upgrade", "2")), False)

    def test_removal_has_no_incoming_packages(self):
        validate_operations("remove", ("fixture",), (operation(action="Remove"),), False)
        with self.assertRaises(ValueError):
            validate_operations("remove", ("fixture",), (operation(),), False)

    def test_codecs_may_only_replace_frozen_allowlist(self):
        allowed = operation("ffmpeg-free", "Remove")
        validate_operations("codecs", CODEC_PACKAGES, (allowed,), True)
        with self.assertRaises(ValueError):
            validate_operations("codecs", CODEC_PACKAGES, (allowed,), False)
        with self.assertRaises(ValueError):
            validate_operations("codecs", CODEC_PACKAGES, (operation("mesa-va-drivers", "Remove"),), True)

    @patch("services.software.rpm_transactions.helper_command", return_value="/usr/bin/loofi-rpm-transaction")
    def test_runtime_observation_does_not_authorize_execution(self, _helper):
        runtime = Mock()
        runtime.execute_read_only.return_value = ActionResult.ok("preview", stdout=json.dumps(preview().to_dict()))
        observed = RpmTransactionService(runtime).preview("install", ("fixture",))
        self.assertTrue(observed.available)
        self.assertEqual(runtime.execute_read_only.call_args.args[0][1], "preview")

    @patch("services.software.rpm_transactions.helper_command", return_value="/usr/bin/loofi-rpm-transaction")
    def test_unreadable_or_malformed_observations_fail_closed(self, _helper):
        runtime = Mock()
        for result in (ActionResult.fail("timeout"), ActionResult.ok("bad", stdout="{}"), ActionResult.ok("bad", stdout="not json")):
            runtime.execute_read_only.return_value = result
            self.assertFalse(RpmTransactionService(runtime).preview("install", ("fixture",)).available)

    def test_complete_inventory_including_unrelated_packages_is_verified(self):
        runtime = Mock()
        runtime.execute_read_only.return_value = ActionResult.ok("inventory", stdout="unrelated|unrelated-0:1-1.noarch\nfixture|fixture-0:1-1.noarch\ngpg-pubkey|gpg-pubkey-0:12345678-deadbeef.(none)\n")
        self.assertEqual(verify_preview(preview(), runtime).state, "succeeded")
        runtime.execute_read_only.return_value = ActionResult.ok("inventory", stdout="fixture|fixture-0:1-1.noarch\n")
        result = verify_preview(preview(), runtime)
        self.assertEqual(result.state, "failed")
        self.assertEqual(result.data["evidence_status"], "partial")

    def test_unreadable_inventory_is_unknown_not_absent(self):
        runtime = Mock()
        runtime.execute_read_only.return_value = ActionResult.fail("denied")
        result = verify_preview(preview(), runtime)
        self.assertEqual(result.state, "failed")
        self.assertEqual(result.data["evidence_status"], "unknown")

    def test_old_rpm_plan_cannot_render_privileged_command(self):
        from core.actions.assurance import _render_application_evidence
        runtime = Mock()
        runtime.is_atomic.return_value = False
        with self.assertRaises(ValueError):
            _render_application_evidence({"source": "fedora", "package_id": "fixture"}, runtime,
                                         PolicyDecision(True, "old", "old", facts={"target_nevra": "fixture"}), installing=True)

    def test_executor_only_accepts_fixed_installed_apply_helper(self):
        snapshot = preview()
        validate_command(HELPER, snapshot.apply_vector()[1:])
        validate_command("pkexec", snapshot.apply_vector())
        with self.assertRaises(CommandValidationError):
            validate_command("pkexec", ["/tmp/loofi-rpm-transaction", *snapshot.apply_vector()[1:]])

    @patch("services.software.rpm_transaction_helper.signal.alarm")
    @patch("services.software.rpm_transaction_helper.signal.signal")
    @patch("services.software.rpm_transaction_helper.os.geteuid", return_value=0)
    @patch("services.software.rpm_transaction_helper.RpmSession")
    @patch("builtins.print")
    def test_apply_checks_drift_under_lock_before_downloading(self, _print, session_class, _uid, _signal, _alarm):
        session = session_class.return_value
        transaction = Mock()
        session.resolve.return_value = (preview(), transaction)
        args = ["apply", *request_args("install", ("fixture",)), "--snapshot-digest", "0" * 64]
        self.assertEqual(main(args), 1)
        session_class.assert_called_once_with(writable=True)
        transaction.download.assert_not_called()
        transaction.run.assert_not_called()
        session.close.assert_called_once()

    @patch("services.software.rpm_transaction_helper.signal.alarm")
    @patch("services.software.rpm_transaction_helper.signal.signal")
    @patch("services.software.rpm_transaction_helper.os.geteuid", return_value=0)
    @patch("services.software.rpm_transaction_helper.RpmSession")
    @patch("builtins.print")
    def test_unsigned_package_never_runs(self, _print, session_class, _uid, _signal, _alarm):
        session = session_class.return_value
        transaction = Mock()
        transaction.check_gpg_signatures.return_value = False
        session.resolve.return_value = (preview(), transaction)
        self.assertEqual(main(preview().apply_vector()[1:]), 1)
        transaction.download.assert_called_once()
        transaction.run.assert_not_called()
        session.close.assert_called_once()
