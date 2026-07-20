# Loofi Fedora Tweaks v17.0.0 "Assurance"

<!-- markdownlint-configure-file {"MD033": false} -->

<p align="center">
  <img src="loofi-fedora-tweaks/assets/loofi-fedora-tweaks.png" alt="Loofi Fedora Tweaks logo" width="128"/>
</p>

<p align="center">
  <strong>A focused Fedora maintenance and desktop control center</strong><br>
  Six destinations, one Home, one search surface, safe system operations.
</p>

<p align="center">
  <a href="https://github.com/loofiboss-bit/loofi-fedora-tweaks/releases/tag/v17.0.0">
    <img src="https://img.shields.io/badge/Release-v17.0.0-blue?style=for-the-badge&logo=github" alt="Release v17.0.0"/>
  </a>
  <img src="https://img.shields.io/badge/Fedora_KDE-44-blue?style=for-the-badge&logo=fedora" alt="Fedora KDE 44"/>
  <img src="https://img.shields.io/badge/Python-3.12+-green?style=for-the-badge&logo=python" alt="Python 3.12 or newer"/>
  <img src="https://img.shields.io/badge/Coverage-85%25-brightgreen?style=for-the-badge&logo=pytest" alt="Coverage gate 85%"/>
</p>

## What Assurance changes

v17 converges the five canonical maintenance workflows on preview-first,
explicitly confirmed, audited, and outcome-verified Action Center plans.

- Fedora, Flatpak, and firmware updates create independent, single-action plans
  with exact preflight facts and action-specific readback verification.
- Application install/remove, cleanup, and recovery-point creation use the same
  plan, confirm, apply, verify, and history lifecycle.
- Atomic Fedora and reboot-requiring firmware runs pause durably at
  `awaiting_reboot` and verify the expected deployment after restart.
- Action Center schema v2 preserves readable v1 history and migrates writable
  stores atomically with a verified backup.
- The authenticated Web API is read-only except for token issuance.
- The v16 responsive shell, stable routes, Home, search, CLI, daemon, IPC, and
  original three Action Center definitions remain compatible.

The recorded v17 release benchmark renders meaningful Home in 160.268 ms and
uses 78,092 KiB RSS. It constructs one plugin and starts with no subprocess
probes, active hidden-page timers, or worker threads.

Full details: [v17 release notes](docs/releases/RELEASE-NOTES-v17.0.0.md).

## The six destinations

| Destination | What belongs there |
| --- | --- |
| Home | Current state, the next useful action, attention items, and common tasks |
| Software & Updates | Applications, repositories, updates, cleanup, Fedora upgrade, and Action Center |
| System | System details, performance, processes, hardware, storage, diagnostics, health history, and recovery points |
| Network & Security | Connections, DNS, privacy, firewall, exposure, and backups |
| Desktop | Appearance, displays, and window behavior |
| Settings | Appearance and behavior settings, Standard/Advanced mode, Repair Loofi, and About |

Advanced contains development, local AI, agents, automation, virtualization,
gaming, community, device sharing, profiles, extensions, and workspace tools.
These routes remain discoverable when policy and component availability allow;
Advanced mode never weakens confirmation or privilege rules.

## Five common workflows

1. **Update Fedora:** Home → Updates → review Fedora → create plan → confirm in Action Center.
2. **Install an application:** Home → Applications → Install → review and confirm the generated plan.
3. **Diagnose a slow system:** Home → Check performance → Analyze Slow System.
4. **Find reclaimable disk space:** Software & Updates → Cleanup → Analyze.
5. **Protect the system:** Home → Protect or recover → create a recovery point.

The five canonical surfaces may create one exact Action Center plan and open it
for review. They never apply it automatically; apply remains a separate,
explicitly confirmed operation.

## Screenshots

<table>
  <tr>
    <td width="50%"><img src="docs/images/user-guide/home-dashboard.png" alt="Clarity Home with responsive six-destination sidebar"/></td>
    <td width="50%"><img src="docs/images/user-guide/maintenance-updates.png" alt="Software and Updates maintenance workflow"/></td>
  </tr>
  <tr>
    <td><strong>Canonical Home</strong></td>
    <td><strong>Updates and maintenance</strong></td>
  </tr>
  <tr>
    <td><img src="docs/images/user-guide/system-monitor.png" alt="System performance and processes"/></td>
    <td><img src="docs/images/user-guide/settings-appearance.png" alt="Settings appearance page"/></td>
  </tr>
  <tr>
    <td><strong>System diagnosis</strong></td>
    <td><strong>Settings</strong></td>
  </tr>
</table>

The complete, reproducible screenshot catalog is in
[docs/images/user-guide/README.md](docs/images/user-guide/README.md).

## Install

The supported package source is the Fedora COPR repository:

```bash
pkexec dnf copr enable loofitheboss/loofi-fedora-tweaks
pkexec dnf install loofi-fedora-tweaks
```

Optional runtimes remain separate:

```bash
pkexec dnf install loofi-fedora-tweaks-api
pkexec dnf install loofi-fedora-tweaks-daemon
```

Never run the application with `sudo`. Privileged operations use explicit
Polkit prompts through `pkexec`.

### Run from source

```bash
git clone https://github.com/loofiboss-bit/loofi-fedora-tweaks.git
cd loofi-fedora-tweaks
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[api,daemon,dev]'
PYTHONPATH=loofi-fedora-tweaks python3 loofi-fedora-tweaks/main.py
```

## Entry modes

| Mode | Command | Contract |
| --- | --- | --- |
| GUI | `loofi-fedora-tweaks` | Desktop control center |
| CLI | `loofi-fedora-tweaks --cli <command>` | Scriptable commands and stable JSON envelopes |
| Daemon | `loofi-fedora-tweaks --daemon` | Optional D-Bus host with preserved compatibility methods |
| Web API | `loofi-fedora-tweaks --web` | Authenticated read-only status and inspection API |

The API binds to `127.0.0.1:8000` by default. Configure
`LOOFI_API_HOST`, `LOOFI_API_PORT`, and the comma-separated
`LOOFI_CORS_ORIGINS` allowlist when a different trusted interface is required.

## CLI examples

```bash
alias loofi='loofi-fedora-tweaks --cli'

loofi info
loofi health
loofi doctor
loofi support-bundle
loofi readiness --target 44
loofi action-center list
loofi action-center plan dnf-clean-all
loofi action-center show PLAN_ID
loofi action-center apply PLAN_ID --confirm
loofi action-center verify RUN_ID
loofi --json state doctor
```

The global `--json` option appears before the CLI command.

## Safety and compatibility

- Action Center exposes the original three definitions plus eight Assurance
  definitions for independent updates, application operations, cleanup, and
  recovery-point creation.
- Plans expire and are re-preflighted. Exit code zero is not success until the
  verifier passes. Interrupted runs never resume automatically.
- Commands are list-based, allowlisted, timeout-bounded, audit-linked, and never
  use `shell=True`.
- State schemas, atomic writes, backup/restore planning, redaction, routes,
  aliases, favorites, first-run sentinels, CLI JSON, API, daemon, and IPC remain
  compatible with v14.
- Specialist tools are logically isolated but remain in the base RPM. Current
  ownership and runtime overlap keep a physical extras RPM out of v17 scope.

## Development

Use the repository command surface:

```bash
just test
just test-coverage
just lint
just typecheck
just verify
just check-packaging
just validate-release
just build-rpm
```

See [AGENTS.md](AGENTS.md), [ARCHITECTURE.md](ARCHITECTURE.md), and
[CONTRIBUTING.md](CONTRIBUTING.md) before changing code.

## Documentation

- [Beginner quick guide](docs/BEGINNER_QUICK_GUIDE.md)
- [Full user guide](docs/USER_GUIDE.md)
- [Advanced administration](docs/ADVANCED_ADMIN_GUIDE.md)
- [Verified maintenance](docs/VERIFIED_MAINTENANCE.md)
- [State integrity and recovery](docs/STATE_INTEGRITY.md)
- [Troubleshooting](docs/TROUBLESHOOTING.md)
- [Documentation index](docs/README.md)
- [Changelog](CHANGELOG.md)

## Release status

`v17.0.0 "Assurance"` is the current release for Fedora KDE 44. The canonical
tag, GitHub release assets, checksums, SBOM/provenance, and Fedora 44 COPR build
are produced from one exact release commit.

## License

MIT License.
