# Loofi Fedora Tweaks v27.0.1 "Core"

<!-- markdownlint-configure-file {"MD033": false} -->

<p align="center">
  <img src="loofi-fedora-tweaks/assets/loofi-fedora-tweaks.png" alt="Loofi Fedora Tweaks logo" width="128"/>
</p>

<p align="center">
  <strong>A focused Fedora maintenance core</strong><br>
  Five destinations, one review surface, and verified system changes.
</p>

![Loofi Fedora Tweaks Home](docs/images/user-guide/home-dashboard.png)

<p align="center">
  <a href="https://github.com/loofiboss-bit/loofi-fedora-tweaks/releases/tag/v27.0.1">
    <img src="https://img.shields.io/badge/Release-v27.0.1-blue?style=for-the-badge&logo=github" alt="Loofi Fedora Tweaks v27.0.1 release"/>
  </a>
  <img src="https://img.shields.io/badge/Fedora-43_|_44-blue?style=for-the-badge&logo=fedora" alt="Fedora 43 and 44"/>
  <img src="https://img.shields.io/badge/Python-3.12+-green?style=for-the-badge&logo=python" alt="Python 3.12 or newer"/>
</p>

## What Loofi does

Loofi Fedora Tweaks brings the most useful Fedora maintenance tasks into one
small, desktop-neutral control center. It focuses on inspection, clear review,
and independently verified results. It does not run a background service or
include a web API.

- Home shows current state, one recommended next action, and common tasks.
- Updates & Apps checks system packages, Flatpak, and firmware independently;
  application discovery can be handed off to the desktop's native software
  center.
- System Health provides read-only checks, symptom-driven troubleshooting,
  storage and hardware inspection, and support export.
- Protection & Recovery groups firewall exposure, backups, recovery points,
  and supported rollback guidance.
- Changes is the single review, confirmation, execution, and verification
  workspace for persistent system changes.

This is the [v27.0.1 Core release](docs/releases/RELEASE-NOTES-v27.0.1.md).
The previous public release was [v26.0.3 Everyday](docs/releases/RELEASE-NOTES-v26.0.3.md).
Automated qualification is complete. Physical desktop, authorization, reboot,
and fresh Atomic qualification are intentionally reported as unverified for
this release; no manual test result is inferred from offscreen or rootless
evidence.

The maintained V27 surface reaches 86.94% local line coverage with an 85%
blocking gate. The planned repository-wide 90% target is deferred to the next
release so this version can ship without overstating coverage.

## Install

The supported package source is the Fedora COPR repository:

```bash
pkexec dnf copr enable loofitheboss/loofi-fedora-tweaks
pkexec dnf install loofi-fedora-tweaks
```

Launch the application from the desktop menu or with:

```bash
loofi-fedora-tweaks
```

System authorization is requested only when a reviewed change needs it. The
application uses the desktop's standard authorization agent and does not ship
project-specific policy files. Never launch the application as root.

### Run from source

```bash
git clone https://github.com/loofiboss-bit/loofi-fedora-tweaks.git
cd loofi-fedora-tweaks
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev]'
PYTHONPATH=loofi-fedora-tweaks python3 loofi-fedora-tweaks/main.py
```

The `install.sh` helper is intentionally guarded because downloading and
executing a shell script is less auditable than installing a published RPM:

```bash
bash install.sh --i-know-what-i-am-doing
```

## Entry modes

| Mode | Command | Purpose |
| --- | --- | --- |
| GUI | `loofi-fedora-tweaks` | Desktop maintenance control center |
| CLI | `loofi-fedora-tweaks --cli <command>` | Scriptable inspection and reviewed changes |

The CLI surface is intentionally small:

```bash
alias loofi='loofi-fedora-tweaks --cli'

loofi info
loofi check
loofi updates check
loofi troubleshoot profiles
loofi changes list
loofi activity list
loofi doctor
loofi support-bundle
```

Use `--json` before a command when a stable machine-readable envelope is
needed. Changes remain review-first: inspect the plan, confirm it explicitly,
and verify the outcome separately.

## Safety model

- UI views are read-only until they hand an explicit request to Changes.
- Commands are list-based, allowlisted, timeout-bounded, and never use a shell
  interpreter.
- A plan contains a closed action and typed parameters, not an arbitrary command
  supplied by a user or document.
- Fresh preflight, explicit authorization, one mutation lease, and independent
  verification are required for supported persistent changes.
- Unknown platform or deployment detection stays unavailable; it never falls
  back to a traditional Fedora assumption.
- No automatic reboot, retry, rollback, unattended schedule, or remote apply is
  performed.

## Development

Use the repository command surface:

```bash
just test
just lint
just typecheck
just verify
just check-packaging
just validate-release
just build-rpm
just build-sdist
```

Read [AGENTS.md](AGENTS.md), [ARCHITECTURE.md](ARCHITECTURE.md), and
[CONTRIBUTING.md](CONTRIBUTING.md) before changing code.

## Documentation

- [Getting started](docs/BEGINNER_QUICK_GUIDE.md)
- [Full user guide](docs/USER_GUIDE.md)
- [Verified maintenance](docs/VERIFIED_MAINTENANCE.md)
- [State integrity](docs/STATE_INTEGRITY.md)
- [Troubleshooting](docs/TROUBLESHOOTING.md)
- [Documentation index](docs/README.md)
- [Changelog](CHANGELOG.md)

## License

MIT License.
