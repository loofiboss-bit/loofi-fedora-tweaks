# Loofi Fedora Tweaks Wiki — v30.1.0 "Personalize" local candidate

Welcome to the official documentation for Loofi Fedora Tweaks, a curated
Fedora utility for installing applications, tuning safe settings, diagnosing
problems, and updating the system.

**Current candidate:** v30.1.0 "Personalize" (local and unpublished)

![Loofi Fedora Tweaks Home](images/home-dashboard.png)

## Product principles

1. Browsing, search, and diagnosis do not modify the host.
2. Every persistent mutation uses the internal orchestrator with fresh
   preflight, bounded execution, and independent verification.
3. Traditional Fedora, Atomic, bootc, and unknown backends remain distinct;
   unsupported mutations fail closed.
4. There is no background daemon, web API, arbitrary shell execution,
   automatic retry, rollback, or reboot.
5. Physical environment claims require physical evidence; unrun environments
   remain `unverified`.

The current public release remains v29.0.1 "Utility"; the v30.1.0 candidate
has not been published.

## The five destinations

| Destination | Purpose |
| --- | --- |
| **[Home](GUI-Tabs-Reference#home)** | Fedora profile, status, recommendation, and shortcuts |
| **[Apps](GUI-Tabs-Reference#install)** | Curated app search, source labels, and multi-select review |
| **[Tweaks](GUI-Tabs-Reference#tune)** | Searchable desktop and power settings with current values |
| **[Health](GUI-Tabs-Reference#fix)** | Symptom-first diagnosis and reviewed maintenance |
| **[Updates](GUI-Tabs-Reference#update)** | Independent System, Flatpak, and Firmware cards |

Activity & Recovery and Settings are secondary header surfaces.

## Documentation

- **[Getting Started](Getting-Started)** — installation and first workflows
- **[GUI Reference](GUI-Tabs-Reference)** — the five task destinations
- **[CLI Reference](CLI-Reference)** — bounded read-first CLI commands
- **[Atomic Fedora](Atomic-Fedora-Support)** — immutable deployment behavior
- **[Troubleshooting](Troubleshooting)** — diagnostic and recovery runbooks
- **[Configuration](Configuration)** — XDG state and privacy boundaries
- **[Security Model](Security-Model)** — authorization and execution boundary
- **[Testing](Testing)** — automated and physical qualification rules
- **[Screenshots](Screenshots)** — current interface gallery
- **[Changelog](Changelog)** — release history

## Install

```bash
pkexec dnf copr enable loofitheboss/loofi-fedora-tweaks
pkexec dnf install loofi-fedora-tweaks
loofi-fedora-tweaks
```

Source code and releases are available in the
[GitHub repository](https://github.com/loofiboss-bit/loofi-fedora-tweaks).
Packages are published in the
[Fedora COPR project](https://copr.fedorainfracloud.org/coprs/loofitheboss/loofi-fedora-tweaks/).
