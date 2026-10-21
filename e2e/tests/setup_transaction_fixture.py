"""Native source/codec qualification, exclusively in a disposable QEMU guest.

The source trust registry is unchanged. Only its immutable key download is
served from staged bytes. Codec packages are signed inert fixtures in a native
libdnf5 installroot; they never replace the guest's actual media stack.
"""
from __future__ import annotations

from contextlib import ExitStack, contextmanager, redirect_stdout
import hashlib
import io
import json
import os
from pathlib import Path
import select
import shutil
import subprocess
import sys
from types import SimpleNamespace
from unittest.mock import patch

ROOT = Path('/var/tmp/loofi-e2e/setup-transactions')
REPORT = ROOT / 'evidence.json'
MARKER = Path('/etc/loofi-e2e-guest')
INVENTORY_FORMAT = '%{NAME}|%{NAME}-%{EPOCHNUM}:%{VERSION}-%{RELEASE}.%{ARCH}\\n'


def command(args: list[str], *, timeout: int = 120) -> str:
    return subprocess.run(args, check=True, capture_output=True, text=True,
                          timeout=timeout, env={**os.environ, 'LC_ALL': 'C'}).stdout.strip()


@contextmanager
def competing_file_lock(path: Path):
    """Hold the actual helper's flock in an independently scheduled process."""
    code = ('import fcntl, sys; '
            'lock = open(sys.argv[1], "a"); '
            'fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB); '
            'print("locked", flush=True); sys.stdin.read()')
    process = subprocess.Popen(['/usr/bin/python3', '-c', code, str(path)],
                               stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    try:
        ready, _, _ = select.select([process.stdout], [], [], 10)
        if not ready or process.stdout.readline().strip() != 'locked':
            raise RuntimeError('Competing lock process did not acquire the native helper lock')
        yield process.pid
    finally:
        process.terminate()
        try:
            process.communicate(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()
            process.communicate(timeout=10)


def guard() -> None:
    if os.geteuid() != 0 or not MARKER.is_file() or MARKER.read_text().strip() != 'loofi-fedora-tweaks-e2e':
        raise RuntimeError('Setup qualification requires the dedicated root guest harness')
    if command(['systemd-detect-virt', '--vm']) not in ('qemu', 'kvm'):
        raise RuntimeError('Setup qualification requires QEMU virtualization')
    if REPORT.exists():
        raise RuntimeError('Refusing to reuse a setup qualification checkpoint')
    ROOT.mkdir(parents=True, exist_ok=True, mode=0o700)
    for name in ('HOME', 'XDG_DATA_HOME', 'XDG_CONFIG_HOME', 'XDG_STATE_HOME', 'XDG_CACHE_HOME'):
        path = ROOT / name.lower()
        path.mkdir(mode=0o700, exist_ok=True)
        os.environ[name] = str(path)
    sys.path.insert(0, '/usr/lib/loofi-fedora-tweaks')


def staged_fetch(url: str) -> bytes:
    from services.software.setup_sources import SOURCES
    definition = SOURCES['rpmfusion-free']
    if url != definition.key_url:
        raise ValueError('Fixture refuses an unregistered download')
    data = (ROOT / 'rpmfusion-free-key.asc').read_bytes()
    if hashlib.sha256(data).hexdigest() != definition.key_sha256:
        raise ValueError('Staged source key differs from the immutable trust definition')
    return data


def prepare_staged_key() -> None:
    """Stage the bundled public fixture exclusively, after the guest guard."""
    from services.software.setup_sources import SOURCES
    definition = SOURCES['rpmfusion-free']
    path = ROOT / 'rpmfusion-free-key.asc'
    if path.is_symlink():
        raise ValueError('Fixture key must not be a symlink')
    if path.exists():
        staged_fetch(definition.key_url)
        return
    if __package__:
        from .source_fixture_key import KEY_BYTES
    else:
        from source_fixture_key import KEY_BYTES
    if hashlib.sha256(KEY_BYTES).hexdigest() != definition.key_sha256:
        raise ValueError('Bundled source key differs from the immutable trust definition')
    with path.open('xb') as destination:
        destination.write(KEY_BYTES)


class ClosedExecutor:
    """Allow only exact validated helper vectors and independent inventory."""

    def __init__(self, installroot: Path):
        self.installroot = installroot
        self.calls: list[dict] = []

    def execute(self, vector, **options):
        from core.executor.action_result import ActionResult
        from services.software import rpm_transaction_helper as rpm_helper
        from services.software import setup_sources_helper as source_helper
        from services.software.rpm_transactions import parse_args, trusted_helpers
        from services.software.setup_sources import trusted_helpers as source_helpers, validate_helper_args
        vector = list(vector)
        mutating = len(vector) > 1 and vector[1] == 'apply'
        if mutating and options.get('authority') != 'action_center':
            raise ValueError('Fixture mutation requires OperationController authority')
        if vector and vector[0] in source_helpers() and validate_helper_args(vector[1:]):
            if vector[3:6] != ['rpmfusion-free', '--scope', 'system']:
                raise ValueError('Fixture permits only RPM Fusion Free system setup')
            if mutating and options.get('action_id') != 'enable-rpm-fusion':
                raise ValueError('Source action identity mismatch')
            function = source_helper.main
        elif vector and vector[0] in trusted_helpers():
            _mode, operation, packages, repo, _consent, _digest = parse_args(vector[1:])
            from services.software.setup_sources import CODEC_PACKAGES
            if operation != 'codecs' or packages != CODEC_PACKAGES or repo:
                raise ValueError('Fixture permits only the fixed codec recipe')
            if mutating and options.get('action_id') != 'install-multimedia-codecs':
                raise ValueError('Codec action identity mismatch')
            function = rpm_helper.main
        elif vector == ['rpm', '-qa', '--qf', INVENTORY_FORMAT]:
            output = command(['rpm', '--root', str(self.installroot), *vector[1:]])
            return ActionResult(True, '', 0, stdout=output, structured_output=output)
        elif vector == ['fuser', '/var/lib/dnf/metadata_lock.pid', '/var/lib/dnf/lock', '/var/lib/rpm/.rpm.lock']:
            # No fabricated lock result: probe the actual disposable guest.
            result = subprocess.run(vector, capture_output=True, text=True, timeout=10)
            return ActionResult(result.returncode == 0, '', result.returncode, stdout=result.stdout)
        else:
            raise ValueError('Fixture refuses an arbitrary command')
        capture = io.StringIO()
        with redirect_stdout(capture):
            code = function(vector[1:])
        output = capture.getvalue()
        self.calls.append({'vector': vector, 'action_id': options.get('action_id', ''), 'returncode': code})
        return ActionResult(code == 0, '', code, stdout=output, structured_output=output)


def scoped_api(api, installroot: Path, repos: Path):
    """Inject filesystem scope before native Base.setup; retain real API code."""
    base_module, *others = api

    class ScopedBase(base_module.Base):
        def load_config(self):
            super().load_config()
            config = self.get_config()
            config.get_installroot_option().set(str(installroot))
            config.get_reposdir_option().set([str(repos)])
            config.get_varsdir_option().set([])
            from core.fedora_release_policy import FEDORA_RELEASE_POLICY
            self.get_vars().set('releasever', FEDORA_RELEASE_POLICY.stable_release)
            for name in ('cachedir', 'system_cachedir', 'persistdir', 'logdir'):
                getattr(config, 'get_' + name + '_option')().set(str(ROOT / name))

    wrapped = SimpleNamespace(Base=ScopedBase, Goal=base_module.Goal, GoalJobSettings=base_module.GoalJobSettings)
    return (wrapped, *others)


def build_inert_rpm(name: str, build: Path, keyring: Path, fingerprint: str, extra: str = '') -> Path:
    build.mkdir()
    spec = build / 'fixture.spec'
    spec.write_text(f'''Name: {name}
Version: 1.0
Release: 1
Summary: Inert disposable codec transaction fixture
License: MIT
BuildArch: noarch
{extra}%description
Contains inert text only, without scripts, triggers or media implementations.
%install
mkdir -p %{{buildroot}}/usr/share/loofi-e2e-codecs
printf '{name}\\n' > %{{buildroot}}/usr/share/loofi-e2e-codecs/{name}
%files
/usr/share/loofi-e2e-codecs/{name}
''')
    command(['rpmbuild', '-bb', '--define', f'_topdir {build}', str(spec)])
    package = next((build / 'RPMS/noarch').glob('*.rpm'))
    command(['rpmsign', '--define', f'_openpgp_sign_id {fingerprint}', '--define', f'_gpg_name {fingerprint}',
             '--define', f'_gpg_path {keyring}', '--addsign', str(package)])
    return package


def publish_repository(repo: Path, repos: Path, installroot: Path, keyring: Path, public: Path) -> None:
    command(['createrepo_c', str(repo)])
    command(['gpg', '--homedir', str(keyring), '--batch', '--yes', '--armor', '--detach-sign', str(repo / 'repodata/repomd.xml')])
    configuration = (f'[loofi-codec-fixture]\nname=Signed inert codec fixture\nbaseurl=file://{repo}\n'
                     f'enabled=1\ngpgcheck=1\nrepo_gpgcheck=1\ngpgkey=file://{public}\n')
    (repos / 'fixture.repo').write_text(configuration)
    from core.fedora_release_policy import FEDORA_RELEASE_POLICY
    command(['dnf5', '--installroot', str(installroot), '--releasever', FEDORA_RELEASE_POLICY.stable_release, '--setopt', f'reposdir={repos}',
             '--setopt', f'cachedir={ROOT / "cachedir"}', '--setopt', f'system_cachedir={ROOT / "system_cachedir"}',
             '--assumeyes', 'makecache'])


def build_codec_repository() -> tuple[Path, Path, str]:
    from services.software.setup_sources import CODEC_PACKAGES
    installroot, repo, repos, keyring = (ROOT / name for name in ('installroot', 'repo', 'repos', 'gnupg'))
    for path in (installroot, repo, repos, keyring):
        path.mkdir(mode=0o700)
    command(['rpm', '--root', str(installroot), '--initdb'])
    command(['gpg', '--homedir', str(keyring), '--batch', '--pinentry-mode', 'loopback', '--passphrase', '',
             '--quick-generate-key', 'Loofi codec fixture <codec@example.invalid>', 'rsa2048', 'sign', '0'])
    keys = command(['gpg', '--homedir', str(keyring), '--with-colons', '--list-secret-keys'])
    fingerprint = next(line.split(':')[9] for line in keys.splitlines() if line.startswith('fpr:'))
    os.environ['GNUPGHOME'] = str(keyring)
    public = ROOT / 'codec-key.asc'
    public.write_text(command(['gpg', '--homedir', str(keyring), '--armor', '--export', fingerprint]) + '\n')
    command(['rpm', '--root', str(installroot), '--import', str(public)])
    baseline = []
    for name in ('ffmpeg-free', 'loofi-e2e-unrelated', *CODEC_PACKAGES):
        extra = 'Conflicts: ffmpeg-free\nObsoletes: ffmpeg-free < 2\n' if name == 'ffmpeg' else ''
        package = build_inert_rpm(name, ROOT / ('build-' + name), keyring, fingerprint, extra)
        command(['rpmkeys', '--root', str(installroot), '--checksig', str(package)])
        if name in ('ffmpeg-free', 'loofi-e2e-unrelated'):
            baseline.append(str(package))
        else:
            shutil.copy2(package, repo)
    command(['rpm', '--root', str(installroot), '-i', *baseline])
    publish_repository(repo, repos, installroot, keyring, public)
    conflict_repo, conflict_repos = ROOT / 'conflict-repo', ROOT / 'conflict-repos'
    conflict_repo.mkdir()
    conflict_repos.mkdir()
    for package in repo.glob('*.rpm'):
        if not package.name.startswith('gstreamer1-plugins-ugly-'):
            shutil.copy2(package, conflict_repo)
    incompatible = build_inert_rpm('gstreamer1-plugins-ugly', ROOT / 'build-conflicting-ugly', keyring, fingerprint, 'Conflicts: ffmpeg\n')
    command(['rpmkeys', '--root', str(installroot), '--checksig', str(incompatible)])
    shutil.copy2(incompatible, conflict_repo)
    publish_repository(conflict_repo, conflict_repos, installroot, keyring, public)
    return installroot, repos, fingerprint


def source_case(controller, executor) -> dict:
    from services.software import setup_sources_helper as helper
    from services.software.setup_sources import SOURCES
    paths = sorted(helper.REPO_DIR.glob('*.repo'))
    baseline = {str(path): path.read_bytes() for path in paths}
    sentinel = ROOT / 'source-user-data.txt'
    sentinel.write_text('Preserve user data during optional source activation\n')
    original_inventory = command(['rpm', '-qa', '--qf', INVENTORY_FORMAT]).splitlines()
    parameters = {'source_id': 'rpmfusion-free'}
    ticket = controller.prepare('enable-rpm-fusion', parameters)
    if ticket.blocked:
        raise RuntimeError('Fixture requires RPM Fusion Free initially absent')
    drift = helper.REPO_DIR / 'loofi-fixture-drift.repo'
    drift.write_text('[loofi-fixture-drift]\nname=Disabled drift fixture\nenabled=0\nbaseurl=file:///nonexistent\n')
    try:
        rejection = controller.confirm(ticket, confirmed=True, accept_no_rollback=True)
        if rejection.status != 'blocked' or rejection.prepared is not None:
            raise RuntimeError('Changed source configuration did not invalidate its review')
    finally:
        drift.unlink()
    # Also race the already confirmed token: native helper must reject again
    # under its real file lock, before importing a key or writing a source.
    race_ticket = controller.prepare('enable-rpm-fusion', parameters)
    race_token = controller.confirm(race_ticket, confirmed=True, accept_no_rollback=True)
    if race_token.status != 'prepared':
        raise RuntimeError('Fresh source review did not produce a confirmed token')
    drift.write_text('[loofi-fixture-drift]\nname=Disabled drift fixture\nenabled=0\nbaseurl=file:///nonexistent\n')
    try:
        locked_rejection = controller.run(race_token, executor=executor.execute)
        if locked_rejection.status != 'failed' or (helper.REPO_DIR / 'loofi-rpmfusion-free.repo').exists():
            raise RuntimeError('Native source helper accepted configuration drift after confirmation')
    finally:
        drift.unlink()
    lock_ticket = controller.prepare('enable-rpm-fusion', parameters)
    lock_token = controller.confirm(lock_ticket, confirmed=True, accept_no_rollback=True)
    if lock_token.status != 'prepared':
        raise RuntimeError('Source lock test did not obtain a confirmed token')
    with competing_file_lock(Path('/run/loofi-setup-sources.lock')) as competitor_pid:
        lock_rejection = controller.run(lock_token, executor=executor.execute)
        if lock_rejection.status != 'failed' or (helper.REPO_DIR / 'loofi-rpmfusion-free.repo').exists():
            raise RuntimeError('A competing native source lock did not reject apply')
        if command(['rpm', '-qa', '--qf', INVENTORY_FORMAT]).splitlines() != original_inventory:
            raise RuntimeError('A locked source operation changed RPM inventory')
        if any(Path(path).read_bytes() != data for path, data in baseline.items()):
            raise RuntimeError('A locked source operation changed unrelated configuration')
    outcome = controller.execute('enable-rpm-fusion', parameters, confirmed=True, accept_no_rollback=True, executor=executor.execute)
    if outcome.status != 'succeeded':
        raise RuntimeError('Native source activation failed: ' + json.dumps(outcome.to_dict()))
    current = command(['rpm', '-qa', '--qf', INVENTORY_FORMAT]).splitlines()

    def without_keys(lines):
        return sorted(line for line in lines if not line.startswith('gpg-pubkey|'))
    if without_keys(current) != without_keys(original_inventory) or any(Path(path).read_bytes() != data for path, data in baseline.items()):
        raise RuntimeError('Source setup modified unrelated packages or repository configuration')
    if sentinel.read_text() != 'Preserve user data during optional source activation\n':
        raise RuntimeError('Source setup changed unrelated user data')
    return {'outcome': outcome.to_dict(), 'stale_review': rejection.to_dict(), 'locked_helper_drift': locked_rejection.to_dict(),
            'competing_native_lock': {'pid': competitor_pid, 'outcome': lock_rejection.to_dict(), 'inventory_preserved': True, 'configs_preserved': True},
            'definition': SOURCES['rpmfusion-free'].to_dict(), 'native_key_import_verified': helper._rpm_key_imported('rpmfusion-free'),
            'unrelated_preserved': True, 'original_configs_preserved': True, 'data_preserved': True}


def require_native_dependency_conflict() -> str:
    """Distinguish the intended solver conflict from missing metadata/backend."""
    from services.software.rpm_transaction_helper import RpmSession
    from services.software.setup_sources import CODEC_PACKAGES
    session = RpmSession()
    expected = 'Package dependencies could not be resolved without conflicts.'
    try:
        try:
            session.resolve('codecs', CODEC_PACKAGES, '', True)
        except ValueError as error:
            if str(error) != expected:
                raise RuntimeError('Native conflict fixture failed for an unexpected reason') from error
            return expected
        raise RuntimeError('Native conflict fixture unexpectedly resolved successfully')
    finally:
        session.close()


def native_codec_failures(controller, executor, installroot: Path, repos: Path, native_api) -> dict:
    """Real resolver conflicts and post-confirmation source drift stay read-only."""
    from services.software import rpm_transaction_helper as rpm_helper
    inventory_vector = ['rpm', '--root', str(installroot), '-qa', '--qf', INVENTORY_FORMAT]
    inventory = sorted(command(inventory_vector).splitlines())
    sentinel = installroot / 'fault-user-data.txt'
    preserved = 'Preserve data across native codec failures\n'
    sentinel.write_text(preserved)
    configuration = repos / 'fixture.repo'
    original = configuration.read_bytes()
    ticket = controller.prepare('install-multimedia-codecs', {'removal_consent': True})
    if ticket.blocked:
        raise RuntimeError('Valid signed fixture must resolve before its source drift test')
    token = controller.confirm(ticket, confirmed=True, accept_no_rollback=True)
    if token.status != 'prepared':
        raise RuntimeError('Codec drift test did not obtain a confirmed token')
    public, alternate = ROOT / 'codec-key.asc', ROOT / 'same-trust-alternate-key.asc'
    alternate.write_bytes(public.read_bytes())
    changed = original.replace(f'gpgkey=file://{public}'.encode(), f'gpgkey=file://{alternate}'.encode())
    if changed == original:
        raise RuntimeError('Codec drift fixture did not change the reviewed source identity')
    try:
        configuration.write_bytes(changed)
        drift = controller.run(token, executor=executor.execute)
        if drift.status != 'failed' or drift.result is None or json.loads(drift.result.stdout).get('error_code') != 'transaction_drift':
            raise RuntimeError('Native apply did not reject the changed signed repository identity')
    finally:
        configuration.write_bytes(original)
    if sorted(command(inventory_vector).splitlines()) != inventory or sentinel.read_text() != preserved:
        raise RuntimeError('Rejected native repository drift changed inventory or data')
    before_calls = len(executor.calls)
    with patch.object(rpm_helper, 'load_api', lambda: scoped_api(native_api, installroot, ROOT / 'conflict-repos')):
        conflict_reason = require_native_dependency_conflict()
        conflict = controller.prepare('install-multimedia-codecs', {'removal_consent': True})
    if not conflict.blocked or conflict.plan.policy_decision.reason_code != 'codec_transaction_unavailable':
        raise RuntimeError('Mutually conflicting fixed recipe packages were not blocked by the native resolver')
    if any(call['vector'][1] == 'apply' for call in executor.calls[before_calls:]):
        raise RuntimeError('A conflicting codec preview attempted mutation')
    if sorted(command(inventory_vector).splitlines()) != inventory or sentinel.read_text() != preserved or configuration.read_bytes() != original:
        raise RuntimeError('Rejected native dependency conflict changed inventory, configuration or data')
    return {'signed_source_drift': drift.to_dict(), 'dependency_conflict': conflict.to_dict(),
            'native_resolver_conflict': conflict_reason,
            'inventory_preserved': True, 'configs_preserved': True, 'data_preserved': True,
            'dependency_conflict_fixture': 'Signed gstreamer1-plugins-ugly declares Conflicts: ffmpeg; both are explicit fixed recipe goals.'}


def codec_case(controller, executor, installroot: Path) -> dict:
    from services.software.setup_sources import CODEC_PACKAGES
    sentinel = installroot / 'user-data.txt'
    sentinel.write_text('Preserve user media and unrelated application data\n')
    baseline = command(['rpm', '--root', str(installroot), '-qa', '--qf', INVENTORY_FORMAT]).splitlines()
    denied = controller.prepare('install-multimedia-codecs', {'removal_consent': False})
    if not denied.blocked:
        raise RuntimeError('Codec replacement was reviewable without separate removal consent')
    if command(['rpm', '--root', str(installroot), '-qa', '--qf', INVENTORY_FORMAT]).splitlines() != baseline:
        raise RuntimeError('A rejected codec preview mutated inventory')
    ticket = controller.prepare('install-multimedia-codecs', {'removal_consent': True})
    if ticket.blocked:
        raise RuntimeError('Signed codec recipe could not be reviewed: ' + json.dumps(ticket.to_dict()))
    operations = ticket.plan.policy_decision.facts['rpm_transaction']['operations']
    if not any(item['name'] == 'ffmpeg-free' and item['action'] in ('Remove', 'Replaced') for item in operations):
        raise RuntimeError('Complete codec review did not disclose its replacement')
    confirmed = controller.confirm(ticket, confirmed=True, accept_no_rollback=True)
    running = controller.run(confirmed, executor=executor.execute)
    outcome = controller.verify(running) if running.status == 'verifying' else running
    after = command(['rpm', '--root', str(installroot), '-qa', '--qf', INVENTORY_FORMAT]).splitlines()
    expected = {f'{name}|{name}-0:1.0-1.noarch' for name in CODEC_PACKAGES} | {'loofi-e2e-unrelated|loofi-e2e-unrelated-0:1.0-1.noarch'}
    if outcome.status != 'succeeded' or {row for row in after if not row.startswith('gpg-pubkey|')} != expected:
        raise RuntimeError('Native codec transaction did not reach its complete exact inventory: ' + json.dumps(outcome.to_dict()))
    if sentinel.read_text() != 'Preserve user media and unrelated application data\n':
        raise RuntimeError('Codec operation changed user data')
    command(['rpm', '--root', str(installroot), '-V', 'loofi-e2e-unrelated', *CODEC_PACKAGES])
    return {'without_removal_consent': denied.to_dict(), 'review': ticket.to_dict(), 'outcome': outcome.to_dict(),
            'inventory_before': baseline, 'inventory_after': after, 'data_preserved': True, 'unrelated_preserved': True}


def qualify() -> None:
    guard()
    prepare_staged_key()
    for name in ('rpmbuild', 'rpmsign', 'rpmkeys', 'gpg', 'createrepo_c', 'dnf5'):
        if not shutil.which(name):
            raise RuntimeError('Missing disposable guest fixture tool: ' + name)
    from core.actions.catalog import SystemActionRuntime
    from core.actions.operation_controller import OperationController
    from core.actions.orchestrator import ActionCenterOrchestrator
    from services.software import rpm_transaction_helper as rpm_helper
    from services.software import setup_sources_helper as source_helper
    from services.software.installed_applications import InstalledApplicationService
    staged_fetch(__import__('services.software.setup_sources', fromlist=['SOURCES']).SOURCES['rpmfusion-free'].key_url)
    installroot, repos, fingerprint = build_codec_repository()
    executor = ClosedExecutor(installroot)
    runtime = SystemActionRuntime(executor)
    controller = OperationController(orchestrator=ActionCenterOrchestrator(facade=executor, runtime=runtime))
    evidence = {'schema': 'loofi.setup-native-fixture/v1', 'qualified': False,
                'injected_seams': ['exact immutable source key URL served from staged bytes', 'closed in-process helper dispatch replacing subprocess/Polkit',
                                   'native libdnf5 Base installroot and isolated repository paths before setup', 'independent rpm readback scoped to same installroot'],
                'not_qualified': ['public endpoint availability or TLS', 'Polkit authentication', 'real multimedia playback'],
                'codec_signing_fingerprint': fingerprint}
    REPORT.write_text(json.dumps(evidence, indent=2))
    with ExitStack() as stack:
        stack.enter_context(patch.object(source_helper, '_fetch', staged_fetch))
        stack.enter_context(patch.object(InstalledApplicationService, '_probe', executor.execute))
        native_api = rpm_helper.load_api()
        stack.enter_context(patch.object(rpm_helper, 'load_api', lambda: scoped_api(native_api, installroot, repos)))
        evidence['source'] = source_case(controller, executor)
        REPORT.write_text(json.dumps(evidence, indent=2))
        evidence['native_codec_failures'] = native_codec_failures(controller, executor, installroot, repos, native_api)
        REPORT.write_text(json.dumps(evidence, indent=2))
        evidence['codecs'] = codec_case(controller, executor, installroot)
    evidence.update(qualified=True, helper_calls=executor.calls)
    REPORT.write_text(json.dumps(evidence, indent=2))


if __name__ == '__main__':
    qualify()
