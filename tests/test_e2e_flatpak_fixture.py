"""Safety boundaries for the real guest-only Flatpak integration fixture."""
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from unittest import TestCase
from unittest.mock import patch


SPEC = spec_from_file_location('flatpak_fixture', Path(__file__).resolve().parents[1] / 'e2e/tests/flatpak_fixture.py')
fixture = module_from_spec(SPEC)
SPEC.loader.exec_module(fixture)


class TestFlatpakFixtureGuard(TestCase):
    def test_indented_flatpak_info_reads_target_commit_date_before_history(self):
        commit = 'b' * 64
        details = ('            ID: org.loofi.E2E.Selected\n'
                   f'        Commit: {commit}\n'
                   '          Date: 2026-10-16 17:26:07 +0000\n'
                   '       History:\n'
                   f'        Commit: {"a" * 64}\n'
                   '          Date: 2026-10-16 17:21:07 +0000\n')
        self.assertEqual(fixture.parse_commit_timestamp(details, commit), 1792171567)
        with self.assertRaises(RuntimeError):
            fixture.parse_commit_timestamp(details, 'c' * 64)

    @patch.object(fixture.Path, 'is_file', return_value=False)
    @patch.object(fixture, 'command')
    def test_host_without_guest_marker_never_runs_commands(self, command, is_file):
        with self.assertRaisesRegex(RuntimeError, 'dedicated root guest'):
            fixture.prepare('test-user')
        command.assert_not_called()

    @patch.object(fixture.Path, 'is_file', return_value=True)
    @patch.object(fixture.Path, 'read_text', return_value='loofi-fedora-tweaks-e2e\n')
    @patch.object(fixture.os, 'geteuid', return_value=1000)
    @patch.object(fixture, 'command')
    def test_unprivileged_guest_cannot_prepare_shared_installations(self, command, uid, read_text, is_file):
        with self.assertRaisesRegex(RuntimeError, 'dedicated root guest'):
            fixture.prepare('test-user')
        command.assert_not_called()

    @patch.object(fixture.Path, 'is_file', return_value=True)
    @patch.object(fixture.Path, 'read_text', return_value='loofi-fedora-tweaks-e2e\n')
    @patch.object(fixture.os, 'geteuid', return_value=0)
    @patch.object(fixture, 'command', return_value='docker')
    def test_root_marker_without_qemu_is_rejected_before_setup(self, command, uid, read_text, is_file):
        with self.assertRaisesRegex(RuntimeError, 'QEMU virtualization'):
            fixture.prepare('test-user')
        command.assert_called_once_with(['systemd-detect-virt', '--vm'])
