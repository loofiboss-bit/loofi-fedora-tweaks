"""Complete first-install transaction authority and fail-closed helper modes."""
import unittest
from unittest.mock import Mock, patch

from services.software.flatpak_installation import FlatpakInstallationService, preview_from_facts
from services.software.flatpak_maintenance import validate_helper_args
from services.software.flatpak_updates import update_digest
from services.software import flatpak_maintenance_helper as helper

APP = "app/org.example.App/x86_64/stable"
COMMIT = "a" * 64
SOURCE = "b" * 64


def evidence():
    candidate = {"installation": "user", "ref": APP, "origin": "private", "installed_commit": "", "expected_commit": COMMIT,
                 "name": "Example", "installed_version": "", "available_version": ""}
    operation = {**candidate, "operation": "install", "selected": True}
    return {"available": True, "evidence_version": 1, "installation": "user", "remote": "private", "ref": APP,
            "candidates": [candidate], "operations": [operation], "source_digest": SOURCE,
            "digest": update_digest("user", [candidate], [operation], SOURCE)}


class TestFlatpakInstallation(unittest.TestCase):
    def test_preview_preserves_complete_authority_and_emits_closed_apply_vector(self):
        preview = FlatpakInstallationService(probe=lambda _v: evidence()).preview("user", "private", APP)
        self.assertTrue(preview.available)
        self.assertTrue(preview_from_facts(preview.review_facts()).available)
        self.assertTrue(validate_helper_args(preview.apply_vector()[1:]))
        self.assertIn("private", preview.apply_vector())

    def test_legacy_wrong_installation_and_mutated_dependency_rejected(self):
        self.assertFalse(preview_from_facts({"ref": APP}).available)
        payload = evidence()
        payload["operations"][0]["expected_commit"] = "c" * 64
        self.assertFalse(preview_from_facts(payload).available)
        payload = evidence()
        payload["installation"] = "system"
        self.assertFalse(FlatpakInstallationService(probe=lambda _v: payload).preview("user", "private", APP).available)

    def test_readback_requires_every_origin_and_dependency_commit(self):
        from services.software.flatpak_installation import verify_preview
        preview = preview_from_facts(evidence())

        def state(vector):
            return {"available": True, "installation": "user", "ref": vector[5], "commit": COMMIT, "origin": "private"}
        self.assertEqual(verify_preview(preview, probe=state).state, "succeeded")
        self.assertEqual(verify_preview(preview, probe=lambda vector: {**state(vector), "origin": "changed"}).state, "failed")
        self.assertEqual(verify_preview(preview, probe=lambda vector: {**state(vector), "commit": "c" * 64}).state, "failed")
        self.assertEqual(verify_preview(preview, probe=lambda vector: {**state(vector), "installation": "system"}).state, "failed")

    def test_uninstall_and_option_like_helper_modes_are_rejected(self):
        self.assertFalse(validate_helper_args(["install-preview", "--installation", "user", "--remote", "--evil", "--ref", APP]))
        self.assertFalse(validate_helper_args(["install-preview", "--installation", "user", "--remote", "private", "--ref", "runtime/org.example.Runtime/x86_64/stable"]))
        self.assertFalse(validate_helper_args(["install-apply", "--installation", "user", "--remote", "private", "--ref", APP]))

    @patch("services.software.flatpak_maintenance_helper._update_source_digest", return_value=SOURCE)
    @patch("services.software.flatpak_maintenance_helper.signal.signal")
    def test_preview_aborts_before_auth_apply_requires_same_operations(self, _signal, _source):
        operation = Mock()
        operation.get_operation_type.return_value = "INSTALL"
        operation.get_ref.return_value = APP
        operation.get_remote.return_value = "private"
        operation.get_commit.return_value = COMMIT
        target = Mock()
        target.list_installed_refs.return_value = []
        api, gio = Mock(), Mock()
        api.TransactionOperationType.UPDATE = "UPDATE"
        api.TransactionOperationType.INSTALL = "INSTALL"
        transaction = api.Transaction.new_for_installation.return_value
        callbacks = {}
        transaction.connect.side_effect = lambda name, callback: callbacks.__setitem__(name, callback)
        transaction.get_operations.return_value = [operation]
        transaction.run.side_effect = lambda _c: callbacks["ready-pre-auth"](transaction)
        gio.Cancellable.new.return_value.is_cancelled.return_value = False
        candidate = evidence()["candidates"][0]
        preview = helper.update_transaction(api, gio, target, "user", [candidate], installing=True)
        self.assertTrue(preview["available"])
        self.assertNotIn("success", preview)
        transaction.add_install.assert_called_once_with("private", APP, None)
        transaction.add_update.assert_not_called()
        self.assertFalse(callbacks["add-new-remote"]())
        self.assertFalse(callbacks["end-of-lifed-with-rebase"]())
        callbacks.clear()
        transaction.run.side_effect = lambda _c: callbacks["ready"](transaction)
        operation.get_commit.return_value = "c" * 64
        changed = helper.update_transaction(api, gio, target, "user", [candidate], preview["digest"], installing=True)
        self.assertFalse(changed["success"])

    @patch("services.software.flatpak_maintenance_helper._update_source_digest", return_value=SOURCE)
    @patch("services.software.flatpak_maintenance_helper.signal.signal")
    def test_remove_operation_and_existing_selected_install_fail_closed(self, _signal, _source):
        api, gio, target = Mock(), Mock(), Mock()
        api.TransactionOperationType.UPDATE, api.TransactionOperationType.INSTALL = "UPDATE", "INSTALL"
        transaction = api.Transaction.new_for_installation.return_value
        callbacks = {}
        transaction.connect.side_effect = lambda name, callback: callbacks.__setitem__(name, callback)
        transaction.run.side_effect = lambda _c: callbacks["ready-pre-auth"](transaction)
        gio.Cancellable.new.return_value.is_cancelled.return_value = False
        operation = Mock()
        operation.get_operation_type.return_value = "REMOVE"
        operation.get_ref.return_value = APP
        transaction.get_operations.return_value = [operation]
        target.list_installed_refs.return_value = []
        self.assertFalse(helper.update_transaction(api, gio, target, "user", [evidence()["candidates"][0]], installing=True)["available"])

    @patch("services.software.flatpak_maintenance_helper._update_source_digest", return_value=SOURCE)
    @patch("services.software.flatpak_maintenance_helper.signal.signal")
    def test_dependency_origin_drift_requires_new_review(self, _signal, _source):
        api, gio, target = Mock(), Mock(), Mock()
        api.TransactionOperationType.UPDATE, api.TransactionOperationType.INSTALL = "UPDATE", "INSTALL"
        transaction = api.Transaction.new_for_installation.return_value
        callbacks = {}
        transaction.connect.side_effect = lambda name, callback: callbacks.__setitem__(name, callback)
        transaction.run.side_effect = lambda _c: callbacks["ready-pre-auth"](transaction)
        gio.Cancellable.new.return_value.is_cancelled.return_value = False
        app_operation, dependency_operation, dependency = Mock(), Mock(), Mock()
        dependency_ref = "runtime/org.example.Runtime/x86_64/stable"
        app_operation.get_operation_type.return_value = "INSTALL"
        app_operation.get_ref.return_value = APP
        app_operation.get_remote.return_value = "private"
        app_operation.get_commit.return_value = COMMIT
        dependency_operation.get_operation_type.return_value = "UPDATE"
        dependency_operation.get_ref.return_value = dependency_ref
        dependency_operation.get_remote.return_value = "private"
        dependency_operation.get_commit.return_value = "c" * 64
        dependency.format_ref.return_value = dependency_ref
        dependency.get_commit.return_value = "d" * 64
        dependency.get_origin.return_value = "original"
        dependency.get_appdata_name.return_value = "Runtime"
        dependency.get_appdata_version.return_value = "1"
        target.list_installed_refs.return_value = [dependency]
        transaction.get_operations.return_value = [app_operation, dependency_operation]
        selected = evidence()["candidates"][0]
        preview = helper.update_transaction(api, gio, target, "user", [selected], installing=True)
        self.assertTrue(preview["available"])
        self.assertEqual(next(item for item in preview["operations"] if item["ref"] == dependency_ref)["installed_origin"], "original")
        dependency.get_origin.return_value = "changed"
        callbacks.clear()
        transaction.run.side_effect = lambda _c: callbacks["ready"](transaction)
        result = helper.update_transaction(api, gio, target, "user", [selected], preview["digest"], installing=True)
        self.assertFalse(result["success"])
        self.assertTrue(result["review_required"])
