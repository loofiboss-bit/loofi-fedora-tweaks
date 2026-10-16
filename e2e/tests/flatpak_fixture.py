"""Synthetic offline Flatpaks, created only by the disposable guest's root runner."""
from __future__ import annotations

from datetime import datetime, timezone
import json
import os
import platform
import pwd
import re
import subprocess
import time
from pathlib import Path

ROOT = Path('/var/tmp/loofi-e2e/flatpak-fixture')
APP = 'org.loofi.E2E.Selected'
UNRELATED = 'org.loofi.E2E.Unrelated'
RUNTIME = 'org.loofi.E2E.Platform'
REMOTE = 'loofi-e2e-local'
NAMED = 'loofi-e2e-fixture'
INSTALLATIONS = ('user', 'system', NAMED)
SOURCE = '/usr/lib/loofi-fedora-tweaks'


def command(arguments: list[str], *, user: str | None = None) -> str:
    prefix = ['runuser', '--user', user, '--'] if user else []
    result = subprocess.run([*prefix, *arguments], env={**os.environ, 'LC_ALL': 'C'},
                            capture_output=True, text=True, timeout=90, check=False)
    if result.returncode:
        raise RuntimeError(f'Guest Flatpak fixture command failed: {arguments[:3]}: {result.stderr[-2000:]}')
    return result.stdout.strip()


def scope(installation: str) -> str:
    return '--' + installation if installation in ('user', 'system') else '--installation=' + installation


def ref(identifier: str, *, runtime: bool = False) -> str:
    return f'{"runtime" if runtime else "app"}/{identifier}/{platform.machine()}/stable'


def parse_commit_timestamp(details: str, commit: str) -> int:
    reported_commit = re.search(r'^[ \t]*Commit:[ \t]*([0-9a-f]{64})[ \t]*$', details, re.MULTILINE)
    timestamp = re.search(r'^[ \t]*Date:[ \t]*(.+)$', details, re.MULTILINE)
    if not reported_commit or reported_commit.group(1) != commit or not timestamp:
        raise RuntimeError('Could not read the fixture commit timestamp from Flatpak.')
    try:
        return int(datetime.strptime(timestamp.group(1).strip(), '%Y-%m-%d %H:%M:%S %z').timestamp())
    except ValueError as error:
        raise RuntimeError('Could not parse the fixture commit timestamp.') from error


def prepare(user_name: str) -> None:
    marker = Path('/etc/loofi-e2e-guest')
    if not marker.is_file() or marker.read_text().strip() != 'loofi-fedora-tweaks-e2e' or os.geteuid() != 0:
        raise RuntimeError('Flatpak fixture setup requires the dedicated root guest runner')
    if command(['systemd-detect-virt', '--vm']) not in ('qemu', 'kvm'):
        raise RuntimeError('Flatpak fixture setup requires QEMU virtualization')
    # The offline guest must contain these optional product capabilities. Never
    # silently skip the integration or install packages from the network here.
    command(['/usr/bin/python3', '-c', "import gi; gi.require_version('Flatpak', '1.0'); from gi.repository import Flatpak"])
    user = pwd.getpwnam(user_name)
    ROOT.mkdir(mode=0o755)
    # Ephemeral signing identity for this guest only; never export its secret key.
    gpg_home = ROOT / 'gnupg'
    gpg_home.mkdir(mode=0o700)
    command(['gpg', '--homedir', str(gpg_home), '--batch', '--pinentry-mode', 'loopback', '--passphrase', '',
             '--quick-generate-key', 'Loofi E2E fixture <fixture@example.invalid>', 'rsa2048', 'sign', '0'])
    keys = command(['gpg', '--homedir', str(gpg_home), '--with-colons', '--list-secret-keys'])
    signing_key = next(line.split(':')[9] for line in keys.splitlines() if line.startswith('fpr:'))
    public_key = ROOT / 'fixture-key.asc'
    public_key.write_text(command(['gpg', '--homedir', str(gpg_home), '--armor', '--export', signing_key]) + '\n')
    config = Path('/etc/flatpak/installations.d/loofi-e2e-fixture.conf')
    if config.exists():
        raise RuntimeError('Fixture named installation unexpectedly exists in the clean overlay')
    config.parent.mkdir(parents=True, exist_ok=True)
    config.write_text('[Installation "loofi-e2e-fixture"]\nPath=/var/lib/loofi-e2e-flatpak\nDisplayName=Loofi E2E fixture\n')
    commits: dict[str, dict[str, str]] = {}
    commit_timestamps: dict[str, dict[str, int]] = {}
    base_timestamp = int(time.time()) - 600
    timestamps = {
        '1': datetime.fromtimestamp(base_timestamp, timezone.utc).isoformat(timespec='seconds').replace('+00:00', 'Z'),
        '2': datetime.fromtimestamp(base_timestamp + 300, timezone.utc).isoformat(timespec='seconds').replace('+00:00', 'Z'),
    }
    for version in ('1', '2'):
        commits[version] = {}
        commit_timestamps[version] = {}
        for identifier in (RUNTIME, APP, UNRELATED):
            build = ROOT / f'{identifier}-{version}'
            (build / 'files').mkdir(parents=True)
            (build / 'files' / 'version.txt').write_text(version)
            runtime = identifier == RUNTIME
            section = 'Runtime' if runtime else 'Application'
            metadata = f'[{section}]\nname={identifier}\nruntime={RUNTIME}/{platform.machine()}/stable\nsdk={RUNTIME}/{platform.machine()}/stable\n'
            (build / 'metadata').write_text(metadata)
            if not runtime:
                (build / 'export').mkdir()
            arguments = ['flatpak', 'build-export', '--files=files', '--disable-sandbox',
                         '--timestamp=' + timestamps[version], '--gpg-homedir=' + str(gpg_home), '--gpg-sign=' + signing_key]
            if runtime:
                arguments.append('--runtime')
            command([*arguments, str(ROOT / 'repo'), str(build), 'stable'])
            full_ref = ref(identifier, runtime=runtime)
            # build-export prints diagnostics; use the repository readback as
            # the independent expected commit rather than parsing its output.
            commit = (ROOT / 'repo/refs/heads' / full_ref).read_text().strip()
            commits[version][full_ref] = commit
        if version == '1':
            for installation in INSTALLATIONS:
                invoke_user = user_name if installation == 'user' else None
                command(['flatpak', scope(installation), 'remote-add', '--gpg-import=' + str(public_key), REMOTE,
                         (ROOT / 'repo').as_uri()], user=invoke_user)
                for identifier in (RUNTIME, APP, UNRELATED):
                    command(['flatpak', scope(installation), 'install', '--noninteractive', REMOTE,
                             ref(identifier, runtime=identifier == RUNTIME)], user=invoke_user)
    for version, refs in commits.items():
        commit_timestamps[version] = {}
        for full_ref, commit in refs.items():
            details = command(['flatpak', '--system', 'remote-info', '--commit=' + commit,
                               '--log', REMOTE, full_ref])
            commit_timestamps[version][full_ref] = parse_commit_timestamp(details, commit)
    (ROOT / 'commits.json').write_text(json.dumps(commits, indent=2))
    (ROOT / 'timestamps.json').write_text(json.dumps(timestamps, indent=2))
    (ROOT / 'commit-timestamps.json').write_text(json.dumps(commit_timestamps, indent=2))
    sentinel = Path(user.pw_dir) / '.var/app' / APP / 'loofi-e2e-sentinel'
    sentinel.parent.mkdir(parents=True, exist_ok=True)
    sentinel.write_text('Preserve app data across scoped updates\n')
    for path in (sentinel.parent.parent.parent, sentinel.parent.parent, sentinel.parent, sentinel):
        os.chown(path, user.pw_uid, user.pw_gid)
