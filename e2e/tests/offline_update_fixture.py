"""Signed inert RPM upgrade and real reboot through the installed Action Center.

All mutation is confined to the marker-checked disposable QEMU guest. Root is
used by the guest harness, independently of the desktop Polkit UI tests.
"""
from __future__ import annotations

import json
import math
import os
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path('/var/tmp/loofi-e2e/offline-update')
REPORT = Path('/var/tmp/loofi-e2e/offline-update-evidence.json')
NAME = 'loofi-e2e-offline-update'
HISTORY_MAX_BYTES = 1024 * 1024
HISTORY_MAX_ITEMS = 4096
HISTORY_INFO_LIMIT = 20


def history_payload(vector: list[str]) -> dict:
    """Read a bounded native history document without product matching code."""
    output = command(vector, timeout=30)
    if len(output.encode()) > HISTORY_MAX_BYTES:
        raise RuntimeError('Independent DNF history exceeds its evidence size limit')
    try:
        value = json.loads(output)
    except (ValueError, TypeError) as error:
        raise RuntimeError('Independent DNF history is malformed') from error
    if not isinstance(value, dict) or not isinstance(value.get('items'), list) or len(value['items']) > HISTORY_MAX_ITEMS:
        raise RuntimeError('Independent DNF history is malformed or exceeds its item limit')
    return value


def history_ids(payload: dict) -> list[int]:
    identifiers = []
    for item in payload['items']:
        identifier = item.get('id') if isinstance(item, dict) else None
        if type(identifier) is not int or identifier <= 0 or identifier in identifiers:
            raise RuntimeError('Independent DNF history contains invalid or duplicate transaction IDs')
        identifiers.append(identifier)
    return identifiers


def history_time(value) -> float:
    if isinstance(value, bool) or not isinstance(value, (float, int)):
        raise RuntimeError('Independent DNF history has an invalid transaction time')
    try:
        number = float(value)
    except (ValueError, OverflowError) as error:
        raise RuntimeError('Independent DNF history has an invalid transaction time') from error
    if not math.isfinite(number) or number < 0:
        raise RuntimeError('Independent DNF history has an invalid transaction time')
    return number


def independent_history(evidence: dict) -> tuple[dict, dict, int]:
    """Require a new successful native transaction containing the exact RPM."""
    before = evidence.get('before_history_ids')
    if not isinstance(before, list) or len(before) > HISTORY_MAX_ITEMS or any(type(item) is not int or item <= 0 for item in before):
        raise RuntimeError('Independent pre-stage history checkpoint is missing or malformed')
    if len(set(before)) != len(before):
        raise RuntimeError('Independent pre-stage history checkpoint contains duplicate IDs')
    started = history_time(evidence['stage']['run'].get('started_at'))
    listing = history_payload(['dnf5', 'history', 'list', '--json'])
    history_ids(listing)
    candidates = []
    successful = {'ok', 'success', 'succeeded'}
    for item in listing['items']:
        time = history_time(item.get('start_time'))
        if item['id'] not in before and time >= started and str(item.get('status', '')).casefold() in successful:
            candidates.append(item)
    targets = {f'{NAME}-2.0-1.noarch', f'{NAME}-0:2.0-1.noarch'}
    for item in sorted(candidates, key=lambda record: record['start_time'], reverse=True)[:HISTORY_INFO_LIMIT]:
        details = history_payload(['dnf5', 'history', 'info', str(item['id']), '--json'])
        history_ids(details)
        matches = [record for record in details['items'] if record['id'] == item['id']]
        if len(matches) != 1:
            continue
        record = matches[0]
        if str(record.get('status', '')).casefold() not in successful:
            continue
        packages = record.get('packages')
        if (not isinstance(packages, list) or len(packages) > HISTORY_MAX_ITEMS
                or any(not isinstance(package, dict) or not isinstance(package.get('nevra'), str)
                       or not isinstance(package.get('action'), str) for package in packages)):
            raise RuntimeError('Independent DNF transaction package details are malformed')
        if any(package.get('nevra') in targets and str(package.get('action', '')).casefold() in {'upgrade', 'install', 'reinstall'}
               for package in packages):
            return listing, details, item['id']
    raise RuntimeError('No new successful independent DNF history transaction proves the exact offline target')


def command(args: list[str], *, timeout: int = 120) -> str:
    result = subprocess.run(args, capture_output=True, text=True, check=True, timeout=timeout,
                            env={**os.environ, 'LC_ALL': 'C'})
    return result.stdout.strip()


def guard() -> None:
    marker = Path('/etc/loofi-e2e-guest')
    if os.geteuid() != 0 or not marker.is_file() or marker.read_text().strip() != 'loofi-fedora-tweaks-e2e':
        raise RuntimeError('Offline qualification requires the dedicated root guest harness')
    if command(['systemd-detect-virt', '--vm']) not in ('qemu', 'kvm'):
        raise RuntimeError('Offline qualification requires QEMU virtualization')
    for key in ('HOME', 'XDG_DATA_HOME', 'XDG_CONFIG_HOME', 'XDG_CACHE_HOME', 'XDG_STATE_HOME'):
        path = ROOT / key.lower()
        path.mkdir(parents=True, exist_ok=True, mode=0o700)
        os.environ[key] = str(path)
    sys.path.insert(0, '/usr/lib/loofi-fedora-tweaks')


def snapshot() -> list[str]:
    return sorted(command(['rpm', '-qa', '--qf', '%{NAME}|%{EVR}|%{ARCH}\\n']).splitlines())


def qualify_application_cycle() -> dict:
    """Exercise the shipped RPM application adapter before the reboot update."""
    from core.actions.operation_controller import OperationController
    controller = OperationController()
    exact = f'{NAME}-0:1.0-1.noarch'
    parameters = {'source': 'fedora', 'package_id': exact, 'repo_id': 'loofi-offline-fixture'}
    baseline = snapshot()
    sentinel = ROOT / 'preserved-user-data.txt'
    preserved = sentinel.read_text()
    report = {'package_id': exact, 'repo_id': parameters['repo_id'], 'operations': []}
    report_path = ROOT.parent / 'application-action-evidence.json'

    def check_state(installed: bool) -> None:
        observed = snapshot()
        unrelated = [item for item in observed if not item.startswith(NAME + '|')]
        if unrelated != baseline or sentinel.read_text() != preserved:
            raise RuntimeError('Application action changed unrelated packages or user data')
        expected = [f'{NAME}|1.0-1|noarch'] if installed else []
        if [item for item in observed if item.startswith(NAME + '|')] != expected:
            raise RuntimeError('Application action did not reach its exact requested RPM state')
        payload = Path(f'/usr/share/{NAME}/version')
        if installed:
            if payload.read_text().strip() != '1':
                raise RuntimeError('Installed RPM payload does not match version 1')
            command(['rpm', '-V', NAME])
        elif payload.exists():
            raise RuntimeError('Application removal left the packaged payload installed')

    check_state(False)
    stale = controller.prepare('install-application', parameters)
    if stale.blocked:
        raise RuntimeError(f'Exact signed fixture installation cannot be reviewed: {stale.plan.to_dict()}')
    for index, action in enumerate(('install-application', 'remove-application', 'install-application')):
        outcome = controller.execute(action, parameters, confirmed=True, accept_no_rollback=True, timeout=180)
        report['operations'].append(outcome.to_dict())
        report_path.write_text(json.dumps(report, indent=2))
        if outcome.status != 'succeeded':
            raise RuntimeError(f'Application fixture operation failed: {outcome.to_dict()}')
        check_state(action == 'install-application')
        if index == 0:
            before_stale = snapshot()
            rejection = controller.confirm(stale, confirmed=True, accept_no_rollback=True)
            report['stale_review'] = rejection.to_dict()
            report_path.write_text(json.dumps(report, indent=2))
            if rejection.status != 'blocked' or rejection.prepared is not None or snapshot() != before_stale:
                raise RuntimeError('An obsolete installation review was not rejected without mutation')
    report.update(unrelated_preserved=True, data_preserved=True)
    report_path.write_text(json.dumps(report, indent=2))
    return report


def prepare() -> None:
    guard()
    if REPORT.exists():
        raise RuntimeError('Refusing to reuse an offline update qualification checkpoint')
    for tool in ('rpmbuild', 'rpmsign', 'gpg', 'createrepo_c', 'dnf5'):
        if not shutil.which(tool):
            raise RuntimeError(f'Disposable guest image lacks required fixture tool: {tool}')
    keyring = ROOT / 'gnupg'
    keyring.mkdir(mode=0o700)
    command(['gpg', '--homedir', str(keyring), '--batch', '--pinentry-mode', 'loopback', '--passphrase', '',
             '--quick-generate-key', 'Loofi offline fixture <offline@example.invalid>', 'rsa2048', 'sign', '0'])
    keys = command(['gpg', '--homedir', str(keyring), '--with-colons', '--list-secret-keys'])
    fingerprint = next(line.split(':')[9] for line in keys.splitlines() if line.startswith('fpr:'))
    os.environ["GNUPGHOME"] = str(keyring)
    public_key = ROOT / 'fixture-key.asc'
    public_key.write_text(command(['gpg', '--homedir', str(keyring), '--armor', '--export', fingerprint]) + '\n')
    command(['rpm', '--import', str(public_key)])
    repo = ROOT / 'repo'
    repo.mkdir()
    for version in (1, 2):
        build = ROOT / f'build-{version}'
        build.mkdir()
        spec = build / 'fixture.spec'
        spec.write_text(f'''Name: {NAME}
Version: {version}.0
Release: 1
Summary: Inert offline update qualification fixture
License: MIT
BuildArch: noarch
%description
Disposable VM update readback fixture, no scripts or dependencies.
%install
mkdir -p %{{buildroot}}/usr/share/{NAME}
printf '{version}\\n' > %{{buildroot}}/usr/share/{NAME}/version
%files
/usr/share/{NAME}/version
''')
        command(['rpmbuild', '-bb', '--define', f'_topdir {build}', str(spec)])
        rpm = next((build / 'RPMS/noarch').glob('*.rpm'))
        command(['rpmsign', '--define', f'_openpgp_sign_id {fingerprint}', '--define', f'_gpg_name {fingerprint}', '--define', f'_gpg_path {keyring}', '--addsign', str(rpm)])
        command(['rpmkeys', '--checksig', str(rpm)])
        shutil.copy2(rpm, repo)
    command(['createrepo_c', str(repo)])
    command(['gpg', '--homedir', str(keyring), '--batch', '--yes', '--armor', '--detach-sign', str(repo / 'repodata/repomd.xml')])
    # The entire overlay is disposable. Disable external repos only after the
    # desktop suite has finished, so --refresh cannot access the network.
    disabled = ROOT / 'original-repos'
    disabled.mkdir()
    for path in Path('/etc/yum.repos.d').glob('*.repo'):
        shutil.move(str(path), disabled / path.name)
    Path('/etc/yum.repos.d/loofi-offline-fixture.repo').write_text(
        f'[loofi-offline-fixture]\nname=Loofi signed offline fixture\nbaseurl=file://{repo}\nenabled=1\ngpgcheck=1\nrepo_gpgcheck=1\ngpgkey=file://{public_key}\n')
    command(['dnf5', '--assumeyes', 'makecache'])
    sentinel = ROOT / 'preserved-user-data.txt'
    sentinel.write_text('Preserve data across the offline update\n')
    application_actions = qualify_application_cycle()
    before = snapshot()
    from core.actions.operation_controller import OperationController
    before_history_ids = history_ids(history_payload(['dnf5', 'history', 'list', '--json']))
    outcome = OperationController().execute('update-fedora-system', confirmed=True, accept_no_rollback=True, timeout=300)
    if outcome.status != 'awaiting_reboot':
        raise RuntimeError(f'Action Center did not stage the offline fixture: {outcome.to_dict()}')
    if snapshot() != before:
        raise RuntimeError('Offline staging changed installed packages before activation')
    REPORT.write_text(json.dumps({'before_boot_id': Path('/proc/sys/kernel/random/boot_id').read_text().strip(),
                                  'before_packages': before, 'signing_fingerprint': fingerprint,
                                  'before_history_ids': before_history_ids,
                                  'stage': outcome.to_dict(), 'preserved_data': sentinel.read_text(), 'application_actions': application_actions}, indent=2))


def activate() -> None:
    guard()
    evidence = json.loads(REPORT.read_text())
    from core.actions.operation_controller import OperationController
    evidence['activation_requested'] = True
    REPORT.write_text(json.dumps(evidence, indent=2))
    outcome = OperationController().execute(
        'activate-fedora-offline-update', {'source_run_id': evidence['stage']['run']['run_id']},
        confirmed=True, accept_no_rollback=True, timeout=90)
    evidence['activation'] = outcome.to_dict()
    REPORT.write_text(json.dumps(evidence, indent=2))
    if outcome.status != 'awaiting_reboot':
        raise RuntimeError(f'Action Center offline activation failed: {outcome.to_dict()}')


def verify() -> None:
    guard()
    evidence = json.loads(REPORT.read_text())
    boot = Path('/proc/sys/kernel/random/boot_id').read_text().strip()
    if boot == evidence['before_boot_id']:
        raise RuntimeError('No actual kernel reboot occurred')
    from core.actions.operation_controller import OperationController
    outcome = OperationController().verify(evidence['stage']['run']['run_id'])
    if outcome.status != 'succeeded':
        raise RuntimeError(f'Post-reboot Action Center verification failed: {outcome.to_dict()}')
    after = snapshot()
    before_unrelated = [line for line in evidence['before_packages'] if not line.startswith(NAME + '|')]
    after_unrelated = [line for line in after if not line.startswith(NAME + '|')]
    if after_unrelated != before_unrelated or f'{NAME}|2.0-1|noarch' not in after:
        raise RuntimeError('Offline update did not preserve unrelated packages or install exact target')
    if (ROOT / 'preserved-user-data.txt').read_text() != evidence['preserved_data']:
        raise RuntimeError('Offline upgrade modified unrelated data')
    command(['rpm', '-V', NAME])
    command(['dnf5', 'check'])
    history, history_info, transaction_id = independent_history(evidence)
    evidence.update(after_boot_id=boot, after_packages=after, verification=outcome.to_dict(),
                    data_preserved=True, history=history, history_info=history_info, matched_history_id=transaction_id, unrelated_preserved=True)
    REPORT.write_text(json.dumps(evidence, indent=2))


if __name__ == '__main__':
    {'prepare': prepare, 'activate': activate, 'verify': verify}[sys.argv[1]]()
