"""Offline qualification remains VM-only and uses the installed Action Center."""
import copy
import json
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from e2e.tests import offline_update_fixture as fixture


class TestIndependentOfflineHistory(unittest.TestCase):
    def setUp(self):
        self.evidence = {'before_history_ids': [1], 'stage': {'run': {'run_id': 'offline-run', 'started_at': 100.0}}}
        self.listing = {'items': [{'id': 2, 'start_time': 101, 'status': 'Success'}]}
        self.details = {'items': [{'id': 2, 'status': 'Success',
                                   'packages': [{'action': 'Upgrade', 'nevra': f'{fixture.NAME}-2.0-1.noarch'}]}]}

    @patch.object(fixture, 'command')
    def test_exact_new_successful_transaction_info_is_retained(self, command):
        for action in ('Upgrade', 'Install', 'Reinstall'):
            for epoch in ('', '0:'):
                with self.subTest(action=action, epoch=epoch):
                    details = copy.deepcopy(self.details)
                    details['items'][0]['packages'][0] = {'action': action, 'nevra': f'{fixture.NAME}-{epoch}2.0-1.noarch'}
                    command.side_effect = [json.dumps(self.listing), json.dumps(details)]
                    listing, observed, identifier = fixture.independent_history(self.evidence)
                    self.assertEqual(identifier, 2)
                    self.assertEqual(listing, self.listing)
                    self.assertEqual(observed, details)
                    self.assertEqual(command.call_args.args[0], ['dnf5', 'history', 'info', '2', '--json'])
                    self.assertEqual(command.call_args.kwargs['timeout'], 30)

    @patch.object(fixture, 'command')
    def test_empty_failed_old_and_pre_stage_history_do_not_prove_success(self, command):
        cases = [[], [{'id': 1, 'start_time': 101, 'status': 'Success'}],
                 [{'id': 2, 'start_time': 99, 'status': 'Success'}], [{'id': 2, 'start_time': 101, 'status': 'Error'}]]
        for items in cases:
            with self.subTest(items=items):
                command.reset_mock()
                command.return_value = json.dumps({'items': items})
                with self.assertRaisesRegex(RuntimeError, 'No new successful independent'):
                    fixture.independent_history(self.evidence)
                command.assert_called_once_with(['dnf5', 'history', 'list', '--json'], timeout=30)

    @patch.object(fixture, 'command')
    def test_nonfinite_malformed_times_and_nonpositive_or_bool_ids_rejected(self, command):
        for field, values in (('id', [True, 0, -1, '2', None]),
                              ('start_time', [float('nan'), float('inf'), -1, None, True, '101'])):
            for value in values:
                with self.subTest(field=field, value=value):
                    listing = copy.deepcopy(self.listing)
                    listing['items'][0][field] = value
                    command.return_value = json.dumps(listing)
                    with self.assertRaises(RuntimeError):
                        fixture.independent_history(self.evidence)

    @patch.object(fixture, 'command')
    def test_malformed_empty_wrong_id_failed_info_and_wrong_package_are_rejected(self, command):
        cases = [{'items': []}, {'items': [{'id': 3, 'status': 'Success', 'packages': []}]},
                 {'items': [{'id': True}]}, {'items': [{'id': 2, 'status': 'Error', 'packages': []}]},
                 {'items': [{'id': 2, 'status': 'Success', 'packages': None}]}]
        for change in ({'nevra': f'{fixture.NAME}-1.0-1.noarch'}, {'nevra': f'{fixture.NAME}-1:2.0-1.noarch'},
                       {'nevra': f'{fixture.NAME}-2.0-1.x86_64'}, {'nevra': 'unrelated-2.0-1.noarch'},
                       {'action': 'Remove'}, {'action': 'UpgradeInvalid'}, {'nevra': []}):
            details = copy.deepcopy(self.details)
            details['items'][0]['packages'][0].update(change)
            cases.append(details)
        for details in cases:
            with self.subTest(details=details):
                command.side_effect = [json.dumps(self.listing), json.dumps(details)]
                with self.assertRaises(RuntimeError):
                    fixture.independent_history(self.evidence)

    @patch.object(fixture, 'command')
    def test_missing_or_duplicate_pre_stage_checkpoint_is_rejected_before_probes(self, command):
        for before in (None, [True], [0], [1, 1], '1'):
            with self.subTest(before=before):
                evidence = {**self.evidence, 'before_history_ids': before}
                with self.assertRaises(RuntimeError):
                    fixture.independent_history(evidence)
        command.assert_not_called()

    @patch.object(fixture, 'command')
    def test_history_json_shape_and_size_are_bounded(self, command):
        for output in ('not json', '[]', '{}', '{"items":null}', ' ' * (fixture.HISTORY_MAX_BYTES + 1),
                       json.dumps({'items': [{'id': index + 1} for index in range(fixture.HISTORY_MAX_ITEMS + 1)]})):
            with self.subTest(length=len(output)):
                command.return_value = output
                with self.assertRaises(RuntimeError):
                    fixture.history_payload(['dnf5', 'history', 'list', '--json'])

    @patch.object(fixture, 'command')
    def test_only_twenty_new_transaction_details_are_probed(self, command):
        listing = {'items': [{'id': index + 2, 'start_time': 101 + index, 'status': 'Success'} for index in range(25)]}
        command.side_effect = [json.dumps(listing)] + [json.dumps({'items': []})] * fixture.HISTORY_INFO_LIMIT
        with self.assertRaisesRegex(RuntimeError, 'No new successful independent'):
            fixture.independent_history(self.evidence)
        self.assertEqual(command.call_count, fixture.HISTORY_INFO_LIMIT + 1)

    @patch('core.actions.operation_controller.OperationController')
    @patch.object(fixture.Path, 'read_text', return_value='new-boot')
    @patch.object(fixture, 'command')
    @patch.object(fixture, 'snapshot')
    @patch.object(fixture, 'guard')
    @patch.object(fixture, 'ROOT')
    @patch.object(fixture, 'REPORT')
    def test_product_success_with_empty_history_does_not_write_successful_evidence(
        self, report, root, _guard, snapshot, command, _read, controller,
    ):
        evidence = {**self.evidence, 'before_boot_id': 'old-boot', 'before_packages': ['unrelated|1-1|noarch', f'{fixture.NAME}|1.0-1|noarch'],
                    'preserved_data': 'preserved'}
        report.read_text.return_value = json.dumps(evidence)
        root.__truediv__.return_value.read_text.return_value = 'preserved'
        controller.return_value.verify.return_value = SimpleNamespace(status='succeeded', to_dict=lambda: {'status': 'succeeded'})
        snapshot.return_value = ['unrelated|1-1|noarch', f'{fixture.NAME}|2.0-1|noarch']
        command.side_effect = ['', '', json.dumps({'items': []})]
        with self.assertRaisesRegex(RuntimeError, 'No new successful independent'):
            fixture.verify()
        controller.return_value.verify.assert_called_once_with('offline-run')
        report.write_text.assert_not_called()

    @patch('core.actions.operation_controller.OperationController')
    @patch.object(fixture.Path, 'read_text', return_value='new-boot')
    @patch.object(fixture, 'command')
    @patch.object(fixture, 'snapshot')
    @patch.object(fixture, 'guard')
    @patch.object(fixture, 'ROOT')
    @patch.object(fixture, 'REPORT')
    def test_successful_reboot_evidence_stores_full_independently_matched_history_info(
        self, report, root, _guard, snapshot, command, _read, controller,
    ):
        evidence = {**self.evidence, 'before_boot_id': 'old-boot', 'before_packages': ['unrelated|1-1|noarch', f'{fixture.NAME}|1.0-1|noarch'],
                    'preserved_data': 'preserved'}
        report.read_text.return_value = json.dumps(evidence)
        root.__truediv__.return_value.read_text.return_value = 'preserved'
        controller.return_value.verify.return_value = SimpleNamespace(status='succeeded', to_dict=lambda: {'status': 'succeeded'})
        snapshot.return_value = ['unrelated|1-1|noarch', f'{fixture.NAME}|2.0-1|noarch']
        details = {**self.details, 'extra-native-field': {'retained': True}}
        command.side_effect = ['', '', json.dumps(self.listing), json.dumps(details)]
        fixture.verify()
        report.write_text.assert_called_once()
        saved = json.loads(report.write_text.call_args.args[0])
        self.assertEqual(saved['matched_history_id'], 2)
        self.assertEqual(saved['history_info'], details)
        self.assertEqual(saved['history'], self.listing)
        self.assertTrue(saved['unrelated_preserved'])
        self.assertTrue(saved['data_preserved'])


class TestOfflineUpdateFixture(unittest.TestCase):
    @patch.object(fixture.os, 'geteuid', return_value=1000)
    def test_unprivileged_host_is_rejected_before_commands(self, _uid):
        with self.assertRaisesRegex(RuntimeError, 'dedicated root guest'):
            fixture.guard()

    @patch.object(fixture.Path, 'read_text', return_value='loofi-fedora-tweaks-e2e')
    @patch.object(fixture.Path, 'is_file', return_value=True)
    @patch.object(fixture.os, 'geteuid', return_value=0)
    @patch.object(fixture, 'command', return_value='none')
    def test_marker_alone_cannot_authorize_host_mutation(self, command, _uid, _exists, _read):
        with self.assertRaisesRegex(RuntimeError, 'QEMU'):
            fixture.guard()
        command.assert_called_once_with(['systemd-detect-virt', '--vm'])

    @patch.object(fixture.Path, 'read_text', return_value='same')
    @patch.object(fixture, 'command', return_value='')
    @patch.object(fixture, 'snapshot', return_value=['unrelated|1-1|noarch'])
    @patch.object(fixture, 'guard')
    @patch.object(fixture, 'REPORT')
    def test_missing_reboot_cannot_be_reported_verified(self, report, _guard, _snapshot, _command, _read):
        report.read_text.return_value = '{"before_boot_id":"same"}'
        with self.assertRaisesRegex(RuntimeError, 'No actual kernel reboot'):
            fixture.verify()
        report.write_text.assert_not_called()

    @patch('core.actions.operation_controller.OperationController')
    @patch.object(fixture, 'guard')
    @patch.object(fixture, 'REPORT')
    def test_activation_uses_exact_prepared_action_run(self, report, _guard, controller):
        report.read_text.return_value = '{"stage":{"run":{"run_id":"reviewed-run"}}}'
        outcome = controller.return_value.execute.return_value
        outcome.status = 'awaiting_reboot'
        outcome.to_dict.return_value = {'status': 'awaiting_reboot'}
        fixture.activate()
        controller.return_value.execute.assert_called_once_with(
            'activate-fedora-offline-update', {'source_run_id': 'reviewed-run'},
            confirmed=True, accept_no_rollback=True, timeout=90)
        self.assertEqual(report.write_text.call_count, 2)

    @patch('core.actions.operation_controller.OperationController')
    @patch.object(fixture, 'command')
    @patch.object(fixture, 'snapshot')
    @patch.object(fixture, 'Path')
    @patch.object(fixture, 'ROOT')
    def test_application_cycle_uses_exact_signed_identity_and_rejects_stale_review(
        self, root, path, snapshot, command, controller,
    ):
        from types import SimpleNamespace
        absent = ['unrelated|1-1|noarch']
        present = [*absent, f'{fixture.NAME}|1.0-1|noarch']
        snapshot.side_effect = [absent, absent, present, present, present, absent, present]
        root.__truediv__.return_value.read_text.return_value = 'preserved data'
        path.return_value.read_text.return_value = '1'
        path.return_value.exists.return_value = False
        controller.return_value.prepare.return_value.blocked = False
        rejection = SimpleNamespace(status='blocked', prepared=None, to_dict=lambda: {'status': 'blocked'})
        controller.return_value.confirm.return_value = rejection
        controller.return_value.execute.side_effect = [
            SimpleNamespace(status='succeeded', to_dict=lambda action=action: {'status': 'succeeded', 'action_id': action})
            for action in ('install-application', 'remove-application', 'install-application')
        ]
        result = fixture.qualify_application_cycle()
        self.assertTrue(result['unrelated_preserved'])
        self.assertTrue(result['data_preserved'])
        self.assertEqual(result['stale_review']['status'], 'blocked')
        self.assertEqual(controller.return_value.execute.call_count, 3)
        expected = {'source': 'fedora', 'package_id': f'{fixture.NAME}-0:1.0-1.noarch', 'repo_id': 'loofi-offline-fixture'}
        for call in controller.return_value.execute.call_args_list:
            self.assertEqual(call.args[1], expected)
        self.assertEqual(command.call_count, 2)
