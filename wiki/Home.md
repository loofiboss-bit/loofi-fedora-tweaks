# Loofi Fedora Tweaks Wiki — v35.0.0 "Everyday"

Loofi Fedora Tweaks brings application management, desktop settings, maintenance
and verified operation history together, prioritizing traditional Fedora KDE
with DNF5.

**Release:** [v35.0.0 Everyday](https://github.com/loofiboss-bit/loofi-fedora-tweaks/releases/tag/v35.0.0).
Search local AppStream catalogs, review complete RPM/Flatpak transactions, remove
RPM applications and choose optional reviewed sources/codecs in Get Fedora ready.
Guides require verified results for change steps; interrupted work never resumes
a mutation automatically.

See [release notes](https://github.com/loofiboss-bit/loofi-fedora-tweaks/blob/master/docs/releases/RELEASE-NOTES-v35.0.0.md)
and [qualification](https://github.com/loofiboss-bit/loofi-fedora-tweaks/blob/master/docs/V35_QUALIFICATION.md).
The known Qt accessibility defect remains disclosed. Native VM matrices are
optional under the maintainer's risk-based release policy; local checks do not
establish physical desktop qualification.

**Previous public release:** [v33.0.1 Concord](https://github.com/loofiboss-bit/loofi-fedora-tweaks/releases/tag/v33.0.1).

![Loofi Fedora Tweaks Overview](images/overview.png)

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

Physical GNOME, KDE, Atomic, Polkit, keyboard, Orca, and scaling checks remain
unverified; automated qualification is recorded in the release notes.

## The six destinations

| Destination | Purpose |
| --- | --- |
| **[Overview](GUI-Tabs-Reference#overview)** | CPU, memory, GPU, storage, recorded state and guidance |
| **[Tweaks](GUI-Tabs-Reference#tweaks)** | Settings and Profiles, scope, review, verification and restore |
| **[Apps](GUI-Tabs-Reference#apps)** | Catalog, Installed, Sources and exact selected-app review |
| **[Updates](GUI-Tabs-Reference#updates)** | Independent System, Flatpak and Firmware operations |
| **[Health](GUI-Tabs-Reference#health)** | Symptom diagnostics and reviewed recovery |
| **[Activity](GUI-Tabs-Reference#activity)** | Recorded outcomes and eligible restoration |

Tools contains advanced destinations; Settings stays in the sidebar footer.

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
