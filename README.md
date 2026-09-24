# Loofi Fedora Tweaks v30.1.0 "Personalize"

<!-- markdownlint-configure-file {"MD033": false} -->

<p align="center">
  <img src="loofi-fedora-tweaks/assets/loofi-fedora-tweaks.png" alt="Loofi Fedora Tweaks logo" width="128"/>
</p>

<p align="center">
  <strong>A curated Fedora utility</strong><br>
  Find apps, adjust your desktop, maintain health, and update Fedora.
</p>

![Loofi Fedora Tweaks Home](docs/images/user-guide/home-dashboard.png)

<p align="center">
  <a href="https://github.com/loofiboss-bit/loofi-fedora-tweaks/releases/tag/v30.1.0">
    <img src="https://img.shields.io/badge/Release-v30.1.0-blue?style=for-the-badge&logo=github" alt="Loofi Fedora Tweaks v30.1.0 release"/>
  </a>
  <img src="https://img.shields.io/badge/Fedora-43_|_44-blue?style=for-the-badge&logo=fedora" alt="Fedora 43 and 44"/>
  <img src="https://img.shields.io/badge/Python-3.12+-green?style=for-the-badge&logo=python" alt="Python 3.12 or newer"/>
</p>

## What Loofi does

Loofi Fedora Tweaks brings common Fedora jobs into one small, desktop-neutral
utility. The interface is organised around the work users want to complete:

- **Apps** — find trusted applications, select several, and see a result for
  each installation.
- **Tweaks** — search supported GNOME, KDE, and power settings, change one
  value, and see its verified result in place.
- **Health** — start from a symptom, inspect evidence, run storage maintenance, or apply one verified repair
  or open the correct native settings page.
- **Updates** — update system packages, Flatpaks, and firmware independently.

Home is the launchpad. Activity & Recovery is the secondary place for
pending verification, reboot follow-up, failures, and recovery guidance. The
internal Action Center execution engine remains the safety boundary but is not a
normal user-facing destination.

v30.1.0 includes the v30.0.1 stability work and is distributed through the
[GitHub release](https://github.com/loofiboss-bit/loofi-fedora-tweaks/releases/tag/v30.1.0)
and the Fedora COPR repository. Installation on this workstation is a separate action.

The v30.0.1 automated qualification is recorded separately. Physical desktop,
authorization, reboot, Atomic, keyboard, and Orca checks for v30.1.0 remain
`unverified` until run. Offscreen results do not establish physical qualification.

The maintained repository-wide line-coverage gate is 85%.

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
loofi activity list
loofi doctor
loofi support-bundle
```

Use `--json` before a command for machine-readable output. JSON schemas are
command-specific, so automation should validate the selected command's shape.
The CLI remains review-first: inspect saved state, confirm an explicit
compatibility plan when needed, and verify the outcome separately. The GUI
uses the same internal orchestrator but presents compact confirmation and
verified results on the page where the action started.

## Safety model

- UI views do not run arbitrary commands. Supported everyday actions start
  from their owning page through the shared operation controller.
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
