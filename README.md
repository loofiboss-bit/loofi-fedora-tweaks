# Loofi Fedora Tweaks v23.0.0 "Compass"

<!-- markdownlint-configure-file {"MD033": false} -->

<p align="center">
  <img src="loofi-fedora-tweaks/assets/loofi-fedora-tweaks.png" alt="Loofi Fedora Tweaks logo" width="128"/>
</p>

<p align="center">
  <strong>A focused Fedora maintenance and desktop control center</strong><br>
  Six destinations, one Home, one search surface, safe system operations.
</p>

<p align="center">
  <a href="https://github.com/loofiboss-bit/loofi-fedora-tweaks/releases/tag/v23.0.0">
    <img src="https://img.shields.io/badge/Release-v23.0.0-blue?style=for-the-badge&logo=github" alt="Loofi Fedora Tweaks v23.0.0 release"/>
  </a>
  <img src="https://img.shields.io/badge/Fedora_KDE-44-blue?style=for-the-badge&logo=fedora" alt="Fedora KDE 44"/>
  <img src="https://img.shields.io/badge/Python-3.12+-green?style=for-the-badge&logo=python" alt="Python 3.12 or newer"/>
  <img src="https://img.shields.io/badge/Coverage-86%25-brightgreen?style=for-the-badge&logo=pytest" alt="Coverage gate 86%"/>
</p>

## What Compass changes

Compass turns the existing System diagnostics route into one explicit,
bounded troubleshooting journey without adding repair or execution authority.

- Six closed symptom profiles collect source-owned evidence only after an
  explicit start.
- Findings expose source, freshness, applicability, evidence quality, and one
  safe next step.
- Related changes remain conservatively labelled **Possibly related**.
- Follow-up results keep Action Center verification separate from
  troubleshooting resolution.
- CLI collection is explicit; authenticated API endpoints are retrieval-only;
  Support Bundle v13 remains bounded and command-free.

Full details: [v23 release notes](docs/releases/RELEASE-NOTES-v23.0.0.md).

## The six destinations

| Destination | What belongs there |
| --- | --- |
| Home | Current state, the next useful action, attention items, and common tasks |
| Software & Updates | Applications, repositories, updates, cleanup, Fedora upgrade, and Action Center |
| System | System details, performance, processes, hardware, storage, diagnostics, health history, and recovery points |
| Network & Security | Connections, DNS, privacy, firewall, exposure, and backups |
| Desktop | Appearance, displays, and window behavior |
| Settings | Appearance and behavior settings, Specialist Tools status, Repair Loofi, and About |

Specialist Tools contains development, local AI, agents, automation, virtualization,
gaming, device sharing, local profiles, desktop extensions, and workspace tools.
These routes remain discoverable when policy and component availability allow;
their visibility never weakens confirmation or privilege rules.

## Five common workflows

1. **Update Fedora:** Home → Updates → review Fedora → create plan → confirm in Action Center.
2. **Install an application:** Home → Applications → Install → review and confirm the generated plan.
3. **Diagnose a slow system:** Home → Check performance → Analyze Slow System.
4. **Find reclaimable disk space:** Software & Updates → Cleanup → Analyze.
5. **Protect the system:** Home → Protect or recover → create a recovery point.

The five canonical surfaces may create one exact Action Center plan and open it
for review. They never apply it automatically; apply remains a separate,
explicitly confirmed operation.

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

The API accepts loopback bindings only and defaults to `127.0.0.1:8000`.
`LOOFI_API_HOST` may select another loopback address; non-local values stop
startup. `LOOFI_API_PORT` changes the port and `LOOFI_CORS_ORIGINS` is limited
to loopback origins.

## CLI examples

```bash
alias loofi='loofi-fedora-tweaks --cli'

loofi info
loofi health
loofi health check
loofi health findings
loofi health history --limit 5
loofi troubleshoot profiles
loofi troubleshoot run system_slow
loofi troubleshoot latest
loofi troubleshoot show SESSION_ID
loofi troubleshoot compare SESSION_ID FOLLOWUP_ID
loofi troubleshoot export SESSION_ID
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

- Action Center exposes 63 classified first-party definitions. Unsupported host
  operations are visible as non-executable `manual_only` plans.
- System Check findings cannot execute commands. Action handoff resolves only
  fresh, untampered evidence against the closed Action Center catalog.
- Plans expire and are re-preflighted. Exit code zero is not success until the
  verifier passes. Interrupted runs never resume automatically.
- Commands are list-based, allowlisted, timeout-bounded, audit-linked, and never
  use `shell=True`.
- State schemas, atomic writes, backup/restore planning, redaction, routes,
  aliases, favorites, first-run sentinels, CLI JSON, API, daemon, and IPC remain
  compatible with v14.
- Built-in specialist tools remain lazy-loaded in the base RPM. External Python
  code is not an extension boundary.

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

`v23.0.0 "Compass"` is approved for publication through the canonical
exact-tag release pipeline. Fedora 45 remains preview-only. The older
"Architecture Hardening" tag object is preserved byte-identically as
`legacy-v23.0.0-architecture-hardening`; the canonical `v23.0.0` reference is
reserved for Compass. Historical Sentinel, Horizon, Nebula, and Synapse
lineages likewise remain preserved under explicit `legacy-v*` tags.

## License

MIT License.
