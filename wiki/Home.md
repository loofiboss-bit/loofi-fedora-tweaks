# Loofi Fedora Tweaks Wiki

Welcome to the official documentation and wiki for **Loofi Fedora Tweaks**.

Loofi Fedora Tweaks is a focused, desktop-neutral maintenance control center for Fedora Linux. It unifies system diagnostics, multi-source updates, hardware health, and verified system changes into a single, safe desktop interface and scriptable CLI.

**Current public release:** v28.0.2 "Ease"<br>
**Target distributions:** Fedora 43 and 44 (Stable) • Fedora 45 (Preview)

![Loofi Fedora Tweaks Home](images/home-dashboard.png)

---

## Core Principles

1. **Read-Only Inspection**: Browsing views, auditing services, checking updates, and running diagnostics never modifies your system.
2. **Action Center Boundary**: Every persistent system change must be reviewed as a typed plan in **Changes** before execution.
3. **Independent Verification**: Command exit codes are never trusted alone; changes are independently probed and verified post-execution.
4. **Desktop & Architecture Neutral**: Works consistently across GNOME, KDE Plasma, XFCE, Sway, and other environments.
5. **Traditional & Atomic Awareness**: Keeps standard DNF5 workflows cleanly separated from `rpm-ostree` and `bootc` immutable deployments.
6. **No Background Daemons**: Zero background services, zero telemetry, and zero memory overhead when closed.

---

## The Five Destinations

The unified interface is organized into five primary destinations:

| Destination | Purpose | Key Capabilities |
| --- | --- | --- |
| **[Home](GUI-Tabs-Reference#1-home-dashboard)** | System overview & state | Environmental snapshot, single recommended action, quick tasks |
| **[Updates & Apps](GUI-Tabs-Reference#2-updates--apps)** | Multi-stream updates | Independent DNF5, Flatpak, and fwupd firmware updates; AppStream handoff |
| **[System Health](GUI-Tabs-Reference#3-system-health)** | Diagnostics & hardware | System check, symptom troubleshooting, storage reclaim, hardware monitor |
| **[Protection & Recovery](GUI-Tabs-Reference#4-protection--recovery)** | Security & rollbacks | Firewall zone audits, Btrfs/Atomic rollbacks, Trusted Change Journal |
| **[Changes](GUI-Tabs-Reference#5-changes-the-action-center)** | Action Center workspace | The single authority for plan review, Polkit authorization, and verification |

---

## Documentation Directory

### User Guides & Reference
- **[Getting Started](Getting-Started)** — 10-minute setup, installation from COPR, and first run walkthrough.
- **[GUI Destinations Guide](GUI-Tabs-Reference)** — Comprehensive breakdown of all five tabs, workflows, and settings.
- **[Fedora Tweaks & Maintenance](Fedora-Tweaks-Guide)** — Practical guide to package caching, ZRAM swap, battery charge thresholds, journal vacuuming, and Flatpak hygiene.
- **[Atomic & Immutable Fedora](Atomic-Fedora-Support)** — Using Loofi on Fedora Silverblue, Kinoite, Bazzite, CoreOS, and bootc systems.
- **[CLI Reference](CLI-Reference)** — Full guide to the 8 bounded CLI commands, command-specific JSON payloads, and scripting examples.
- **[Screenshots Gallery](Screenshots)** — Visual showcase of all primary screens and workflows.

### Operations & Diagnostics
- **[Troubleshooting Runbooks](Troubleshooting)** — Step-by-step diagnosis recipes for startup, Polkit, package locks, and support bundle generation.
- **[Configuration & State](Configuration)** — XDG storage paths, atomic state persistence, versioned schemas, and privacy boundaries.
- **[Frequently Asked Questions](FAQ)** — Common questions regarding permissions, safety, desktop environments, and features.

### Architecture & Development
- **[Architecture Overview](Architecture)** — Architectural design, module boundaries (`ui/`, `core/`, `services/`, `cli/`), and PlatformProfile.
- **[Security Model](Security-Model)** — Privilege separation, `pkexec` execution, allowlisted subprocesses, and mutation lease isolation.
- **[Contributing](Contributing)** — Contributor guidelines, development environment setup, and coding conventions.
- **[Testing & Quality Gates](Testing)** — Test execution, coverage requirements, and release verification gates.
- **[CI/CD Automation](CI-CD-Pipeline)** — GitHub Actions workflows, CodeQL security analysis, and automated release validation.
- **[Provider Architecture](Plugin-Development)** — Internal product catalog, provider contracts, and action definitions.
- **[Release Changelog](Changelog)** — Complete historical changelog.

---

## Quick Install

Enable the Fedora COPR repository and install the verified RPM:

```bash
pkexec dnf copr enable loofitheboss/loofi-fedora-tweaks
pkexec dnf install loofi-fedora-tweaks
loofi-fedora-tweaks
```

To use the scriptable command-line interface:

```bash
alias loofi='loofi-fedora-tweaks --cli'

loofi info
loofi check
loofi updates check
loofi doctor
```

---

## Community & Support

- **Source Code**: [GitHub Repository](https://github.com/loofiboss-bit/loofi-fedora-tweaks)
- **Issue Tracker**: [GitHub Issues](https://github.com/loofiboss-bit/loofi-fedora-tweaks/issues)
- **Release Packages**: [Fedora COPR](https://copr.fedorainfracloud.org/coprs/loofitheboss/loofi-fedora-tweaks/)
- **Latest Release**: [v28.0.2 Ease on GitHub](https://github.com/loofiboss-bit/loofi-fedora-tweaks/releases/tag/v28.0.2)
