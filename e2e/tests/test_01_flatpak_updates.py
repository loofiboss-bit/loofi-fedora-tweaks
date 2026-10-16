"""Real libflatpak transactions against two offline versions in a disposable VM."""
from __future__ import annotations

from datetime import datetime
import json
import os
from pathlib import Path
import subprocess

from flatpak_fixture import APP, INSTALLATIONS, ROOT, RUNTIME, SOURCE, UNRELATED, ref, scope
from helpers import authenticate_polkit


def invoke(code: str) -> dict:
    result = subprocess.run(['/usr/bin/python3', '-c', code], env={**os.environ, 'PYTHONPATH': SOURCE},
                            capture_output=True, text=True, check=False, timeout=180)
    assert result.returncode == 0, result.stderr or result.stdout
    return json.loads(result.stdout)


def installed(installation: str, full_ref: str) -> str:
    result = subprocess.run(['flatpak', scope(installation), 'info', '--show-commit', full_ref],
                            capture_output=True, text=True, check=True, timeout=30)
    return result.stdout.strip()


def commits() -> dict:
    assert (ROOT / 'commits.json').is_file(), 'Root guest fixture preparation must finish before tests'
    return json.loads((ROOT / 'commits.json').read_text())


def fixture_timestamps() -> dict[str, str]:
    return json.loads((ROOT / 'timestamps.json').read_text())


def commit_timestamps() -> dict[str, dict[str, int]]:
    return json.loads((ROOT / 'commit-timestamps.json').read_text())


def assert_preserved(expected: dict[str, str]) -> None:
    for installation in INSTALLATIONS:
        assert installed(installation, ref(UNRELATED)) == expected[ref(UNRELATED)]
    sentinel = Path.home() / '.var/app' / APP / 'loofi-e2e-sentinel'
    assert sentinel.read_text() == 'Preserve app data across scoped updates\n'


def test_same_ref_scoped_update_verifies_app_and_dependency_without_touching_other_installations(loofi_app) -> None:
    versions = commits()
    timestamps = fixture_timestamps()
    actual_timestamps = commit_timestamps()
    assert datetime.fromisoformat(timestamps['2'].replace('Z', '+00:00')) > datetime.fromisoformat(
        timestamps['1'].replace('Z', '+00:00'))
    assert all(actual_timestamps['2'][full_ref] > actual_timestamps['1'][full_ref]
               for full_ref in versions['1'])
    discovered = invoke('import json; from services.software.flatpak_updates import FlatpakUpdatesService; '
                        'print(json.dumps(FlatpakUpdatesService().discover().to_dict()))')
    assert discovered['available'], discovered
    identities = {(candidate['installation'], candidate['ref']) for candidate in discovered['candidates']}
    assert {(installation, ref(APP)) for installation in INSTALLATIONS}.issubset(identities), discovered
    cli = subprocess.run(['/usr/bin/loofi-fedora-tweaks', '--cli', '--json', 'updates', 'flatpaks',
                          '--installation', 'user', '--ref', ref(APP)],
                         capture_output=True, text=True, check=False, timeout=90)
    assert cli.returncode == 0, cli.stdout or cli.stderr
    cli_snapshot = json.loads(cli.stdout)
    assert cli_snapshot['available'], cli_snapshot
    assert {(item['installation'], item['ref']) for item in cli_snapshot['candidates']} == {('user', ref(APP))}
    evidence = {'fixture_commits': versions, 'fixture_timestamps': timestamps,
                'fixture_commit_timestamps': actual_timestamps,
                'discovery': discovered, 'cli': cli_snapshot, 'transactions': []}
    report = ROOT.parent / 'flatpak-update-evidence.json'
    for index, installation in enumerate(INSTALLATIONS):
        selected = ref(APP)
        preview = invoke('import json; from services.software.flatpak_updates import FlatpakUpdatesService; '
                         f'print(json.dumps(FlatpakUpdatesService().preview({installation!r}, ({selected!r},)).to_dict()))')
        assert preview['available'], preview
        assert {(candidate['installation'], candidate['ref']) for candidate in preview['candidates']} == {(installation, selected)}
        operations = preview['installations'][0]['operations']
        assert {operation['ref'] for operation in operations} == {selected, ref(RUNTIME, runtime=True)}, preview
        assert next(operation for operation in operations if operation['ref'] == selected)['selected']
        assert not next(operation for operation in operations if operation['ref'] != selected)['selected']
        code = ('import json; from core.actions.operation_controller import OperationController; '
                f"outcome=OperationController().execute('update-flatpaks', {{'installation':{installation!r},'refs':[{selected!r}]}}, "
                'confirmed=True,accept_no_rollback=True); print(json.dumps(outcome.to_dict())); '
                "raise SystemExit(0 if outcome.status == 'succeeded' else 1)")
        output = ROOT / f'{installation}-action.json'
        errors = ROOT / f'{installation}-action.log'
        with output.open('w') as stdout, errors.open('w') as stderr:
            process = subprocess.Popen(['/usr/bin/python3', '-c', code],
                                       env={**os.environ, 'PYTHONPATH': SOURCE}, stdout=stdout, stderr=stderr)
            try:
                def complete():
                    if process.poll() is not None:
                        assert process.returncode == 0, errors.read_text() + output.read_text()
                        return True
                    return False
                authenticate_polkit(completed=complete, timeout=90)
                assert process.wait(timeout=180) == 0, errors.read_text() + output.read_text()
            finally:
                if process.poll() is None:
                    process.terminate()
                    try:
                        process.wait(timeout=10)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        process.wait(timeout=10)
        outcome = json.loads(output.read_text())
        assert outcome['status'] == 'succeeded', outcome
        results = outcome['run']['verification_result']['data']['results']
        assert {result['ref'] for result in results} == {selected, ref(RUNTIME, runtime=True)}
        assert all(result['installation'] == installation and result['status'] == 'verified' for result in results)
        assert outcome['run']['run_id'], 'Verified result must identify its real Activity run'
        for other_index, other in enumerate(INSTALLATIONS):
            expected = versions['2' if other_index <= index else '1']
            assert installed(other, selected) == expected[selected]
            assert installed(other, ref(RUNTIME, runtime=True)) == expected[ref(RUNTIME, runtime=True)]
        assert_preserved(versions['1'])
        evidence['transactions'].append({'installation': installation, 'preview': preview, 'outcome': outcome,
                                         'unrelated_apps_and_appdata_preserved': True})
        report.write_text(json.dumps(evidence, indent=2))


def test_review_is_rejected_when_installed_commit_changes(loofi_app) -> None:
    versions = commits()
    selected = ref(APP)
    runtime = ref(RUNTIME, runtime=True)
    # Reproduce a normal split installation: the user's app can use an
    # already installed system runtime without adding a duplicate user runtime.
    subprocess.run(['flatpak', '--user', 'uninstall', '--noninteractive', '--no-related', '--force-remove', runtime],
                   check=True, capture_output=True, timeout=90)
    subprocess.run(['flatpak', '--user', 'update', '--noninteractive', '--no-deps',
                    '--commit=' + versions['1'][selected], selected], check=True, capture_output=True, timeout=90)
    preview = invoke('import json; from services.software.flatpak_updates import FlatpakUpdatesService, apply_vector; '
                     f'snapshot=FlatpakUpdatesService().preview("user", ({selected!r},)); '
                     'print(json.dumps({"snapshot":snapshot.to_dict(),"command":apply_vector(snapshot)}))')
    assert preview['snapshot']['available'], preview
    assert {item['ref'] for item in preview['snapshot']['installations'][0]['operations']} == {selected}, preview
    assert installed('system', runtime) == versions['2'][runtime]
    subprocess.run(['flatpak', '--user', 'update', '--noninteractive', '--no-deps', selected],
                   check=True, capture_output=True, timeout=90)
    rejected = subprocess.run(preview['command'], capture_output=True, text=True, timeout=90, check=False)
    assert rejected.returncode != 0, 'The helper accepted stale installed-commit review evidence'
    assert installed('user', selected) == versions['2'][selected]
    assert_preserved(versions['1'])
    report = ROOT.parent / 'flatpak-update-evidence.json'
    evidence = json.loads(report.read_text())
    missing = subprocess.run(['flatpak', '--user', 'info', runtime], capture_output=True, text=True, timeout=30, check=False)
    assert missing.returncode != 0, 'The shared system runtime was duplicated into the user installation'
    assert installed('system', runtime) == versions['2'][runtime]
    assert installed(INSTALLATIONS[2], runtime) == versions['2'][runtime]
    evidence['system_runtime_reused_without_user_duplicate'] = True
    evidence['stale_review_rejected'] = True
    report.write_text(json.dumps(evidence, indent=2))
