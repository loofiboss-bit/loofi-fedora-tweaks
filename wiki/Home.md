# Loofi Fedora Tweaks Wiki

Welcome to the official wiki for **Loofi Fedora Tweaks** — a modern Fedora control center for maintenance, diagnostics, security, performance, and automation.

**Current Version**: v15.0.0 "Essentials" — Product Simplification
**Screenshots Refreshed**: July 2026

![Loofi Fedora Tweaks Dashboard](images/hero-home.png)

## At a Glance

- **Focused navigation**: Standard mode has six destinations: Home, Software & Updates, System, Network & Security, Desktop, and Settings.
- **One Home**: Saved health, state, update, backup, history, and Action Center signals are summarized without probing or mutating the host at startup.
- **One search surface**: `Ctrl+K` finds routes, settings, and safe action entry points while respecting availability and Standard/Advanced policy.
- **Advanced tools on demand**: AI Lab, Agents, Automation, Community, Teleport, Virtualization, Gaming, Performance, Profiles, Extensions, and Loofi Link remain available through the optional Advanced destination.
- **Safe actions**: Privileged operations use `pkexec`; command preview and execution share the same allowlist, timeout, action metadata, and command-vector checks.
- **State & Recovery**: Read-only State Doctor, privacy-safe backup, plan-before-apply restore, and collector status live in Settings.
- **Verified maintenance**: Software & Updates → Action Center creates expiring plans, rechecks preflight before apply, serializes mutations, and records separate execution and verification results. Interrupted runs never resume automatically.
- **First-Class Atomic Support**: Dedicated `rpm-ostree` diagnostics and upgrade checks for Silverblue/Kinoite.
- 4 run modes: GUI, CLI (`--json`), daemon scheduler, and Web API.
- Privileged actions through `pkexec` (never `sudo`).

## Start Here

- [Installation](Installation)
- [Getting Started](Getting-Started)
- [GUI Tabs Reference](GUI-Tabs-Reference)
- [CLI Reference](CLI-Reference)
- [Screenshots](Screenshots)

## Feature Preview

### Core Workflows

| System Monitor | Maintenance Updates |
| --- | --- |
| ![System Monitor](images/system-monitor.png) | ![Maintenance Updates](images/maintenance-updates.png) |

| Release Readiness | Security and Privacy |
| --- | --- |
| ![Release Readiness](images/release-readiness.png) | ![Security and Privacy](images/security-privacy.png) |

| Upgrade Assistant | Network Connections |
| --- | --- |
| ![Upgrade Assistant](images/upgrade-assistant.png) | ![Network Connections](images/network-connections.png) |

### Advanced Workflows

| Settings Appearance | AI Lab Models |
| --- | --- |
| ![Settings Appearance](images/settings-appearance.png) | ![AI Lab Models](images/ai-lab-models.png) |

| Community Presets | Community Marketplace |
| --- | --- |
| ![Community Presets](images/community-presets.png) | ![Community Marketplace](images/community-marketplace.png) |

## Wiki Pages

### Getting Started

- [Installation](Installation)
- [Getting Started](Getting-Started)
- [FAQ](FAQ)

### Features and Usage

- [GUI Tabs Reference](GUI-Tabs-Reference)
- [CLI Reference](CLI-Reference)
- [Configuration](Configuration)
- [Screenshots](Screenshots)

### Architecture and Development

- [Architecture](Architecture)
- [Plugin Development](Plugin-Development)
- [Security Model](Security-Model)
- [Atomic Fedora Support](Atomic-Fedora-Support)

### Contributing and Support

- [Contributing](Contributing)
- [Testing](Testing)
- [CI/CD Pipeline](CI-CD-Pipeline)
- [Troubleshooting](Troubleshooting)

### Reference

- [Changelog](Changelog)

## Quick Links

- GitHub Repository: [loofiboss-bit/loofi-fedora-tweaks](https://github.com/loofiboss-bit/loofi-fedora-tweaks)
- Latest Release: [v15.0.0](https://github.com/loofiboss-bit/loofi-fedora-tweaks/releases/tag/v15.0.0)
- Issues: [Issue Tracker](https://github.com/loofiboss-bit/loofi-fedora-tweaks/issues)
- Main README: [README.md](https://github.com/loofiboss-bit/loofi-fedora-tweaks/blob/master/README.md)
- Architecture Doc: [ARCHITECTURE.md](https://github.com/loofiboss-bit/loofi-fedora-tweaks/blob/master/ARCHITECTURE.md)

## Support

1. Check [Troubleshooting](Troubleshooting).
2. Search existing [GitHub Issues](https://github.com/loofiboss-bit/loofi-fedora-tweaks/issues).
3. Run `loofi-fedora-tweaks --cli doctor` and `loofi-fedora-tweaks --cli support-bundle`.
4. Open a new issue with Fedora version, desktop environment, repro steps, and logs.
