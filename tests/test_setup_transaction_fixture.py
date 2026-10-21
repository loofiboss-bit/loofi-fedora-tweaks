"""Rootless contracts for the explicitly scoped native setup qualification."""
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from e2e.tests import setup_transaction_fixture as fixture
from e2e.tests.source_fixture_key import KEY_BYTES
from services.software.setup_sources import CODEC_PACKAGES, SOURCES
from services.software.rpm_transactions import request_args


class TestSetupTransactionFixture(unittest.TestCase):
    @patch('services.software.rpm_transaction_helper.RpmSession')
    def test_dependency_conflict_requires_actual_solver_rejection(self, session_class):
        session = session_class.return_value
        expected = 'Package dependencies could not be resolved without conflicts.'
        session.resolve.side_effect = ValueError(expected)
        self.assertEqual(fixture.require_native_dependency_conflict(), expected)
        session.resolve.assert_called_once_with('codecs', CODEC_PACKAGES, '', True)
        session.close.assert_called_once_with()

    @patch('services.software.rpm_transaction_helper.RpmSession')
    def test_missing_metadata_or_success_cannot_count_as_solver_conflict(self, session_class):
        for failure in (ValueError('Metadata unavailable'), None):
            with self.subTest(failure=failure):
                session = session_class.return_value
                session.reset_mock()
                session.resolve.side_effect = failure
                with self.assertRaisesRegex(RuntimeError, 'unexpected'):
                    fixture.require_native_dependency_conflict()
                session.close.assert_called_once_with()

    @patch.object(fixture.select, 'select')
    @patch.object(fixture.subprocess, 'Popen')
    def test_competing_native_lock_uses_separate_process_and_bounded_cleanup(self, popen, select):
        process = popen.return_value
        process.stdout.readline.return_value = 'locked\n'
        process.pid = 123
        select.return_value = ([process.stdout], [], [])
        with fixture.competing_file_lock(Path('/run/loofi-setup-sources.lock')) as pid:
            self.assertEqual(pid, 123)
            process.terminate.assert_not_called()
        invocation = popen.call_args.args[0]
        self.assertEqual(invocation[:2], ['/usr/bin/python3', '-c'])
        self.assertIn('fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)', invocation[2])
        self.assertEqual(invocation[3], '/run/loofi-setup-sources.lock')
        process.terminate.assert_called_once_with()
        process.communicate.assert_called_once_with(timeout=10)

    @patch.object(fixture.select, 'select', return_value=([], [], []))
    @patch.object(fixture.subprocess, 'Popen')
    def test_missing_child_lock_acknowledgment_cannot_count_as_fault_evidence(self, popen, _select):
        with self.assertRaisesRegex(RuntimeError, 'did not acquire'):
            with fixture.competing_file_lock(Path('/run/loofi-setup-sources.lock')):
                self.fail('The lock test cannot proceed without an actual acknowledgment')
        popen.return_value.terminate.assert_called_once_with()
        popen.return_value.communicate.assert_called_once_with(timeout=10)

    @patch.object(fixture, 'require_native_dependency_conflict', return_value='Native solver conflict')
    @patch.object(fixture.Path, 'read_bytes')
    @patch.object(fixture.Path, 'write_bytes')
    @patch.object(fixture.Path, 'read_text', return_value='Preserve data across native codec failures\n')
    @patch.object(fixture.Path, 'write_text')
    @patch.object(fixture, 'command', return_value='unrelated|unrelated-0:1.0-1.noarch')
    def test_native_fault_case_requires_exact_drift_error_and_blocked_conflict(self, command, _write_text, _read_text, write_bytes, read_bytes, native_conflict):
        original = f'gpgkey=file://{fixture.ROOT / "codec-key.asc"}\n'.encode()
        read_bytes.side_effect = [original, b'same-public-key', original]
        controller = Mock()
        valid = Mock(blocked=False)
        conflict = Mock(blocked=True)
        conflict.plan.policy_decision.reason_code = 'codec_transaction_unavailable'
        conflict.to_dict.return_value = {'blocked': True}
        controller.prepare.side_effect = [valid, conflict]
        controller.confirm.return_value.status = 'prepared'
        drift = Mock(status='failed')
        drift.result.stdout = '{"error_code":"transaction_drift"}'
        drift.to_dict.return_value = {'status': 'failed', 'error_code': 'transaction_drift'}
        controller.run.return_value = drift
        executor = SimpleNamespace(calls=[], execute=Mock())
        result = fixture.native_codec_failures(controller, executor, Path('/isolated/root'), Path('/isolated/repos'), ())
        self.assertTrue(result['inventory_preserved'])
        self.assertTrue(result['configs_preserved'])
        self.assertTrue(result['data_preserved'])
        self.assertEqual(result['signed_source_drift']['error_code'], 'transaction_drift')
        native_conflict.assert_called_once_with()
        self.assertEqual(result['native_resolver_conflict'], 'Native solver conflict')
        self.assertEqual(command.call_count, 3)
        self.assertEqual(write_bytes.call_args_list[-1].args[0], original)
        controller.verify.assert_not_called()
        self.assertEqual(controller.run.call_args.kwargs['executor'], executor.execute)

    @patch.object(fixture.Path, 'read_bytes')
    @patch.object(fixture.Path, 'write_bytes')
    @patch.object(fixture.Path, 'write_text')
    @patch.object(fixture, 'command', return_value='unrelated|unrelated-0:1.0-1.noarch')
    def test_other_execution_error_cannot_be_reported_as_native_drift(self, _command, _write_text, write_bytes, read_bytes):
        original = f'gpgkey=file://{fixture.ROOT / "codec-key.asc"}\n'.encode()
        read_bytes.side_effect = [original, b'same-public-key']
        controller = Mock()
        controller.prepare.return_value.blocked = False
        controller.confirm.return_value.status = 'prepared'
        controller.run.return_value.status = 'failed'
        controller.run.return_value.result.stdout = '{"error_code":"backend_unavailable"}'
        executor = SimpleNamespace(calls=[], execute=Mock())
        with self.assertRaisesRegex(RuntimeError, 'did not reject the changed signed repository'):
            fixture.native_codec_failures(controller, executor, Path('/isolated/root'), Path('/isolated/repos'), ())
        self.assertEqual(write_bytes.call_args_list[-1].args[0], original)
        self.assertEqual(controller.prepare.call_count, 1)

    @patch.object(fixture.os, 'geteuid', return_value=1000)
    @patch.object(fixture, 'command')
    def test_host_rejected_before_any_command(self, command, _uid):
        with self.assertRaisesRegex(RuntimeError, 'dedicated root guest'):
            fixture.guard()
        command.assert_not_called()

    @patch.object(fixture, 'command', return_value='none')
    @patch.object(fixture, 'MARKER')
    @patch.object(fixture.os, 'geteuid', return_value=0)
    def test_marker_without_qemu_does_not_authorize_mutation(self, _uid, marker, command):
        marker.is_file.return_value = True
        marker.read_text.return_value = 'loofi-fedora-tweaks-e2e'
        with self.assertRaisesRegex(RuntimeError, 'QEMU'):
            fixture.guard()
        command.assert_called_once_with(['systemd-detect-virt', '--vm'])

    @patch.object(fixture, 'REPORT')
    @patch.object(fixture, 'command', return_value='qemu')
    @patch.object(fixture, 'MARKER')
    @patch.object(fixture.os, 'geteuid', return_value=0)
    def test_existing_checkpoint_is_not_reused(self, _uid, marker, _command, report):
        marker.is_file.return_value = True
        marker.read_text.return_value = 'loofi-fedora-tweaks-e2e'
        report.exists.return_value = True
        with self.assertRaisesRegex(RuntimeError, 'reuse'):
            fixture.guard()

    def test_committed_real_public_key_matches_product_pin(self):
        self.assertEqual(hashlib.sha256(KEY_BYTES).hexdigest(), SOURCES['rpmfusion-free'].key_sha256)

    @patch.object(fixture.Path, 'is_symlink', return_value=False)
    @patch.object(fixture.Path, 'exists', return_value=False)
    @patch.object(fixture.Path, 'open')
    def test_missing_key_stages_exact_bundled_pin_exclusively(self, open_file, _exists, _symlink):
        fixture.prepare_staged_key()
        open_file.assert_called_once_with('xb')
        open_file.return_value.__enter__.return_value.write.assert_called_once_with(KEY_BYTES)

    @patch('e2e.tests.source_fixture_key.KEY_BYTES', b'changed-bundled-key')
    @patch.object(fixture.Path, 'is_symlink', return_value=False)
    @patch.object(fixture.Path, 'exists', return_value=False)
    @patch.object(fixture.Path, 'open')
    def test_changed_bundled_pin_is_rejected_before_write(self, open_file, _exists, _symlink):
        with self.assertRaisesRegex(ValueError, 'Bundled source key'):
            fixture.prepare_staged_key()
        open_file.assert_not_called()

    @patch.object(fixture.Path, 'is_symlink', return_value=False)
    @patch.object(fixture.Path, 'exists', return_value=True)
    @patch.object(fixture.Path, 'read_bytes', return_value=b'existing-untrusted-key')
    @patch.object(fixture.Path, 'open')
    def test_existing_untrusted_key_is_preserved_and_rejected(self, open_file, _read, _exists, _symlink):
        with self.assertRaisesRegex(ValueError, 'Staged source key'):
            fixture.prepare_staged_key()
        open_file.assert_not_called()

    @patch.object(fixture.Path, 'is_symlink', return_value=False)
    @patch.object(fixture.Path, 'exists', return_value=True)
    @patch.object(fixture.Path, 'read_bytes', return_value=KEY_BYTES)
    @patch.object(fixture.Path, 'open')
    def test_existing_pinned_key_never_overwritten(self, open_file, _read, _exists, _symlink):
        fixture.prepare_staged_key()
        open_file.assert_not_called()

    @patch.object(fixture.Path, 'is_symlink', return_value=True)
    @patch.object(fixture.Path, 'open')
    def test_key_symlink_cannot_redirect_fixture_write(self, open_file, _symlink):
        with self.assertRaisesRegex(ValueError, 'symlink'):
            fixture.prepare_staged_key()
        open_file.assert_not_called()

    @patch.object(fixture.Path, 'read_bytes')
    def test_staged_fetch_cannot_serve_an_arbitrary_url(self, read):
        with self.assertRaisesRegex(ValueError, 'unregistered'):
            fixture.staged_fetch('https://example.invalid/key')
        read.assert_not_called()

    @patch.object(fixture.Path, 'read_bytes', return_value=b'wrong-key')
    def test_staged_key_pin_is_checked_without_trust_override(self, _read):
        with self.assertRaisesRegex(ValueError, 'immutable trust'):
            fixture.staged_fetch(SOURCES['rpmfusion-free'].key_url)

    def test_closed_executor_refuses_arbitrary_commands(self):
        executor = fixture.ClosedExecutor(Path('/unexecuted/installroot'))
        for vector in (['sh', '-c', 'true'], ['rpm', '-e', 'bash'], ['/tmp/loofi-setup-sources', 'preview']):
            with self.assertRaises(ValueError):
                executor.execute(vector)

    def test_mutation_cannot_bypass_action_center(self):
        executor = fixture.ClosedExecutor(Path('/unexecuted/installroot'))
        vector = ['/usr/bin/loofi-setup-sources', 'apply', '--source-id', 'rpmfusion-free', '--scope', 'system',
                  '--snapshot-digest', '0' * 64]
        with self.assertRaisesRegex(ValueError, 'OperationController'):
            executor.execute(vector, action_id='enable-rpm-fusion')
        with self.assertRaisesRegex(ValueError, 'identity mismatch'):
            executor.execute(vector, action_id='install-multimedia-codecs', authority='action_center')

    @patch('services.software.setup_sources_helper.main')
    def test_native_source_entrypoint_receives_only_closed_vector(self, main):
        def run(args):
            print(json.dumps({'available': True}))
            return 0
        main.side_effect = run
        executor = fixture.ClosedExecutor(Path('/unexecuted/installroot'))
        vector = ['/usr/bin/loofi-setup-sources', 'state', '--source-id', 'rpmfusion-free', '--scope', 'system']
        result = executor.execute(vector)
        self.assertTrue(result.success)
        main.assert_called_once_with(vector[1:])
        self.assertEqual(executor.calls[0]['vector'], vector)

    @patch('services.software.rpm_transaction_helper.main')
    def test_codec_native_entrypoint_requires_fixed_recipe_and_action(self, main):
        main.side_effect = lambda args: 0
        executor = fixture.ClosedExecutor(Path('/unexecuted/installroot'))
        vector = ['/usr/bin/loofi-rpm-transaction', 'preview', *request_args('codecs', CODEC_PACKAGES, '', True)]
        self.assertTrue(executor.execute(vector).success)
        main.assert_called_once_with(vector[1:])
        with self.assertRaisesRegex(ValueError, 'fixed codec'):
            executor.execute(['/usr/bin/loofi-rpm-transaction', 'preview', *request_args('install', ('bash',))])

    @patch.object(fixture, 'command', return_value='fixture|fixture-0:1-1.noarch')
    def test_independent_inventory_is_explicitly_installroot_scoped(self, command):
        executor = fixture.ClosedExecutor(Path('/unexecuted/installroot'))
        executor.execute(['rpm', '-qa', '--qf', fixture.INVENTORY_FORMAT])
        command.assert_called_once_with(['rpm', '--root', '/unexecuted/installroot', '-qa', '--qf', fixture.INVENTORY_FORMAT])

    def test_base_adapter_scopes_native_files_before_setup(self):
        native = Mock()

        class Base:
            def load_config(self):
                native.loaded()

            def get_config(self):
                return native.config

            def get_vars(self):
                return native.variables

        module = SimpleNamespace(Base=Base, Goal=object(), GoalJobSettings=object())
        api = (module, object(), object(), object(), object())
        adapted = fixture.scoped_api(api, Path('/isolated/root'), Path('/isolated/repos'))
        base = adapted[0].Base()
        base.load_config()
        native.loaded.assert_called_once_with()
        native.config.get_installroot_option.return_value.set.assert_called_once_with('/isolated/root')
        native.config.get_reposdir_option.return_value.set.assert_called_once_with(['/isolated/repos'])
        self.assertEqual(adapted[1:], api[1:])
        self.assertIs(adapted[0].Goal, module.Goal)

    @patch.object(fixture, 'command', return_value='loofi-e2e-unrelated|loofi-e2e-unrelated-0:1.0-1.noarch')
    @patch.object(fixture.Path, 'write_text')
    def test_codec_case_stops_before_execution_without_separate_consent(self, _write, command):
        controller = Mock()
        controller.prepare.return_value.blocked = False
        executor = Mock()
        with self.assertRaisesRegex(RuntimeError, 'without separate removal consent'):
            fixture.codec_case(controller, executor, Path('/unexecuted/installroot'))
        controller.prepare.assert_called_once_with('install-multimedia-codecs', {'removal_consent': False})
        controller.run.assert_not_called()
        executor.execute.assert_not_called()

    @patch.object(fixture.Path, 'read_text', return_value='Preserve user media and unrelated application data\n')
    @patch.object(fixture.Path, 'write_text')
    @patch.object(fixture, 'command')
    def test_codec_case_records_exact_review_consent_verification_and_preservation(self, command, _write, _read):
        baseline = 'ffmpeg-free|ffmpeg-free-0:1.0-1.noarch\nloofi-e2e-unrelated|loofi-e2e-unrelated-0:1.0-1.noarch'
        after = '\n'.join([f'{name}|{name}-0:1.0-1.noarch' for name in CODEC_PACKAGES]
                          + ['loofi-e2e-unrelated|loofi-e2e-unrelated-0:1.0-1.noarch'])
        command.side_effect = [baseline, baseline, after, '']
        denied = Mock(blocked=True)
        denied.to_dict.return_value = {'blocked': True}
        review = Mock(blocked=False)
        review.plan.policy_decision.facts = {'rpm_transaction': {'operations': [{'name': 'ffmpeg-free', 'action': 'Replaced'}]}}
        review.to_dict.return_value = {'removal_consent': True}
        controller = Mock()
        controller.prepare.side_effect = [denied, review]
        running = SimpleNamespace(status='verifying')
        controller.run.return_value = running
        outcome = Mock(status='succeeded')
        outcome.to_dict.return_value = {'status': 'succeeded'}
        controller.verify.return_value = outcome
        executor = Mock()
        result = fixture.codec_case(controller, executor, Path('/unexecuted/installroot'))
        self.assertTrue(result['data_preserved'])
        self.assertTrue(result['unrelated_preserved'])
        self.assertEqual(result['inventory_after'], after.splitlines())
        self.assertEqual(controller.prepare.call_args_list[1].args[1], {'removal_consent': True})
        controller.verify.assert_called_once_with(running)
        self.assertEqual(controller.run.call_args.kwargs['executor'], executor.execute)


if __name__ == '__main__':
    unittest.main()
