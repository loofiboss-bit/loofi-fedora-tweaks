"""First installations through the installed Action Center, using signed local refs."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import subprocess

from flatpak_fixture import APP, FIRST_INSTALL, INSTALLATIONS, REMOTE, ROOT, RUNTIME, SOURCE, ref, scope
from helpers import authenticate_polkit
from test_01_flatpak_updates import assert_preserved, commits, installed, invoke


def inventory() -> dict[str, list[str]]:
    """Read all scoped refs, commits and origins independently of product verification."""
    result = {}
    for installation in INSTALLATIONS:
        completed = subprocess.run(['flatpak', scope(installation), 'list', '--columns=ref,commit,origin'],
                                   capture_output=True, text=True, check=True, timeout=30)
        result[installation] = sorted(completed.stdout.splitlines())
    return result


def execute(installation: str) -> dict:
    parameters = {'source': 'flatpak', 'package_id': ref(FIRST_INSTALL), 'installation': installation, 'remote': REMOTE}
    code = ('import json; from core.actions.operation_controller import OperationController; '
            f"outcome=OperationController().execute('install-application', {parameters!r}, "
            'confirmed=True,accept_no_rollback=True); print(json.dumps(outcome.to_dict())); '
            "raise SystemExit(0 if outcome.status == 'succeeded' else 1)")
    output, errors = ROOT / f'{installation}-first-install.json', ROOT / f'{installation}-first-install.log'
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
    return {'parameters': parameters, 'outcome': json.loads(output.read_text()),
            'probe_sha256': hashlib.sha256(code.encode()).hexdigest()}


def test_first_install_uses_exact_scopes_and_rejects_changed_source(loofi_app) -> None:
    versions, selected = commits(), ref(FIRST_INSTALL)
    baseline = inventory()
    assert all(not any(line.split('\t')[0] == selected for line in rows) for rows in baseline.values())
    evidence = {'fixture_commits': versions, 'before': baseline, 'transactions': [],
                'public_key_sha256': hashlib.sha256((ROOT / 'fixture-key.asc').read_bytes()).hexdigest(),
                'execution': 'Installed RPM OperationController and native libflatpak with desktop Polkit',
                'limitations': ['Synthetic offline applications are not launched; no permission editing.',
                                'AT-SPI and native update navigation are qualified by the separate v34 matrix.']}
    # A source configuration change must invalidate a previously reviewed install.
    # Alter only this ephemeral user remote, restore it even on failure, and never
    # execute the rejected ticket. The before/after inventory proves no mutation.
    stale_code = f'''import json, subprocess
from core.actions.operation_controller import OperationController
controller=OperationController()
ticket=controller.prepare('install-application', {{'source':'flatpak','package_id':{selected!r},'installation':'user','remote':{REMOTE!r}}})
assert not ticket.blocked, ticket.to_dict()
priority=subprocess.run(['flatpak','--user','remotes','--columns=name,priority'],capture_output=True,text=True,check=True,timeout=30)
original=next(line.split()[1] for line in priority.stdout.splitlines() if line.split()[0] == {REMOTE!r})
try:
 subprocess.run(['flatpak','--user','remote-modify','--prio='+str(int(original)+1),{REMOTE!r}],capture_output=True,check=True,timeout=30)
 outcome=controller.confirm(ticket,confirmed=True,accept_no_rollback=True)
 print(json.dumps({{'ticket':ticket.to_dict(),'outcome':outcome.to_dict()}}))
 assert outcome.status == 'blocked' and outcome.prepared is None
finally:
 subprocess.run(['flatpak','--user','remote-modify','--prio='+original,{REMOTE!r}],capture_output=True,check=True,timeout=30)
'''
    evidence['stale_review'] = invoke(stale_code)
    assert inventory() == baseline, 'Rejected source review changed installed refs'
    report = ROOT.parent / 'flatpak-install-evidence.json'
    report.write_text(json.dumps(evidence, indent=2))
    for installation in INSTALLATIONS:
        before = inventory()
        preview = invoke('import json; from services.software.flatpak_installation import FlatpakInstallationService; '
                         f'p=FlatpakInstallationService().preview({installation!r},{REMOTE!r},{selected!r}); '
                         'print(json.dumps({"available":p.available,"error":p.error,"facts":p.review_facts()}))')
        assert preview['available'], preview
        facts = preview['facts']
        operations = facts['operations']
        assert {item['ref'] for item in operations}.issubset({selected, ref(RUNTIME, runtime=True)}), preview
        chosen = [item for item in operations if item['ref'] == selected]
        assert len(chosen) == 1 and chosen[0]['operation'] == 'install' and chosen[0]['selected'] is True
        assert chosen[0]['expected_commit'] == versions['2'][selected]
        assert all(item['installation'] == installation and item['origin'] == REMOTE for item in operations)
        executed = execute(installation)
        outcome = executed['outcome']
        assert outcome['status'] == 'succeeded' and outcome['run']['run_id'], outcome
        verified = outcome['run']['verification_result']['data']['results']
        assert {item['ref'] for item in verified} == {item['ref'] for item in operations}, outcome
        assert all(item['status'] == 'verified' and item['installation'] == installation
                   and item['observed_origin'] == REMOTE for item in verified), outcome
        for item in operations:
            assert installed(installation, item['ref']) == item['expected_commit']
            origin = subprocess.run(['flatpak', scope(installation), 'info', '--show-origin', item['ref']],
                                    capture_output=True, text=True, check=True, timeout=30)
            assert origin.stdout.strip() == item['origin']
        after = inventory()
        changed_refs = {item['ref'] for item in operations}
        for scoped in INSTALLATIONS:
            if scoped != installation:
                assert after[scoped] == before[scoped], 'Another installation changed'
            else:
                assert [line for line in after[scoped] if line.split('\t')[0] not in changed_refs] == [
                    line for line in before[scoped] if line.split('\t')[0] not in changed_refs]
        assert_preserved(versions['1'])
        assert (Path.home() / '.var/app' / APP / 'loofi-e2e-sentinel').is_file()
        evidence['transactions'].append({**executed, 'preview': preview, 'before': before, 'after': after,
                                         'unrelated_refs_and_data_preserved': True})
        report.write_text(json.dumps(evidence, indent=2))
