"""Rootless regression coverage of the native libdnf5 session boundary."""
import json
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from services.software.rpm_transaction_helper import RpmSession, _timeout, main
from services.software.rpm_transactions import CODEC_PACKAGES, evidence_digest, request_args


def package(name, version="1", repo="fixture", signed=True):
    result = Mock()
    result.get_name.return_value = name
    result.get_full_nevra.return_value = f"{name}-0:{version}-1.noarch"
    result.get_repo_id.return_value = repo
    result.get_checksum.return_value.get_checksum.return_value = "a" * 64
    result.is_pkg_gpgcheck_enabled.return_value = signed
    return result


def transaction_item(pkg, action="Install"):
    result = Mock()
    result.get_package.return_value = pkg
    result.get_action.return_value = action
    return result


def native_api(items=None):
    """Model only the native calls used by the helper, without a host RPMDB."""
    events = []
    base, goal, settings, transaction = Mock(), Mock(), Mock(), Mock()
    config, repo_config = Mock(), Mock()
    base.get_config.return_value = config
    base.lock_system_repo.side_effect = lambda *_args: events.append("lock") or True
    base.get_repo_sack.return_value.load_repos.side_effect = lambda *_args: events.append("load")
    repo = Mock()
    repo.get_id.return_value = "fixture"
    repo.get_config.return_value = repo_config
    for key, value in {"enabled": True, "baseurl": ["https://fixture.invalid/repo"], "metalink": "", "mirrorlist": "",
                       "gpgkey": ["file:///fixture/key"], "pkg_gpgcheck": True, "repo_gpgcheck": True, "sslverify": True}.items():
        setattr(repo_config, key, value)
    query = Mock()
    query.__iter__ = Mock(return_value=iter([package("unrelated", repo="@System"), package("existing", repo="@System")]))
    transaction.get_problems.return_value = 0
    transaction.get_transaction_packages.return_value = items if items is not None else [transaction_item(package("fixture"))]
    transaction.TransactionRunResult_SUCCESS = 0
    transaction.run.return_value = 0
    transaction.check_gpg_signatures.return_value = True
    goal.resolve.return_value = transaction
    api = (SimpleNamespace(Base=Mock(return_value=base), Goal=Mock(return_value=goal), GoalJobSettings=Mock(return_value=settings)),
           SimpleNamespace(RepoQuery=Mock(return_value=[repo]), Repo=SimpleNamespace(Type_SYSTEM="system")),
           SimpleNamespace(PackageQuery=Mock(return_value=query)),
           SimpleNamespace(transaction_item_action_to_string=lambda action: action,
                           transaction_item_action_is_inbound=lambda action: action in {"Install", "Upgrade", "Reinstall"}),
           SimpleNamespace(LockAccess_WRITE="write", LockBlocking_NON_BLOCKING="nonblocking"))
    return SimpleNamespace(api=api, base=base, config=config, repo_config=repo_config, goal=goal, settings=settings,
                           transaction=transaction, query=query, events=events)


class RpmSessionTests(unittest.TestCase):
    @patch("services.software.rpm_transaction_helper.load_api")
    def test_source_identity_binds_endpoints_and_keys_without_metadata_download(self, load_api):
        native = native_api()
        load_api.return_value = native.api
        session = RpmSession()
        original = session.source_state()
        self.assertTrue(original["available"])
        self.assertEqual(original["enabled_count"], 1)
        native.base.get_repo_sack.return_value.load_repos.assert_not_called()
        native.repo_config.baseurl = ["https://changed.invalid/repo"]
        changed_url = session.source_state()
        self.assertNotEqual(changed_url["repository_digest"], original["repository_digest"])
        native.repo_config.gpgkey = ["file:///changed/key"]
        self.assertNotEqual(session.source_state()["repository_digest"], changed_url["repository_digest"])
        self.assertNotIn("https://", json.dumps(original))

    @patch("services.software.rpm_transaction_helper.signal.alarm")
    @patch("services.software.rpm_transaction_helper.signal.signal")
    @patch("services.software.rpm_transaction_helper.RpmSession")
    @patch("builtins.print")
    def test_source_mode_only_observes_configuration(self, output, session_class, _signal, _alarm):
        expected = {"available": True, "enabled_count": 1, "repository_digest": "a" * 64}
        session_class.return_value.source_state.return_value = expected
        self.assertEqual(main(["sources"]), 0)
        session_class.assert_called_once_with(writable=False)
        session_class.return_value.resolve.assert_not_called()
        self.assertEqual(json.loads(output.call_args.args[0]), expected)

    @patch("services.software.rpm_transaction_helper.load_api")
    def test_writable_session_locks_before_loading_and_disables_partial_repositories(self, load_api):
        native = native_api()
        load_api.return_value = native.api
        session = RpmSession(writable=True)
        session.resolve("install", ("fixture",), "", False)
        self.assertEqual(native.events, ["lock", "load"])
        native.base.lock_system_repo.assert_called_once_with("write", "nonblocking")
        for option, value in (("plugins", False), ("cacheonly", "all"), ("clean_requirements_on_remove", False),
                              ("install_weak_deps", False), ("allow_downgrade", False), ("assumeno", True),
                              ("pkg_gpgcheck", True), ("localpkg_gpgcheck", True), ("skip_if_unavailable", False)):
            getattr(native.config, "get_" + option + "_option").return_value.set.assert_called_once_with(value)
        native.repo_config.get_skip_if_unavailable_option.return_value.set.assert_called_once_with(False)
        session.close()
        native.base.unlock_system_repo.assert_called_once_with()

    @patch("services.software.rpm_transaction_helper.load_api")
    def test_lock_contention_never_loads_repositories_or_resolves(self, load_api):
        native = native_api()
        native.base.lock_system_repo.side_effect = None
        native.base.lock_system_repo.return_value = False
        load_api.return_value = native.api
        with self.assertRaisesRegex(ValueError, "lock"):
            RpmSession(writable=True)
        native.base.get_repo_sack.assert_not_called()
        native.goal.resolve.assert_not_called()

    @patch("services.software.rpm_transaction_helper.load_api")
    def test_install_pins_source_and_exact_selector_and_records_complete_evidence(self, load_api):
        native = native_api([transaction_item(package("z-dependency")), transaction_item(package("fixture"))])
        load_api.return_value = native.api
        preview, transaction = RpmSession().resolve("install", ("fixture-0:1-1.noarch",), "fixture", False)
        native.base.lock_system_repo.assert_not_called()
        native.base.get_repo_sack.return_value.load_repos.assert_called_once_with()
        native.query.filter_installed.assert_called_once_with()
        native.settings.set_to_repo_ids.assert_called_once_with(["fixture"])
        native.goal.add_rpm_install.assert_called_once_with("fixture-0:1-1.noarch", native.settings)
        for key in ("clean_requirements_on_remove", "with_provides", "with_filenames", "with_binaries", "expand_globs", "skip_unavailable", "skip_broken"):
            getattr(native.settings, "set_" + key).assert_called_once_with(False)
        native.goal.set_allow_erasing.assert_not_called()
        self.assertIs(transaction, native.transaction)
        self.assertEqual(preview.installed, ("existing-0:1-1.noarch", "unrelated-0:1-1.noarch"))
        self.assertEqual([item["name"] for item in preview.operations], ["fixture", "z-dependency"])
        self.assertEqual(preview.operations[0], {"action": "Install", "name": "fixture", "nevra": "fixture-0:1-1.noarch",
                                                 "repo_id": "fixture", "checksum": "a" * 64})
        self.assertEqual(preview.digest, evidence_digest(preview.to_dict()))
        self.assertEqual(len(preview.repository_digest), 64)

    @patch("services.software.rpm_transaction_helper.load_api")
    def test_remove_loads_only_system_and_keeps_dependency_removal_evidence(self, load_api):
        native = native_api([transaction_item(package("existing", repo="@System"), "Remove"),
                             transaction_item(package("dependent", repo="@System"), "Remove")])
        load_api.return_value = native.api
        preview, _transaction = RpmSession().resolve("remove", ("existing-0:1-1.noarch",), "", False)
        native.base.get_repo_sack.return_value.load_repos.assert_called_once_with("system")
        native.goal.add_rpm_remove.assert_called_once_with("existing-0:1-1.noarch", native.settings)
        native.goal.add_rpm_install.assert_not_called()
        native.goal.set_allow_erasing.assert_called_once_with(True)
        native.settings.set_to_repo_ids.assert_not_called()
        self.assertEqual({item["name"] for item in preview.operations}, {"existing", "dependent"})
        self.assertTrue(all(item["checksum"] == "" for item in preview.operations))

    @patch("services.software.rpm_transaction_helper.load_api")
    def test_codec_replacements_require_explicit_erasing_and_preserve_both_sides(self, load_api):
        native = native_api([transaction_item(package("ffmpeg")), transaction_item(package("ffmpeg-free"), "Remove")])
        load_api.return_value = native.api
        preview, _transaction = RpmSession().resolve("codecs", CODEC_PACKAGES, "", True)
        native.goal.set_allow_erasing.assert_called_once_with(True)
        self.assertEqual(native.goal.add_rpm_install.call_count, len(CODEC_PACKAGES))
        self.assertTrue(preview.allow_replacements)
        self.assertEqual(len(preview.operations), 2)

    @patch("services.software.rpm_transaction_helper.load_api")
    def test_conflicts_protected_components_and_unsigned_overrides_fail_closed(self, load_api):
        for reason in ("conflict", "protected", "unsigned"):
            with self.subTest(reason=reason):
                native = native_api()
                if reason == "conflict":
                    native.transaction.get_problems.return_value = 1
                elif reason == "protected":
                    native.transaction.get_transaction_packages.return_value = [transaction_item(package("dnf5"), "Remove")]
                else:
                    native.transaction.get_transaction_packages.return_value = [transaction_item(package("fixture", signed=False))]
                load_api.return_value = native.api
                with self.assertRaises(ValueError):
                    RpmSession().resolve("remove" if reason == "protected" else "install", ("fixture",), "", False)
                native.transaction.download.assert_not_called()
                native.transaction.run.assert_not_called()


@patch("services.software.rpm_transaction_helper.signal.alarm")
@patch("services.software.rpm_transaction_helper.signal.signal")
@patch("services.software.rpm_transaction_helper.os.geteuid", return_value=0)
@patch("builtins.print")
class RpmNativeEntrypointTests(unittest.TestCase):
    @patch("services.software.rpm_transaction_helper.load_api")
    def test_apply_success_uses_approved_transaction_and_unlocks(self, load_api, output, _uid, _signal, alarm):
        native = native_api()
        load_api.return_value = native.api
        preview, _transaction = RpmSession().resolve("install", ("fixture",), "", False)
        # A new helper session needs a fresh iterable inventory, as libdnf supplies.
        native.query.__iter__.return_value = iter([package("unrelated", repo="@System"), package("existing", repo="@System")])
        native.config.get_cacheonly_option.return_value.set.reset_mock()

        def download():
            self.assertEqual(native.config.get_cacheonly_option.return_value.set.call_args.args, ("metadata",))
        native.transaction.download.side_effect = download
        self.assertEqual(main(preview.apply_vector()[1:]), 0)
        self.assertEqual(native.config.get_cacheonly_option.return_value.set.call_args_list[0].args, ("all",))
        native.transaction.download.assert_called_once_with()
        native.transaction.check_gpg_signatures.assert_called_once_with()
        native.transaction.set_description.assert_called_once_with("Loofi reviewed install")
        native.transaction.run.assert_called_once_with()
        self.assertEqual(json.loads(output.call_args.args[0]), preview.to_dict())
        native.base.unlock_system_repo.assert_called_once_with()
        self.assertEqual(alarm.call_args.args, (0,))

    @patch("services.software.rpm_transaction_helper.load_api")
    def test_non_successful_native_run_returns_closed_failure_and_unlocks(self, load_api, output, _uid, _signal, _alarm):
        native = native_api()
        load_api.return_value = native.api
        preview, _transaction = RpmSession().resolve("install", ("fixture",), "", False)
        native.query.__iter__.return_value = iter([package("unrelated", repo="@System"), package("existing", repo="@System")])
        native.transaction.run.return_value = 1
        self.assertEqual(main(preview.apply_vector()[1:]), 1)
        native.transaction.run.assert_called_once_with()
        native.base.unlock_system_repo.assert_called_once_with()
        self.assertFalse(json.loads(output.call_args.args[0])["available"])

    @patch("services.software.rpm_transaction_helper.RpmSession")
    def test_oversized_evidence_is_never_reported_as_available(self, session_class, output, _uid, _signal, _alarm):
        preview = Mock()
        preview.to_dict.return_value = {"available": True, "oversized": "x" * (1024 * 1024)}
        session_class.return_value.resolve.return_value = (preview, Mock())
        self.assertEqual(main(["preview", *request_args("install", ("fixture",))]), 1)
        self.assertFalse(json.loads(output.call_args.args[0])["available"])
        session_class.return_value.close.assert_called_once_with()

    @patch("services.software.rpm_transaction_helper.load_api")
    def test_drift_keeps_cacheonly_all_and_never_downloads(self, load_api, output, _uid, _signal, _alarm):
        native = native_api()
        load_api.return_value = native.api
        self.assertEqual(main(["apply", *request_args("install", ("fixture",)), "--snapshot-digest", "0" * 64]), 1)
        native.config.get_cacheonly_option.return_value.set.assert_called_once_with("all")
        native.transaction.download.assert_not_called()
        native.transaction.run.assert_not_called()
        native.base.unlock_system_repo.assert_called_once_with()
        self.assertFalse(json.loads(output.call_args.args[0])["available"])

    @patch("services.software.rpm_transaction_helper.load_api")
    def test_preview_never_downloads_or_mutates(self, load_api, output, _uid, _signal, alarm):
        native = native_api()
        load_api.return_value = native.api
        self.assertEqual(main(["preview", *request_args("install", ("fixture",))]), 0)
        native.base.lock_system_repo.assert_not_called()
        native.transaction.download.assert_not_called()
        native.transaction.run.assert_not_called()
        native.base.unlock_system_repo.assert_called_once_with()
        self.assertTrue(json.loads(output.call_args.args[0])["available"])
        self.assertEqual(alarm.call_args_list[0].args, (85,))

    @patch("services.software.rpm_transaction_helper.RpmSession")
    def test_backend_errors_are_redacted_and_always_release_existing_session(self, session_class, output, _uid, _signal, alarm):
        for failure in (OSError, RuntimeError, TypeError, AttributeError, TimeoutError):
            with self.subTest(failure=failure.__name__):
                session = session_class.return_value
                session.reset_mock()
                session.resolve.side_effect = failure("private https://user:secret@fixture.invalid")
                self.assertEqual(main(["preview", *request_args("install", ("fixture",))]), 1)
                self.assertNotIn("secret", output.call_args.args[0])
                self.assertFalse(json.loads(output.call_args.args[0])["available"])
                session.close.assert_called_once_with()
                self.assertEqual(alarm.call_args.args, (0,))

    @patch("services.software.rpm_transaction_helper.RpmSession")
    def test_unprivileged_apply_is_rejected_before_session_creation(self, session_class, output, _uid, _signal, _alarm):
        _uid.return_value = 1000
        self.assertEqual(main(["apply", *request_args("install", ("fixture",)), "--snapshot-digest", "0" * 64]), 1)
        session_class.assert_not_called()

    def test_timeout_is_a_closed_error(self, _output, _uid, _signal, _alarm):
        with self.assertRaises(TimeoutError):
            _timeout(14, None)
