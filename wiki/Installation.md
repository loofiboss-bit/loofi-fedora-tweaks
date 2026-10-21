# Installation Guide — v35.0.0 "Everyday"

Loofi Fedora Tweaks is distributed as an audited RPM package built specifically for Fedora Linux. The primary supported package channel is the official Fedora COPR repository.

---

## System Requirements

- **Primary v35 platform**: traditional Fedora 44 with KDE Plasma and DNF5.
- **Other environments**: GNOME and Atomic retain existing feature availability boundaries; unsupported actions explain their limitations.
- **Published COPR channel**: Fedora 44 `x86_64`. The application RPM is `noarch`; this does not qualify other architectures or desktop sessions.
- **Runtime Dependencies**: Python 3.12 or newer, PyQt6 (automatically pulled by the RPM).
- **Privilege Separation**: `pkexec` and a standard desktop Polkit authentication agent for executing confirmed changes.

> [!IMPORTANT]
> Never launch `loofi-fedora-tweaks` as `root` or with `sudo`. The application is architected to run unprivileged; authentication is requested on-demand only when applying a reviewed change.

---

## 1. Install via Fedora COPR (Recommended)

The easiest and most reliable way to install and receive automated updates is through the Fedora COPR repository:

```bash
pkexec dnf copr enable loofitheboss/loofi-fedora-tweaks
pkexec dnf install loofi-fedora-tweaks
```

Launch Loofi from your desktop application launcher or run:

```bash
loofi-fedora-tweaks
```

---

## 2. Install Release RPM Directly

If you prefer to install without enabling the COPR repository, download the RPM and published checksums directly from GitHub:

1. Visit the [v35.0.0 Release Page](https://github.com/loofiboss-bit/loofi-fedora-tweaks/releases/tag/v35.0.0).
2. Download `loofi-fedora-tweaks-35.0.0-1.fc44.noarch.rpm` (or the RPM matching your Fedora release) from the release assets.
3. Install the downloaded RPM using DNF:

```bash
pkexec dnf install ./loofi-fedora-tweaks-*.noarch.rpm
```

---

## 3. Run from Source (Development)

For developers and contributors wishing to run from a local git checkout:

```bash
git clone https://github.com/loofiboss-bit/loofi-fedora-tweaks.git
cd loofi-fedora-tweaks
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev]'
PYTHONPATH=loofi-fedora-tweaks python3 loofi-fedora-tweaks/main.py
```

---

## 4. Verifying the Installation

Verify that the CLI and dependencies are healthy:

```bash
# Print installed version
loofi-fedora-tweaks --version

# Run environment self-check
loofi-fedora-tweaks --cli doctor

# Query system facts
loofi-fedora-tweaks --cli --json info
```

---

## 5. Uninstallation

To remove Loofi Fedora Tweaks:

```bash
pkexec dnf remove loofi-fedora-tweaks
```

Uninstalling the package removes application binaries and desktop launchers. Personal configuration (`~/.config/loofi-fedora-tweaks/`) and the Trusted Change Journal (`~/.local/share/loofi-fedora-tweaks/`) are preserved so past maintenance records remain intact.
