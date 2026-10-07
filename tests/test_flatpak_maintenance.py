"""Evidence, transaction and command-boundary contracts for runtime cleanup."""
import json
import signal
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from core.actions import flatpak_cleanup
from core.actions.catalog import ActionCatalog
from core.execution_policy import classify_command, execution_allowed
from core.executor.command_policy import CommandValidationError, validate_command_vector
from services.software import flatpak_maintenance_helper as helper
from services.software.flatpak_maintenance import (
    FlatpakMaintenanceService, MAX_OUTPUT, RefRecord, UnusedSnapshot, helper_command,
    snapshot_digest, trusted_helpers, validate_helper_args,
)

RUNTIME = "runtime/org.example.Unused/x86_64/stable"
APP = "app/org.example.App/x86_64/stable"
COMMIT = "a" * 64


def record(ref):
    return {"ref": ref, "commit": COMMIT, "size_bytes": 123}


def snapshot():
    data = {"available": True, "installation": "user", "installed": [record(APP), record(RUNTIME)], "refs": [record(RUNTIME)], "pins": []}
    data["digest"] = snapshot_digest("user", data["installed"], data["refs"], data["pins"])
    return data


def installed_ref(ref):
    item = Mock()
    item.format_ref.return_value = ref
    item.get_commit.return_value = COMMIT
    item.get_installed_size.return_value = 123
    item.get_appdata_name.return_value = "Example"
    item.get_name.return_value = "org.example.App"
    item.get_appdata_version.return_value = "1.0"
    item.get_origin.return_value = "local"
    item.get_eol.return_value = "End of life"
    item.get_eol_rebase.return_value = "org.example.Replacement"
    item.load_metadata.return_value.get_data.return_value = (b"[Application]\nruntime=org.example.Unused/x86_64/stable\n"
                                                           if ref.startswith("app/") else b"[Runtime]\nname=org.example.Unused\n")
    return item


class TestMaintenanceClient(unittest.TestCase):
    def test_snapshot_parsing_and_scope(self):
        service = FlatpakMaintenanceService(probe=lambda _vector: snapshot())
        observed = service.unused()
        self.assertTrue(observed.available)
        self.assertEqual(observed.refs[0].ref, RUNTIME)
        self.assertEqual(observed.to_dict()["digest"], snapshot()["digest"])
        self.assertFalse(service.unused("system").available)
        self.assertIn("shared", service.unused("system").warning)

    def test_malformed_evidence(self):
        cases = [{"available": False}, {**snapshot(), "digest": "wrong"}, {**snapshot(), "refs": [record(APP)]},
                 {**snapshot(), "pins": [None]}, {**snapshot(), "installed": [record(APP), record(APP)]},
                 {**snapshot(), "refs": [{"ref": RUNTIME, "commit": "bad", "size_bytes": 123}]},
                 {**snapshot(), "refs": [{"ref": RUNTIME, "commit": COMMIT, "size_bytes": -1}]},
                 {**snapshot(), "refs": [record("runtime/org.example.Other/x86_64/stable")] }]
        for payload in cases:
            self.assertFalse(FlatpakMaintenanceService(probe=lambda _v: payload).unused().available)
        self.assertFalse(FlatpakMaintenanceService().unused("--bad").available)

    def test_details_and_installations(self):
        service = FlatpakMaintenanceService(probe=lambda _v: {"available": True, "ref": APP, "installation": "user", "version": "2", "runtime_missing": True})
        details = service.details(APP)
        self.assertTrue(details.available)
        self.assertTrue(details.to_dict()["runtime_missing"])
        self.assertEqual(details.version, "2")
        self.assertFalse(service.details("bad").available)
        self.assertFalse(FlatpakMaintenanceService(probe=lambda _v: {}).details(APP).available)
        self.assertEqual(service.installations(), ())
        service = FlatpakMaintenanceService(probe=lambda _v: {"available": True, "installations": ["user", "system", "office"]})
        self.assertEqual(service.installations(), ("user", "system", "office"))

    def test_invalid_details_fail_closed(self):
        base = {"available": True, "ref": APP, "installation": "user"}
        for fields in [{"ref": RUNTIME}, {"size_bytes": -1}, {"size_bytes": True}, {"runtime_missing": "yes"},
                       {"origin": "https://private.example/token"}, {"runtime": "bad"}, {"eol": "a\x00b"}, {"name": None}]:
            self.assertFalse(FlatpakMaintenanceService(probe=lambda _v: {**base, **fields}).details(APP).available)

    def test_optional_support_error_propagates_without_arbitrary_text(self):
        reason = "Local Flatpak support is unavailable. Optional PyGObject and libflatpak are required."
        service = FlatpakMaintenanceService(probe=lambda _v: {"available": False, "error": reason})
        self.assertEqual(service.unused().error, reason)
        self.assertEqual(service.details(APP).error, reason)
        service = FlatpakMaintenanceService(probe=lambda _v: {"available": False, "error": "https://private/token"})
        self.assertNotIn("private", service.unused().error)
        self.assertNotIn("private", service.details(APP).error)

    @patch("services.software.flatpak_maintenance.subprocess.Popen", side_effect=OSError)
    def test_missing_executable(self, _popen):
        self.assertFalse(FlatpakMaintenanceService._probe(["missing"])["available"])

    @patch("services.software.flatpak_maintenance.selectors.DefaultSelector")
    @patch("services.software.flatpak_maintenance.subprocess.Popen")
    def test_bounded_process(self, popen, selectors):
        process = popen.return_value
        process.poll.return_value = 0
        process.returncode = 0
        stream = process.stdout
        stream.read1.side_effect = [json.dumps(snapshot()).encode(), b""]
        selector = selectors.return_value.__enter__.return_value
        selector.get_map.side_effect = [True, True, False]
        selector.select.return_value = [(SimpleNamespace(fileobj=stream), None)]
        self.assertTrue(FlatpakMaintenanceService._probe(["helper"])["available"])
        self.assertTrue(stream.close.called)

    @patch("services.software.flatpak_maintenance.selectors.DefaultSelector")
    @patch("services.software.flatpak_maintenance.subprocess.Popen")
    def test_output_overflow_kills_child(self, popen, selectors):
        process = popen.return_value
        process.poll.return_value = None
        process.stdout.read1.return_value = b"a" * (MAX_OUTPUT + 1)
        selector = selectors.return_value.__enter__.return_value
        selector.get_map.return_value = True
        selector.select.return_value = [(SimpleNamespace(fileobj=process.stdout), None)]
        self.assertFalse(FlatpakMaintenanceService._probe(["helper"])["available"])
        process.kill.assert_called_once()

    @patch("services.software.flatpak_maintenance.selectors.DefaultSelector")
    @patch("services.software.flatpak_maintenance.subprocess.Popen")
    def test_process_preserves_sanitized_missing_gi_error_on_exit_one(self, popen, selectors):
        reason = "Local Flatpak support is unavailable. Optional PyGObject and libflatpak are required."
        process = popen.return_value
        process.returncode = 1
        process.poll.return_value = 1
        process.stdout.read1.side_effect = [json.dumps({"available": False, "error": reason}).encode(), b""]
        selector = selectors.return_value.__enter__.return_value
        selector.get_map.side_effect = [True, True, False]
        selector.select.return_value = [(SimpleNamespace(fileobj=process.stdout), None)]
        self.assertEqual(FlatpakMaintenanceService._probe(["helper"])["error"], reason)


class TestHelper(unittest.TestCase):
    def target(self):
        target = Mock()
        target.list_installed_refs.return_value = [installed_ref(APP), installed_ref(RUNTIME)]
        target.list_unused_refs.return_value = [installed_ref(RUNTIME)]
        target.list_pinned_refs.return_value = []
        return target

    def test_unused_and_pinned_evidence(self):
        target = self.target()
        self.assertEqual(helper.inspect_unused(target, "user"), snapshot())
        target.list_pinned_refs.return_value = [installed_ref(APP)]
        self.assertEqual(helper.inspect_unused(target, "user")["pins"], [APP])
        target.list_unused_refs.return_value = [installed_ref(APP)]
        self.assertRaises(ValueError, helper.inspect_unused, target, "user")

    def test_details_eol_and_missing_runtime(self):
        target = self.target()
        api = Mock()
        api.get_system_installations.return_value = []
        observed = helper.inspect_details(api, target, APP, "user")
        self.assertEqual(observed["origin"], "local")
        self.assertEqual(observed["eol"], "End of life")
        self.assertEqual(observed["runtime_eol"], "End of life")
        self.assertFalse(observed["runtime_missing"])
        target.list_installed_refs.return_value = [installed_ref(APP)]
        self.assertTrue(helper.inspect_details(api, target, APP, "user")["runtime_missing"])
        self.assertFalse(helper.inspect_details(api, target, RUNTIME, "user")["available"])
        item = installed_ref(APP)
        item.load_metadata.return_value.get_data.return_value = b"[Application]\nruntime=bad\n"
        target.list_installed_refs.return_value = [item]
        self.assertRaises(ValueError, helper.inspect_details, Mock(), target, APP, "user")

    def test_user_details_find_public_system_runtime_by_priority(self):
        api, user, high, low = Mock(), self.target(), Mock(), Mock()
        user.list_installed_refs.return_value = [installed_ref(APP)]
        high.get_priority.return_value = 10
        low.get_priority.return_value = 0
        high.list_installed_refs.return_value = [installed_ref(RUNTIME)]
        low.list_installed_refs.return_value = []
        api.get_system_installations.return_value = [low, high]
        result = helper.inspect_details(api, user, APP, "user")
        self.assertFalse(result["runtime_missing"])
        self.assertEqual(result["runtime_eol"], "End of life")
        low.list_installed_refs.assert_not_called()
        high.list_installed_refs.side_effect = RuntimeError("unreadable")
        self.assertRaises(RuntimeError, helper.inspect_details, api, user, APP, "user")

    def test_named_details_find_default_public_runtime(self):
        api, named, system = Mock(), self.target(), Mock()
        named.list_installed_refs.return_value = [installed_ref(APP)]
        named.get_path.return_value.get_path.return_value = "/named"
        system.get_path.return_value.get_path.return_value = "/system"
        system.get_priority.return_value = 10
        system.list_installed_refs.return_value = [installed_ref(RUNTIME)]
        api.get_system_installations.return_value = [named, system]
        result = helper.inspect_details(api, named, APP, "office")
        self.assertFalse(result["runtime_missing"])
        self.assertEqual(result["runtime_eol"], "End of life")
        api.Installation.new_user.assert_not_called()

    def test_installation_identity(self):
        api = Mock()
        helper.installation(api, "user")
        api.Installation.new_user.assert_called_once_with(None)
        helper.installation(api, "system")
        api.Installation.new_system.assert_called_once_with(None)
        helper.installation(api, "office")
        api.Installation.new_system_with_id.assert_called_once_with("office", None)

    def test_drift_rejects_before_transaction(self):
        api, gio = Mock(), Mock()
        result = helper.apply_cleanup(api, gio, self.target(), "user", "b" * 64, [RUNTIME])
        self.assertTrue(result["review_required"])
        api.Transaction.new_for_installation.assert_not_called()

    @patch("services.software.flatpak_maintenance_helper.signal.signal")
    def test_transaction_verifies_selected_refs(self, _signal):
        api, gio, target = Mock(), Mock(), self.target()
        gio.Cancellable.new.return_value.is_cancelled.return_value = False
        transaction = api.Transaction.new_for_installation.return_value
        operation = Mock()
        operation.get_ref.return_value = RUNTIME
        operation.get_operation_type.return_value = api.TransactionOperationType.UNINSTALL
        transaction.get_operations.return_value = [operation]
        callbacks = {}
        transaction.connect.side_effect = lambda name, callback: callbacks.update({name: callback})
        def run(_cancel):
            self.assertTrue(callbacks["ready"](transaction))
            self.assertFalse(callbacks["operation-error"](transaction, operation, None, 0))
            target.list_installed_refs.return_value = [installed_ref(APP)]
            target.list_unused_refs.return_value = []
            return True
        transaction.run.side_effect = run
        result = helper.apply_cleanup(api, gio, target, "user", snapshot()["digest"], [RUNTIME])
        self.assertTrue(result["success"])
        self.assertEqual(result["removed_refs"], [RUNTIME])
        transaction.set_force_uninstall.assert_called_once_with(False)
        transaction.set_disable_related.assert_called_once_with(True)
        transaction.set_disable_dependencies.assert_called_once_with(True)
        transaction.set_disable_prune.assert_called_once_with(True)

    @patch("services.software.flatpak_maintenance_helper.signal.signal")
    def test_unexpected_operation_aborts_ready(self, _signal):
        api, gio, target = Mock(), Mock(), self.target()
        gio.Cancellable.new.return_value.is_cancelled.return_value = False
        transaction = api.Transaction.new_for_installation.return_value
        operation = Mock()
        operation.get_ref.return_value = APP
        transaction.get_operations.return_value = [operation]
        callbacks = {}
        transaction.connect.side_effect = lambda name, callback: callbacks.update({name: callback})
        transaction.run.side_effect = lambda _c: callbacks["ready"](transaction)
        result = helper.apply_cleanup(api, gio, target, "user", snapshot()["digest"], [RUNTIME])
        self.assertFalse(result["success"])
        self.assertTrue(result["review_required"])

    @patch("services.software.flatpak_maintenance_helper.signal.signal")
    def test_failed_transaction_observes_partial_and_cancel(self, mocked_signal):
        api, gio, target = Mock(), Mock(), self.target()
        gio.Cancellable.new.return_value.is_cancelled.return_value = True
        def run(_cancel):
            target.list_installed_refs.return_value = [installed_ref(APP)]
            target.list_unused_refs.return_value = []
            raise RuntimeError("secret remote token")
        api.Transaction.new_for_installation.return_value.run.side_effect = run
        result = helper.apply_cleanup(api, gio, target, "user", snapshot()["digest"], [RUNTIME])
        self.assertFalse(result["success"])
        self.assertTrue(result["cancelled"])
        self.assertEqual(result["removed_refs"], [RUNTIME])
        self.assertNotIn("secret", result["error"])
        handler = mocked_signal.call_args_list[0].args[1]
        handler(signal.SIGTERM, None)
        gio.Cancellable.new.return_value.cancel.assert_called_once()

    @patch("builtins.print")
    @patch("services.software.flatpak_maintenance_helper.load_api", side_effect=ImportError)
    def test_unavailable_api(self, _api, output):
        self.assertEqual(helper.main(["unused", "--installation", "user"]), 1)
        self.assertFalse(json.loads(output.call_args.args[0])["available"])

    @patch("builtins.print")
    @patch("services.software.flatpak_maintenance_helper.os.geteuid", return_value=0)
    def test_root_and_invalid_shape_rejected(self, _uid, _print):
        self.assertEqual(helper.main(["apply", "--installation", "user", "--snapshot-digest", COMMIT, "--ref", RUNTIME]), 2)
        self.assertEqual(helper.main(["anything"]), 2)

    @patch("builtins.print")
    @patch("services.software.flatpak_maintenance_helper.load_api")
    def test_main_inspection_modes(self, api_loader, output):
        api, gio = Mock(), Mock()
        api_loader.return_value = (api, gio)
        api.Installation.new_user.return_value = self.target()
        api.get_system_installations.return_value = [SimpleNamespace(get_id=lambda: "default"), SimpleNamespace(get_id=lambda: "office")]
        self.assertEqual(helper.main(["installations"]), 0)
        self.assertEqual(json.loads(output.call_args.args[0])["installations"], ["user", "system", "office"])
        self.assertEqual(helper.main(["details", "--installation", "user", "--ref", APP]), 0)
        self.assertEqual(helper.main(["unused", "--installation", "user"]), 0)
        api.Installation.new_user.side_effect = RuntimeError("private URL")
        self.assertEqual(helper.main(["unused", "--installation", "user"]), 1)
        self.assertNotIn("private", output.call_args.args[0])

    @patch("builtins.print")
    @patch("services.software.flatpak_maintenance_helper.os.geteuid", return_value=1000)
    @patch("services.software.flatpak_maintenance_helper.apply_cleanup", return_value={"available": True, "success": True})
    @patch("services.software.flatpak_maintenance_helper.load_api")
    def test_main_apply_and_output_limit(self, loader, apply, _uid, output):
        loader.return_value = (Mock(), Mock())
        args = ["apply", "--installation", "user", "--snapshot-digest", COMMIT, "--ref", RUNTIME]
        self.assertEqual(helper.main(args), 0)
        apply.return_value = {"available": True, "success": True, "evidence": "a" * MAX_OUTPUT}
        self.assertEqual(helper.main(args), 1)
        self.assertFalse(json.loads(output.call_args.args[0])["available"])

    @patch("services.software.flatpak_maintenance_helper.signal.signal")
    def test_post_transaction_inspection_failure(self, _signal):
        target = self.target()
        target.list_installed_refs.side_effect = [[installed_ref(APP), installed_ref(RUNTIME)], RuntimeError("unavailable")]
        result = helper.apply_cleanup(Mock(), Mock(), target, "user", snapshot()["digest"], [RUNTIME])
        self.assertFalse(result["success"])
        self.assertIn("could not be inspected", result["error"])

    @patch("services.software.flatpak_maintenance_helper.os.umask", return_value=0o077)
    @patch("services.software.flatpak_maintenance_helper.signal.signal")
    def test_shared_transaction_uses_and_restores_umask(self, _signal, umask):
        data = snapshot()
        for name in ("system", "office"):
            api, target, user = Mock(), self.target(), Mock()
            target.list_installed_refs.return_value = [installed_ref(RUNTIME)]
            api.get_system_installations.return_value = []
            api.Installation.new_user.return_value = user
            user.list_installed_refs.return_value = []
            digest = helper.inspect_unused(target, name, api)["digest"]
            result = helper.apply_cleanup(api, Mock(), target, name, digest, [RUNTIME])
            self.assertFalse(result["success"])
            self.assertEqual(umask.call_args_list[-2].args, (0o022,))
            self.assertEqual(umask.call_args_list[-1].args, (0o077,))
        umask.reset_mock()
        helper.apply_cleanup(Mock(), Mock(), self.target(), "user", data["digest"], [RUNTIME])
        umask.assert_not_called()

    def test_shared_candidates_protect_foreign_runtime_sdk_and_extensions(self):
        api, target, user = Mock(), self.target(), Mock()
        target.list_installed_refs.return_value = [installed_ref(RUNTIME)]
        api.get_system_installations.return_value = []
        api.Installation.new_user.return_value = user
        app = installed_ref(APP)
        user.list_installed_refs.return_value = [app]
        first = helper.inspect_unused(target, "system", api)
        self.assertEqual(first["refs"], [])
        self.assertTrue(first["dependency_digest"])
        app.load_metadata.return_value.get_data.return_value = b"[Application]\nsdk=org.example.Unused/x86_64/stable\n"
        second = helper.inspect_unused(target, "system", api)
        self.assertEqual(second["refs"], [])
        self.assertNotEqual(first["digest"], second["digest"])
        app.load_metadata.return_value.get_data.return_value = b"[Application]\n[Extension org.example]\nsubdirectories=true\n"
        self.assertEqual(helper.inspect_unused(target, "system", api)["refs"], [])
        app.load_metadata.return_value.get_data.return_value = b"[ExtensionOf]\nref=runtime/org.example.Unused/x86_64/stable\n"
        self.assertEqual(helper.inspect_unused(target, "system", api)["refs"], [])
        app.load_metadata.return_value.get_data.return_value = b"[Application]\nruntime=bad\n"
        self.assertRaises(ValueError, helper.inspect_unused, target, "system", api)
        user.list_installed_refs.side_effect = RuntimeError("unreadable user inventory")
        self.assertRaises(RuntimeError, helper.inspect_unused, target, "system", api)

    def test_shared_public_installation_dependencies_and_commits_bound(self):
        api, target, user, other = Mock(), self.target(), Mock(), Mock()
        target.list_installed_refs.return_value = [installed_ref(RUNTIME)]
        target.get_path.return_value.get_path.return_value = "/selected"
        other.get_path.return_value.get_path.return_value = "/other"
        other.get_id.return_value = "office"
        app = installed_ref(APP)
        other.list_installed_refs.return_value = [app]
        user.list_installed_refs.return_value = []
        api.Installation.new_user.return_value = user
        api.get_system_installations.return_value = [target, other]
        first = helper.inspect_unused(target, "system", api)
        self.assertEqual(first["refs"], [])
        app.get_commit.return_value = "b" * 64
        second = helper.inspect_unused(target, "system", api)
        self.assertNotEqual(first["digest"], second["digest"])
        other.list_installed_refs.side_effect = RuntimeError("unreadable public installation")
        self.assertRaises(RuntimeError, helper.inspect_unused, target, "system", api)

    def test_own_unused_self_sdk_is_not_promoted_to_used(self):
        api, target, user = Mock(), self.target(), Mock()
        item = installed_ref(RUNTIME)
        item.load_metadata.return_value.get_data.return_value = b"[Runtime]\nsdk=org.example.Unused/x86_64/stable\n"
        target.list_installed_refs.return_value = [item]
        api.get_system_installations.return_value = []
        api.Installation.new_user.return_value = user
        user.list_installed_refs.return_value = []
        self.assertEqual(helper.inspect_unused(target, "system", api)["refs"], [record(RUNTIME)])


class TestActionAndPolicy(unittest.TestCase):
    def parameters(self):
        return {"installation": "user", "refs": [RUNTIME], "snapshot_digest": snapshot()["digest"]}

    def test_command_shape_and_authority(self):
        vector = [helper_command(), *flatpak_cleanup._args(self.parameters())]
        validate_command_vector(vector)
        self.assertEqual(classify_command(vector[0], vector[1:]), "host")
        self.assertTrue(execution_allowed(vector[0], vector[1:], authority="action_center", action_id=flatpak_cleanup.ACTION_ID))
        self.assertFalse(execution_allowed(vector[0], vector[1:]))
        self.assertFalse(execution_allowed(vector[0], vector[1:], authority="action_center", action_id="other"))
        self.assertRaises(CommandValidationError, validate_command_vector, ["pkexec", *vector])
        self.assertRaises(CommandValidationError, validate_command_vector, ["/tmp/loofi-flatpak-maintenance", *vector[1:]])
        self.assertRaises(CommandValidationError, validate_command_vector, [vector[0], "apply", "--delete-data"])
        self.assertEqual(classify_command(vector[0], ["unused", "--installation", "user"]), "read_only")
        self.assertEqual(classify_command("/tmp/loofi-flatpak-maintenance", vector[1:]), "manual_only")
        self.assertTrue(validate_helper_args(["details", "--installation", "office", "--ref", APP]))
        for params in [{**self.parameters(), "refs": [APP]}, {**self.parameters(), "refs": [RUNTIME, RUNTIME]},
                       {**self.parameters(), "snapshot_digest": "bad"}, {**self.parameters(), "refs": []}]:
            self.assertFalse(flatpak_cleanup._validate(params).allowed)
        self.assertIn("/usr/bin/loofi-flatpak-maintenance", trusted_helpers())

    @patch("core.actions.flatpak_cleanup.FlatpakMaintenanceService")
    def test_action_preflight_and_verification(self, service):
        current = UnusedSnapshot("user", True, refs=(RefRecord(**record(RUNTIME)),), installed=(RefRecord(**record(APP)), RefRecord(**record(RUNTIME))), digest=snapshot()["digest"])
        service.return_value.unused.return_value = current
        decision = flatpak_cleanup._preflight(self.parameters(), Mock())
        self.assertTrue(decision.allowed)
        plan = SimpleNamespace(parameters=self.parameters(), policy_decision=decision)
        self.assertEqual(flatpak_cleanup._verify(Mock(), plan, Mock()).state, "failed")
        service.return_value.unused.return_value = UnusedSnapshot("user", True, installed=(RefRecord(**record(APP)),))
        self.assertEqual(flatpak_cleanup._verify(Mock(), plan, Mock()).state, "succeeded")
        service.return_value.unused.return_value = UnusedSnapshot("user", True)
        self.assertEqual(flatpak_cleanup._verify(Mock(), plan, Mock()).state, "failed")
        service.return_value.unused.return_value = UnusedSnapshot("user", error="unavailable")
        self.assertFalse(flatpak_cleanup._preflight(self.parameters(), Mock()).allowed)
        self.assertEqual(flatpak_cleanup._verify(Mock(), plan, Mock()).state, "failed")
        service.return_value.unused.return_value = UnusedSnapshot("user", True, digest="b" * 64)
        self.assertFalse(flatpak_cleanup._preflight(self.parameters(), Mock()).allowed)
        self.assertFalse(flatpak_cleanup._preflight({}, Mock()).allowed)
        self.assertEqual(flatpak_cleanup._render(self.parameters(), Mock())[1], "apply")
        definition = ActionCatalog().get(flatpak_cleanup.ACTION_ID)
        self.assertEqual(definition.operation_class, "host")


if __name__ == "__main__":
    unittest.main()
