# Loofi Fedora Tweaks v11.0.0 "Harbor" Release Announcement

## TL;DR

Loofi Fedora Tweaks v11.0.0 "Harbor" is now available with a Unified Action Center, daily maintenance diagnostics, rollback-first guidance, and Support Bundle v7. Fedora KDE 44 remains the stable supported target, while Fedora 45 remains preview-only and advisory.

**Install:**

```bash
pkexec dnf copr enable loofitheboss/loofi-fedora-tweaks
pkexec dnf install loofi-fedora-tweaks
```

**GitHub Release:** https://github.com/loofiboss-bit/loofi-fedora-tweaks/releases/tag/v11.0.0

---

## What's New

- Unified Action Center GUI and CLI for listing, previewing, and inspecting action history.
- Daily Maintenance diagnostics for updates, Flatpak, firmware, failed services, journal warnings, disk usage, package health, and rollback availability.
- Rollback-first guidance for medium/high-risk action candidates.
- Support Bundle v7 fields for Action Center summaries, rollback hints, daemon/API status, maintenance data, and GitHub issue text export.
- Release validation for AppStream and workflow spec version/codename drift.

---

## Installation & Usage

**Fedora 44 via COPR:**

```bash
pkexec dnf copr enable loofitheboss/loofi-fedora-tweaks
pkexec dnf install loofi-fedora-tweaks
```

**Optional runtimes:**

```bash
pkexec dnf install loofi-fedora-tweaks-api
pkexec dnf install loofi-fedora-tweaks-daemon
```

**Run the app or CLI:**

```bash
loofi-fedora-tweaks
loofi-fedora-tweaks --cli info
```

---

## Links

- **GitHub Release**: https://github.com/loofiboss-bit/loofi-fedora-tweaks/releases/tag/v11.0.0
- **Full Changelog**: https://github.com/loofiboss-bit/loofi-fedora-tweaks/blob/master/CHANGELOG.md
- **Architecture Guide**: https://github.com/loofiboss-bit/loofi-fedora-tweaks/blob/master/ARCHITECTURE.md
- **Report Issues**: https://github.com/loofiboss-bit/loofi-fedora-tweaks/issues
