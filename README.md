# Loofi Fedora Tweaks

<p align="center">
  <img src="loofi-fedora-tweaks/assets/loofi-fedora-tweaks.png" alt="Loofi Fedora Tweaks logo" width="128"/>
</p>

<p align="center">
  <strong>Make Fedora feel like your computer.</strong><br>
  Understand your system, change supported settings, and verify results on Fedora.
</p>

<p align="center">
  <a href="https://github.com/loofiboss-bit/loofi-fedora-tweaks/actions/workflows/ci.yml"><img src="https://img.shields.io/github/actions/workflow/status/loofiboss-bit/loofi-fedora-tweaks/ci.yml?branch=master&style=flat-square&label=CI" alt="CI"/></a>
  <a href="https://copr.fedorainfracloud.org/coprs/loofitheboss/loofi-fedora-tweaks/"><img src="https://img.shields.io/badge/COPR-fedora--44-blue?style=flat-square&logo=fedora" alt="COPR"/></a>
  <img src="https://img.shields.io/badge/Fedora-43_|_44-blue?style=flat-square&logo=fedora" alt="Fedora 43 and 44"/>
  <a href="LICENSE"><img src="https://img.shields.io/badge/License-MIT-blue?style=flat-square" alt="MIT License"/></a>
</p>

![Loofi Fedora Tweaks — Overview](docs/images/control-center/overview-dark-1280x800.png)

## What it does

Start with **Overview** for live resources, available hardware readings, and
recorded maintenance. Then choose the task you want to perform.

| | |
|---|---|
| **Overview** | CPU, memory, GPU, storage, network, temperatures, and battery where supported. Unavailable readings explain why. |
| **Tweaks** | Search a setting, check its current value, review a desktop preset, change it, and verify it. Restore a previous value where supported. |
| **Apps** | Install trusted applications, inspect installed apps and Flatpak metadata permissions, and review scoped removal. |
| **Updates** | Update system packages, Flatpaks, and firmware independently. |
| **Health** | Start from a symptom, inspect the evidence, and apply one reviewed fix. |

The local **v34.0.1 Accord** candidate adds installation-bound Flatpak updates:
check a selected installed application, review one or several updates with
their required dependencies, and verify the resulting commits in the same
installation. Result links lead to Activity and optional existing runtime
maintenance. See [Flatpak updates](docs/FLATPAK_UPDATES.md) and
[candidate qualification](docs/V34_QUALIFICATION.md). This candidate is not yet
a published release.

The published **[v33.0.1 Concord](https://github.com/loofiboss-bit/loofi-fedora-tweaks/releases/tag/v33.0.1)** release puts CPU, RAM, GPU,
and storage first in Overview; combines Settings and Profiles in Tweaks;
separates Catalog, Installed, and Sources in Apps; and retains each operation's
origin, result, and return path across navigation. Four resumable guides keep
saved progress and open existing review and verification flows.

Published on 2026-10-12 (Europe/Stockholm), with a Fedora 44 package available
from COPR. Version 33.0.0 remains assigned to the historical Bastion tag.
The maintainer authorized a VM E2E exception after two failed candidate runs,
including an unresolved guest Qt6Gui crash. All other release gates passed.
See the [release notes](docs/releases/RELEASE-NOTES-v33.0.1.md),
[public publication evidence](docs/reports/V33.0.1_RELEASE_PUBLICATION.md), and
[qualification report](docs/V33_QUALIFICATION.md) for exact results and limits.
KDE on traditional Fedora with DNF5 is the first target; GNOME, Atomic,
physical hardware, and human screen-reader behavior retain their documented
evidence limits.

The release builds on Routine's installation comparisons, Health storage guide,
manual DNF5 restart advice and saved profile comparisons; Personal's broader
RPM application discovery, editable profile copies and reviewed KDE controls;
and Companion's profile library, explained Flatpak access, Health comparisons,
screen-sharing diagnostics and Fedora upgrade preparation. The dated
[qualification reports](docs/GUIDE_VERIFICATION.md) record evidence collected
for those releases; they do not qualify later changes.
Open **Tools** in the sidebar for System, Storage,
Network, Security, and Logs. See the [product definition](docs/PRODUCT.md) for
what is, and is not, in scope.

## Install

```bash
pkexec dnf copr enable loofitheboss/loofi-fedora-tweaks
pkexec dnf install loofi-fedora-tweaks
```

Then launch **Loofi Fedora Tweaks** from the desktop menu, or run
`loofi-fedora-tweaks`. Authorization is requested only when a change needs it.
Never run the application as root.

### Run from source

```bash
git clone https://github.com/loofiboss-bit/loofi-fedora-tweaks.git
cd loofi-fedora-tweaks
python3 -m venv .venv && source .venv/bin/activate
python -m pip install -e '.[dev]'
PYTHONPATH=loofi-fedora-tweaks python3 loofi-fedora-tweaks/main.py
```

## Command line

```bash
loofi-fedora-tweaks --cli tweaks list
loofi-fedora-tweaks --cli tweaks preset list
loofi-fedora-tweaks --cli tweaks preset preview reduced-motion
loofi-fedora-tweaks --cli tweaks preset apply file-navigation --yes
loofi-fedora-tweaks --cli apps list
loofi-fedora-tweaks --cli apps permissions app/org.mozilla.firefox/x86_64/stable --installation user
loofi-fedora-tweaks --cli apps details app/org.mozilla.firefox/x86_64/stable --installation user
loofi-fedora-tweaks --cli apps unused --installation user
loofi-fedora-tweaks --cli updates check
loofi-fedora-tweaks --cli updates sources
loofi-fedora-tweaks --cli updates flatpaks --installation user
loofi-fedora-tweaks --cli updates diagnose --source flatpak
loofi-fedora-tweaks --cli tweaks profile library list
loofi-fedora-tweaks --cli apps access app/org.mozilla.firefox/x86_64/stable --installation user
loofi-fedora-tweaks --cli updates prepare-upgrade --target 44
loofi-fedora-tweaks --cli apps compare org.mozilla.firefox
loofi-fedora-tweaks --cli updates restart-advice
loofi-fedora-tweaks --cli tweaks profile library compare focus privacy-basics
```

Add `--json` before a command for machine-readable output.

## Safety

- The interface never runs arbitrary commands. Commands are allow-listed,
  list-based, time-limited, and never use a shell.
- Privileged changes go through the desktop's standard authorization agent.
- Every change is checked after it is applied. Previous values can be restored
  where verified history supports it; other actions show their recovery guidance.
- Nothing reboots, retries, or applies changes remotely on its own.

## Development

```bash
just test        # test suite
just lint        # flake8
just typecheck   # mypy
just verify      # all of the above plus coverage
```

See [CONTRIBUTING](CONTRIBUTING.md), [ARCHITECTURE](ARCHITECTURE.md), and the
[design system](DESIGN.md).

## Documentation

[User guide](docs/USER_GUIDE.md) · [Getting started](docs/BEGINNER_QUICK_GUIDE.md) ·
[Troubleshooting](docs/TROUBLESHOOTING.md) · [Roadmap](ROADMAP.md) ·
[Changelog](CHANGELOG.md)

## License

MIT

### Everyday workflows

Overview prioritizes recorded next steps. Updates restores pending verification
after reopening without repeating an update. Tweaks supports [portable profiles](docs/TWEAK_PROFILES.md),
reviewed desktop presets, and a focused check for one setting. Apps lists installed
Flatpaks by installation, shows metadata permissions, and preserves app data when
reviewing removal. Health provides read-only sound and Bluetooth diagnostics. See
[qualification](docs/EVERYDAY_VERIFICATION.md) for separately dated local evidence.
