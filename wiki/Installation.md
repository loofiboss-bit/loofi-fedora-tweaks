# Installation — v27.0.1 "Core"

Loofi Fedora Tweaks is distributed as one Fedora RPM. The supported package
source is the Loofi COPR project; an sdist is available for development.

## Requirements

- Fedora 43 or 44 for the stable target; Fedora 45 is preview-only.
- Python 3.12 or newer (provided by the RPM/runtime environment).
- PyQt6 and a working desktop session for the GUI.
- `pkexec` and the desktop's standard authorization agent for reviewed
  privileged changes.

The core is desktop-neutral and detects GNOME, KDE, XFCE, Sway, and unknown
sessions without assuming that a missing capability is supported. Traditional
and Atomic/bootc backends are kept separate; an unknown backend is unavailable.

## Install from COPR (recommended)

```bash
pkexec dnf copr enable loofitheboss/loofi-fedora-tweaks
pkexec dnf install loofi-fedora-tweaks
loofi-fedora-tweaks
```

The package installs the GUI, reduced CLI, desktop entry, and documentation.
It does not install a daemon, local Web API, custom Polkit policy files, or a
Flatpak application bundle.

## Install a release RPM

Download the RPM from the [GitHub release page](https://github.com/loofiboss-bit/loofi-fedora-tweaks/releases/tag/v27.0.1),
then install it with the native backend:

```bash
pkexec dnf install ./loofi-fedora-tweaks-*.noarch.rpm
```

On an Atomic/bootc host, use the host's documented image/package workflow;
Loofi reports the capability and reboot state but never reboots automatically.

## Run from source

```bash
git clone https://github.com/loofiboss-bit/loofi-fedora-tweaks.git
cd loofi-fedora-tweaks
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev]'
PYTHONPATH=loofi-fedora-tweaks python3 loofi-fedora-tweaks/main.py
```

The optional `install.sh` helper is guarded and requires an explicit
acknowledgement. Never run the application as root.

## Verify the installation

```bash
loofi-fedora-tweaks --version
loofi-fedora-tweaks --cli --json info
loofi-fedora-tweaks --cli doctor
```

Physical desktop, authorization, reboot, and fresh Atomic installation gates
are separate evidence and remain unverified for v27.0.1.
