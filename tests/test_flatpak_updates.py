"""Installation and commit authority for reviewed Flatpak updates."""
import unittest
import json
import signal
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, mock_open, patch

from core.actions import flatpak_updates as action
from core.execution_policy import classify_command, execution_allowed
from core.executor.command_policy import validate_command_vector
from services.software import flatpak_maintenance_helper as helper
from services.software.flatpak_maintenance import validate_helper_args
from services.software.flatpak_updates import FlatpakUpdatesService, UpdateSnapshot, apply_vector, update_digest, snapshot_from_facts

APP = "app/org.example.App/x86_64/stable"
RUNTIME = "runtime/org.example.Runtime/x86_64/stable"
OLD, NEW = "a" * 64, "b" * 64


def candidate(name="user", ref=APP):
    return {"installation": name, "ref": ref, "origin": "local", "installed_commit": OLD, "expected_commit": NEW,
            "name": "Example", "installed_version": "1", "available_version": ""}


def evidence(name="user", preview=True):
    selected = candidate(name)
    operations = [{**selected, "operation": "update", "selected": True},
                  {**candidate(name, RUNTIME), "installed_commit": "", "operation": "install", "selected": False}] if preview else []
    return {"available": True, "installation": name, "candidates": [selected], "operations": operations,
            "digest": update_digest(name, [selected], operations, OLD), "source_digest": OLD}


class TestUpdateEvidence(unittest.TestCase):
    @patch("services.software.flatpak_maintenance_helper._GLIB")
    @patch("services.software.flatpak_maintenance_helper.Path.open", new_callable=mock_open,
           read_data='[remote "local"]\nName=räksmörgås\ngpg-verify-summary=true\n')
    def test_system_local_source_requires_commit_and_summary_verification(self, opened, glib):
        remote, target = Mock(), Mock()
        remote.get_name.return_value = "local"
        remote.get_url.return_value = "file:///fixture"
        remote.get_gpg_verify.return_value = True
        target.list_remotes.return_value = [remote]
        target.get_path.return_value.get_path.return_value = "/unused/system"
        config = glib.KeyFile.new.return_value
        config.get_boolean.return_value = True
        self.assertTrue(helper._system_source_commit_bound(target, "local"))
        content = '[remote "local"]\nName=räksmörgås\ngpg-verify-summary=true\n'
        config.load_from_data.assert_called_once_with(content, len(content.encode("utf-8")), glib.KeyFileFlags.NONE)
        config.get_boolean.assert_called_once_with('remote "local"', "gpg-verify-summary")
        remote.get_gpg_verify.return_value = False
        self.assertFalse(helper._system_source_commit_bound(target, "local"))
        remote.get_gpg_verify.return_value = True
        config.get_boolean.return_value = False
        self.assertFalse(helper._system_source_commit_bound(target, "local"))
        # Native GLib rejects missing exact keys, including DEFAULT inheritance
        # and differently cased keys. Preserve that fail-closed result.
        config.get_boolean.side_effect = ValueError("Key not found")
        self.assertFalse(helper._system_source_commit_bound(target, "local"))
        config.get_boolean.side_effect = None
        config.load_from_data.side_effect = ValueError("Malformed key file")
        self.assertFalse(helper._system_source_commit_bound(target, "local"))
        remote.get_url.return_value = "oci+https://registry.example.test"
        self.assertTrue(helper._system_source_commit_bound(target, "local"))
        self.assertFalse(helper._system_source_commit_bound(target, "missing"))

    @patch("services.software.flatpak_maintenance_helper.Path.is_file", return_value=True)
    @patch("services.software.flatpak_maintenance_helper.Path.open", new_callable=mock_open, read_data=b"summary=false")
    def test_source_digest_binds_repository_verification_settings(self, opened, _is_file):
        target = Mock()
        target.list_remotes.return_value = []
        target.get_path.return_value.get_path.return_value = "/unused/system"
        before = helper._update_source_digest(target)
        opened.return_value.read.return_value = b"summary=true"
        self.assertNotEqual(before, helper._update_source_digest(target))

    def test_same_ref_distinct_installations_and_batch_binding(self):
        def probe(vector):
            if vector[1] == "installations":
                return {"available": True, "installations": ["user", "system", "office"]}
            return evidence(vector[3])
        snapshot = FlatpakUpdatesService(probe=probe).preview()
        self.assertEqual([item.installation for item in snapshot.candidates], ["user", "system", "office"])
        vector = apply_vector(snapshot)
        self.assertTrue(validate_helper_args(vector[1:]))
        validate_command_vector(vector)
        self.assertEqual(classify_command(vector[0], vector[1:]), "host")
        self.assertTrue(execution_allowed(vector[0], vector[1:], authority="action_center", action_id="update-flatpaks"))
        self.assertFalse(execution_allowed(vector[0], vector[1:], authority="legacy"))
        self.assertFalse(execution_allowed(vector[0], vector[1:], authority="action_center", action_id="remove-unused-flatpaks"))

    def test_partial_installation_results_survive(self):
        def probe(vector):
            if vector[1] == "installations":
                return {"available": True, "installations": ["user", "office"]}
            return evidence(preview=False) if vector[3] == "user" else {"available": False, "error": "private-token"}
        snapshot = FlatpakUpdatesService(probe=probe).discover()
        self.assertEqual(snapshot.status, "partial")
        self.assertEqual(len(snapshot.candidates), 1)
        self.assertNotIn("private-token", snapshot.to_dict().__str__())
        with self.assertRaises(ValueError):
            apply_vector(snapshot)

    def test_identity_validation_and_incomplete_or_illegal_evidence(self):
        for refs in ([{}], [None], [APP, APP]):
            self.assertFalse(FlatpakUpdatesService(probe=Mock()).preview("user", refs).available)
        for change in ("digest", "missing", "no-operations", "uninstall", "unselected", "empty-commit"):
            payload = evidence()
            if change == "digest":
                payload["digest"] = OLD
            elif change == "missing":
                payload["candidates"] = []
            elif change == "no-operations":
                payload["operations"] = []
            elif change == "uninstall":
                payload["operations"][0]["operation"] = "uninstall"
            elif change == "unselected":
                payload["operations"][0]["selected"] = False
            else:
                payload["candidates"][0]["installed_commit"] = ""
            if change != "digest":
                payload["digest"] = update_digest("user", payload["candidates"], payload["operations"], payload["source_digest"])
            with self.subTest(change=change):
                self.assertFalse(FlatpakUpdatesService(probe=lambda _v: payload).preview("user", (APP,)).available)

    def test_discovery_selected_current_app_and_mixed_selection(self):
        payload = evidence(preview=False)
        service = FlatpakUpdatesService(probe=lambda _v: payload)
        mixed = service.discover("user", (APP, RUNTIME))
        self.assertTrue(mixed.available)
        self.assertEqual([item.ref for item in mixed.candidates], [APP])
        payload["candidates"] = []
        payload["digest"] = update_digest("user", [], [], payload["source_digest"])
        current = service.discover("user", (APP,))
        self.assertTrue(current.available)
        self.assertEqual(current.candidates, ())
        self.assertFalse(service.preview("user", (APP,)).available)

    def test_checked_timestamp_is_not_review_authority(self):
        service = FlatpakUpdatesService(probe=lambda _v: evidence())
        self.assertEqual(service.preview("user").review_facts(), service.preview("user").review_facts())
        self.assertEqual(FlatpakUpdatesService(probe=lambda _v: {}).discover().status, "unavailable")

    def test_cancellation_retains_completed_sources(self):
        calls = []

        def probe(vector):
            if vector[1] == "installations":
                return {"available": True, "installations": ["user", "system"]}
            calls.append(vector[3])
            return evidence(vector[3], preview=False) if vector[3] == "user" else {"cancelled": True}
        snapshot = FlatpakUpdatesService(probe=probe).discover()
        self.assertEqual(snapshot.status, "cancelled")
        self.assertEqual(len(snapshot.candidates), 1)

    def test_helper_shapes_reject_ambiguous_or_unbound_arguments(self):
        valid = ["update-apply", "--installation", "user", "--snapshot-digest", NEW, "--ref", APP, "--commit", NEW]
        self.assertTrue(validate_helper_args(valid))
        for args in (valid[:-1], [*valid, *valid[1:]], [*valid[:7], "--commit", "bad"], ["update-preview", "--installation", "user", "--ref", "org.example.App"]):
            self.assertFalse(validate_helper_args(args))
        self.assertTrue(validate_helper_args(["update-state", "--installation", "office", "--ref", APP]))

    @patch("core.actions.flatpak_updates.FlatpakMaintenanceService._probe")
    def test_independent_verification_in_exact_installation(self, probe):
        probe.side_effect = [{"available": True, "installation": "office", "ref": APP, "commit": NEW},
                             {"available": True, "installation": "office", "ref": RUNTIME, "commit": OLD}]
        facts = {"flatpak_updates": {"evidence_version": 1, "installations": [evidence("office")]}}
        result = action._verify(SimpleNamespace(state="failed"), SimpleNamespace(policy_decision=SimpleNamespace(facts=facts)), Mock())
        self.assertEqual([item["status"] for item in result.data["results"]], ["verified", "failed"])
        self.assertTrue(all("office" in call.args[0] for call in probe.call_args_list))
        for bad in (None, [], {}, {"evidence_version": 1, "installations": [None]}):
            result = action._verify(Mock(), SimpleNamespace(policy_decision=SimpleNamespace(facts={"flatpak_updates": bad})), Mock())
            self.assertEqual(result.state, "failed")

    @patch("services.software.flatpak_maintenance_helper.Path.is_file", return_value=False)
    def test_source_digest_detects_same_name_url_change(self, _is_file):
        remote = Mock()
        values = {"name": "local", "url": "file:///first", "gpg_verify": False, "disabled": False, "collection_id": None,
                  "filter": None, "nodeps": False, "noenumerate": False, "prio": 1, "default_branch": None, "main_ref": None}
        for key, value in values.items():
            getattr(remote, "get_" + key).return_value = value
        target = Mock()
        target.list_remotes.return_value = [remote]
        target.get_path.return_value.get_path.return_value = "/unused/installation"
        first = helper._update_source_digest(target)
        remote.get_url.return_value = "file:///second"
        second = helper._update_source_digest(target)
        self.assertNotEqual(first, second)
        payload = evidence()
        self.assertNotEqual(update_digest("user", payload["candidates"], payload["operations"], first),
                            update_digest("user", payload["candidates"], payload["operations"], second))

    def test_unscoped_ref_filter_reviews_only_matching_installations(self):
        calls = []

        def probe(vector):
            calls.append(tuple(vector))
            if vector[1] == "installations":
                return {"available": True, "installations": ["user", "system", "office"]}
            name, mode = vector[3], vector[1]
            payload = evidence(name, preview=mode == "update-preview")
            if name != "user":
                payload["candidates"], payload["operations"] = [], []
                payload["digest"] = update_digest(name, [], [], OLD)
            return payload
        snapshot = FlatpakUpdatesService(probe=probe).preview(refs=(APP,))
        self.assertTrue(snapshot.available)
        self.assertTrue(all(scope.available for scope in snapshot.installations))
        self.assertEqual([item.installation for item in snapshot.candidates], ["user"])
        self.assertTrue(all("--ref" not in call for call in calls if call[1] == "updates"))
        self.assertNotIn("system", apply_vector(snapshot))

    @patch("services.software.flatpak_maintenance_helper.os.path.realpath", side_effect=lambda value: value)
    def test_source_digest_binds_same_named_installation_location(self, _realpath):
        target = Mock()
        target.list_remotes.return_value = []
        target.get_path.return_value.get_path.return_value = "/first/named"
        first = helper._update_source_digest(target)
        target.get_path.return_value.get_path.return_value = "/second/named"
        self.assertNotEqual(first, helper._update_source_digest(target))

    @patch("services.software.flatpak_maintenance_helper.signal.signal")
    @patch("services.software.flatpak_maintenance_helper.os.geteuid", return_value=1000)
    @patch("services.software.flatpak_maintenance_helper.load_api")
    @patch("services.software.flatpak_maintenance_helper.inspect_updates")
    @patch("services.software.flatpak_maintenance_helper.installation")
    @patch("builtins.print")
    def test_native_sigterm_cancellation_propagates_from_transaction_to_exit(self, output, installation, inspect, load_api, _uid, signal_handler):
        handlers = {}
        signal_handler.side_effect = lambda number, callback: handlers.__setitem__(number, callback) if callable(callback) else None
        operation = Mock()
        operation.get_operation_type.return_value = "UPDATE"
        operation.get_ref.return_value = APP
        operation.get_commit.return_value = NEW
        operation.get_remote.return_value = "local"
        installed = Mock()
        installed.format_ref.return_value = APP
        installed.get_commit.return_value = OLD
        installed.get_origin.return_value = "local"
        installed.get_appdata_name.return_value = "Example"
        installed.get_appdata_version.return_value = "1"
        target = installation.return_value
        target.list_installed_refs.return_value = [installed]
        target.list_remotes.return_value = []
        target.get_path.return_value.get_path.return_value = "/unused/installation"
        callbacks = {}
        transaction = Mock()
        transaction.get_operations.return_value = [operation]
        transaction.connect.side_effect = lambda name, callback: callbacks.__setitem__(name, callback)
        api, gio = Mock(), Mock()
        api.TransactionOperationType.UPDATE, api.TransactionOperationType.INSTALL = "UPDATE", "INSTALL"
        api.Transaction.new_for_installation.return_value = transaction

        def cancellable():
            state = {"cancelled": False}
            return SimpleNamespace(cancel=lambda: state.__setitem__("cancelled", True), is_cancelled=lambda: state["cancelled"])

        gio.Cancellable.new.side_effect = cancellable
        load_api.return_value = api, gio
        inspect.return_value = {"candidates": [candidate()]}
        resolved = []
        deny = [False]

        def run(cancel):
            if "ready" not in callbacks:
                resolved.append(callbacks["ready-pre-auth"](transaction))
                return False
            self.assertTrue(callbacks["ready"](transaction))
            if deny[0]:
                raise RuntimeError("authorization declined")
            handlers[signal.SIGTERM](signal.SIGTERM, None)
            self.assertTrue(cancel.is_cancelled())
            raise RuntimeError("cancelled by native signal")

        transaction.run.side_effect = run
        preview = helper.update_transaction(api, gio, target, "user", [candidate()])
        status = helper.main(["update-apply", "--installation", "user", "--snapshot-digest", preview["digest"], "--ref", APP, "--commit", NEW])
        payload = json.loads(output.call_args.args[0])
        self.assertEqual(status, 126)
        self.assertTrue(payload["cancelled"])
        self.assertTrue(payload["installations"][0]["cancelled"])
        self.assertEqual(payload["installations"][0]["results"][0]["status"], "cancelled")
        callbacks.clear()
        deny[0] = True
        status = helper.main(["update-apply", "--installation", "user", "--snapshot-digest", preview["digest"], "--ref", APP, "--commit", NEW])
        denied = json.loads(output.call_args.args[0])
        self.assertEqual(status, 1)
        self.assertFalse(denied["cancelled"])
        self.assertEqual(denied["installations"][0]["results"][0]["status"], "failed")

    def test_review_renderer_consumes_exact_facts_without_reinspection(self):
        snapshot = FlatpakUpdatesService(probe=lambda _v: evidence()).preview("user")
        facts = snapshot.review_facts()
        self.assertEqual(apply_vector(snapshot_from_facts(facts)), apply_vector(snapshot))
        with self.assertRaises(ValueError):
            snapshot_from_facts({"refs": [APP]})

    @patch("services.software.flatpak_updates.helper_command", return_value="/usr/bin/loofi-flatpak-maintenance")
    @patch("services.software.flatpak_updates.atomic_write_json")
    @patch("services.software.flatpak_updates.advisory_lock")
    @patch("services.software.flatpak_updates.Path.exists", return_value=True)
    @patch("services.software.flatpak_updates.Path.is_symlink", return_value=False)
    @patch("services.software.flatpak_updates.Path.stat")
    @patch("services.software.flatpak_updates.Path.read_text")
    def test_cache_preserves_corrupt_future_and_never_authorizes(self, read, stat, _symlink, _exists, _lock, write, _helper):
        stat.return_value.st_size = 100
        service = FlatpakUpdatesService(probe=lambda _v: evidence(preview=False), cache_path=Path("/unused/observations.json"))
        for value in ("broken", json.dumps({"schema_version": 99, "observation": {}})):
            read.return_value = value
            service.discover("user")
            self.assertIsNone(service.last_observation())
        write.assert_not_called()
        read.return_value = json.dumps({"schema_version": 1, "observation": {"available": True}})
        service._save_observation(UpdateSnapshot())
        write.assert_called_once()

    @patch("services.software.flatpak_maintenance_helper._system_source_commit_bound", return_value=True)
    @patch("services.software.flatpak_maintenance_helper.signal.signal")
    def test_preview_aborts_before_auth_and_rejects_removal(self, _signal, bound):
        operation = Mock()
        operation.get_operation_type.return_value = "UPDATE"
        operation.get_ref.return_value = APP
        operation.get_commit.return_value = NEW
        operation.get_remote.return_value = "local"
        installed = Mock()
        installed.format_ref.return_value = APP
        installed.get_commit.return_value = OLD
        installed.get_origin.return_value = "local"
        installed.get_appdata_name.return_value = "Example"
        installed.get_appdata_version.return_value = "1"
        target = Mock()
        target.list_installed_refs.return_value = [installed]
        target.list_remotes.return_value = []
        target.get_path.return_value.get_path.return_value = "/unused/installation"
        transaction = Mock()
        transaction.get_operations.return_value = [operation]
        callbacks = {}
        transaction.connect.side_effect = lambda name, callback: callbacks.__setitem__(name, callback)
        transaction.run.side_effect = lambda _c: callbacks["ready-pre-auth"](transaction)
        api, gio = Mock(), Mock()
        api.TransactionOperationType.UPDATE = "UPDATE"
        api.TransactionOperationType.INSTALL = "INSTALL"
        api.Transaction.new_for_installation.return_value = transaction
        gio.Cancellable.new.return_value.is_cancelled.return_value = False
        for name in ("user", "system", "office"):
            with self.subTest(installation=name):
                transaction.reset_mock()
                callbacks.clear()
                result = helper.update_transaction(api, gio, target, name, [candidate(name)])
                self.assertTrue(result["available"])
                self.assertNotIn("ready", callbacks)
                self.assertNotIn("success", result)
                transaction.add_update.assert_called_once_with(APP, None, None)
                transaction.add_default_dependency_sources.assert_called_once_with()
        self.assertFalse(callbacks["add-new-remote"]())
        self.assertFalse(callbacks["end-of-lifed-with-rebase"]())
        digest = result["digest"]
        callbacks.clear()
        operation.get_commit.return_value = "c" * 64
        transaction.run.side_effect = lambda _c: callbacks["ready"](transaction)
        changed = helper.update_transaction(api, gio, target, "office", [candidate("office")], digest)
        self.assertFalse(changed["success"])
        self.assertEqual(changed["operations"], [])
        self.assertIn("changed", changed["error"])
        operation.get_commit.return_value = NEW
        operation.get_operation_type.return_value = "UNINSTALL"
        callbacks.clear()
        transaction.run.side_effect = lambda _c: callbacks["ready-pre-auth"](transaction)
        result = helper.update_transaction(api, gio, target, "user", [candidate()])
        self.assertFalse(result["available"])
        operation.get_operation_type.return_value = "UPDATE"
        bound.return_value = False
        blocked = helper.update_transaction(api, gio, target, "system", [candidate("system")])
        self.assertFalse(blocked["available"])
        self.assertIn("signed summaries", blocked["error"])
        callbacks.clear()
        transaction.run.side_effect = lambda _c: callbacks["ready"](transaction)
        blocked_apply = helper.update_transaction(api, gio, target, "office", [candidate("office")], digest)
        self.assertFalse(blocked_apply["available"])
        self.assertFalse(blocked_apply["success"])
        self.assertEqual(blocked_apply["operations"], [])

    @patch("services.software.flatpak_maintenance_helper.signal.signal")
    @patch("services.software.flatpak_maintenance_helper.load_api")
    def test_apply_retains_failed_operation_identity_and_stable_error_code(self, load_api, _signal):
        operation = Mock()
        operation.get_operation_type.return_value = "UPDATE"
        operation.get_ref.return_value = APP
        operation.get_commit.return_value = NEW
        operation.get_remote.return_value = "local"
        installed = Mock()
        installed.format_ref.return_value = APP
        installed.get_commit.return_value = OLD
        installed.get_origin.return_value = "local"
        installed.get_appdata_name.return_value = "Example"
        installed.get_appdata_version.return_value = "1"
        target = Mock()
        target.list_installed_refs.return_value = [installed]
        target.list_remotes.return_value = []
        target.get_path.return_value.get_path.return_value = "/unused/installation"
        transaction = Mock()
        transaction.get_operations.return_value = [operation]
        callbacks = {}
        transaction.connect.side_effect = lambda name, callback: callbacks.__setitem__(name, callback)
        api, gio = Mock(), Mock()
        api.TransactionOperationType.UPDATE = "UPDATE"
        api.TransactionOperationType.INSTALL = "INSTALL"
        api.Transaction.new_for_installation.return_value = transaction
        gio.Cancellable.new.return_value.is_cancelled.return_value = False
        load_api.return_value = api, gio
        transaction.run.side_effect = lambda _c: callbacks["ready-pre-auth"](transaction)
        preview = helper.update_transaction(api, gio, target, "user", [candidate()])

        callbacks.clear()
        error = SimpleNamespace(domain="flatpak-error-quark", code=14)

        def fail_after_review(cancellable):
            self.assertTrue(callbacks["ready"](transaction))
            callbacks["operation-error"](transaction, operation, error, 0)
            raise RuntimeError("operation failed")

        transaction.run.side_effect = fail_after_review
        result = helper.update_transaction(api, gio, target, "user", [candidate()], preview["digest"])

        self.assertFalse(result["success"])
        self.assertEqual(result["operation_errors"], [{"ref": APP, "domain": "flatpak-error-quark", "code": 14, "details": 0}])
