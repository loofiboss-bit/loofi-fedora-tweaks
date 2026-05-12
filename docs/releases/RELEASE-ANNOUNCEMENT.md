# Loofi Fedora Tweaks v8.0.0 "Beacon" Release Announcement

## TL;DR

Loofi Fedora Tweaks v8.0.0 "Beacon" is now available as the navigation reliability release. It adds stable route IDs across the sidebar, command palette, quick actions, dashboard cards, and favorites while hardening command safety and packaging validation.

**Install:**

```bash
pkexec dnf copr enable loofitheboss/loofi-fedora-tweaks
pkexec dnf install loofi-fedora-tweaks
```

**GitHub Release:** https://github.com/loofiboss-bit/loofi-fedora-tweaks/releases/tag/v8.0.0

---

## What's New

- Central route manifest for plugin-level and subroute-level navigation.
- Route-aware command palette, quick actions, dashboard cards, favorites, sidebar selection, and breadcrumbs.
- Favorites v2 migration to stable IDs such as `maintenance:updates` and `software:apps`.
- Icon-only collapsed sidebar with tooltips, status dots, QSS styling, and semantic icon fallbacks.
- Shared command allowlist for preview, execute, web API executor, and ProfileManager snapshot commands.
- Blocking RPM import check plus packaging manifest validation for wheel/sdist contents and entry points.

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

- **GitHub Release**: https://github.com/loofiboss-bit/loofi-fedora-tweaks/releases/tag/v8.0.0
- **Full Changelog**: https://github.com/loofiboss-bit/loofi-fedora-tweaks/blob/master/CHANGELOG.md
- **Architecture Guide**: https://github.com/loofiboss-bit/loofi-fedora-tweaks/blob/master/ARCHITECTURE.md
- **Report Issues**: https://github.com/loofiboss-bit/loofi-fedora-tweaks/issues
