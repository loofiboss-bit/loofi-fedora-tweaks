# Loofi Fedora Tweaks v12.0.0 "Lighthouse" Release Announcement

## TL;DR

Loofi Fedora Tweaks v12.0.0 "Lighthouse" is now available with My Fedora Today health snapshots, trend-aware Action Center recommendations, read-only daemon collection, and Support Bundle v8. Fedora KDE 44 remains the stable supported target, while Fedora 45 remains preview-only and advisory.

**Install:**

```bash
pkexec dnf copr enable loofitheboss/loofi-fedora-tweaks
pkexec dnf install loofi-fedora-tweaks
```

**GitHub Release:** https://github.com/loofiboss-bit/loofi-fedora-tweaks/releases/tag/v12.0.0

---

## What's New

- My Fedora Today health timeline for bounded, privacy-safe snapshots.
- Trend-aware Action Center recommendations for recurring, new, resolved, and worsening maintenance signals.
- Read-only daemon/API health snapshot collection without automatic repairs or background upgrades.
- Support Bundle v8 fields for snapshots, timelines, recurring fingerprints, recommendations, daemon snapshot status, and GitHub issue text export.
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

- **GitHub Release**: https://github.com/loofiboss-bit/loofi-fedora-tweaks/releases/tag/v12.0.0
- **Full Changelog**: https://github.com/loofiboss-bit/loofi-fedora-tweaks/blob/master/CHANGELOG.md
- **Architecture Guide**: https://github.com/loofiboss-bit/loofi-fedora-tweaks/blob/master/ARCHITECTURE.md
- **Report Issues**: https://github.com/loofiboss-bit/loofi-fedora-tweaks/issues
