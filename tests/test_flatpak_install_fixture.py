"""The signed guest fixture exposes first-install refs without preinstalling them."""
import hashlib
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from e2e.tests import flatpak_fixture as fixture


class TestFlatpakInstallFixture(unittest.TestCase):
    @patch.object(fixture.os, 'geteuid', return_value=1000)
    @patch.object(fixture, 'command')
    def test_host_rejected_before_any_command(self, command, _uid):
        with self.assertRaisesRegex(RuntimeError, 'dedicated root guest'):
            fixture.prepare('fixture-user')
        command.assert_not_called()

    @patch.object(fixture.os, 'chown')
    @patch.object(fixture.pwd, 'getpwnam')
    @patch.object(fixture.os, 'geteuid', return_value=0)
    @patch.object(fixture, 'command')
    @patch.object(fixture, 'Path')
    @patch.object(fixture, 'ROOT')
    def test_signed_versions_export_new_app_but_only_original_matrix_is_installed(
        self, mocked_root, path, command, _uid, user, _chown,
    ):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / 'fixture'
            home = Path(directory) / 'home'
            home.mkdir()
            marker = Path(directory) / 'marker'
            marker.write_text('loofi-fedora-tweaks-e2e')
            config = Path(directory) / 'config' / 'installation.conf'
            path.side_effect = lambda value: marker if str(value) == '/etc/loofi-e2e-guest' else (
                config if str(value).startswith('/etc/flatpak/installations.d/') else Path(value))
            mocked_root.mkdir.side_effect = lambda **kwargs: root.mkdir(**kwargs)
            mocked_root.__truediv__.side_effect = lambda value: root / value
            user.return_value = SimpleNamespace(pw_dir=str(home), pw_uid=1000, pw_gid=1000)
            exports = []

            def run(arguments, *, user=None):
                if arguments[0] == 'systemd-detect-virt':
                    return 'qemu'
                if '--list-secret-keys' in arguments:
                    return 'fpr:::::::::0123456789ABCDEF:'
                if 'build-export' in arguments:
                    build = Path(arguments[-2])
                    identifier, version = build.name.rsplit('-', 1)
                    full_ref = fixture.ref(identifier, runtime='--runtime' in arguments)
                    destination = root / 'repo/refs/heads' / full_ref
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    destination.write_text(hashlib.sha256((identifier + version).encode()).hexdigest())
                    exports.append((identifier, version, arguments))
                if 'remote-info' in arguments:
                    commit = next(item.split('=', 1)[1] for item in arguments if item.startswith('--commit='))
                    return f'Commit: {commit}\nDate: 2026-10-20 12:00:00 +0000'
                return ''

            command.side_effect = run
            fixture.prepare('fixture-user')
            self.assertEqual({(identifier, version) for identifier, version, _ in exports}, {
                (identifier, version) for identifier in fixture.EXPORTED_IDENTIFIERS for version in ('1', '2')})
            for _, _, arguments in exports:
                self.assertTrue(any(item.startswith('--gpg-sign=') for item in arguments))
                self.assertTrue(any(item.startswith('--gpg-homedir=') for item in arguments))
            installs = [call for call in command.call_args_list if 'install' in call.args[0]]
            self.assertEqual(len(installs), 3 * len(fixture.INSTALLATIONS))
            for installation in fixture.INSTALLATIONS:
                scoped = [call for call in installs if fixture.scope(installation) in call.args[0]]
                self.assertEqual({call.args[0][-1] for call in scoped}, {
                    fixture.ref(identifier, runtime=identifier == fixture.RUNTIME) for identifier in fixture.INITIAL_IDENTIFIERS})
                self.assertTrue(all(call.kwargs.get('user') == ('fixture-user' if installation == 'user' else None)
                                    for call in scoped))
            import json
            commits = json.loads((root / 'commits.json').read_text())
            selected = fixture.ref(fixture.FIRST_INSTALL)
            self.assertNotEqual(commits['1'][selected], commits['2'][selected])
            self.assertTrue((home / '.var/app' / fixture.APP / 'loofi-e2e-sentinel').is_file())
