# Loofi Fedora Tweaks v10.0.0 "Waypoint" Release Announcement

## TL;DR

Loofi Fedora Tweaks v10.0.0 "Waypoint" is now available with a guided Upgrade Assistant for Fedora release planning. Fedora KDE 44 remains the stable supported target, while Fedora 45 is available as a preview planning profile with read-only checks, risk explanations, command previews, verification, and support export.

**Install:**

```bash
pkexec dnf copr enable loofitheboss/loofi-fedora-tweaks
pkexec dnf install loofi-fedora-tweaks
```

**GitHub Release:** https://github.com/loofiboss-bit/loofi-fedora-tweaks/releases/tag/v10.0.0

---

## What's New

- Upgrade Assistant launched from Home and Maintenance.
- Fedora 45 preview checks for repo config relocation, Python 3.15 packaging risk, IPv6-mostly NetworkManager behavior, Podman 6, Atomic Flatpak filtering, RPM/OpenSSL/certificate compatibility, and KDE/PackageKit-DNF5 consistency.
- Readiness CLI commands for planning, explaining checks, and exporting support bundles.
- Support Bundle v6 fields for release plans, target changes, action history, update preview, and redacted package/repo health details.
- User guide and wiki screenshots regenerated from the v10 PyQt UI.

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

- **GitHub Release**: https://github.com/loofiboss-bit/loofi-fedora-tweaks/releases/tag/v10.0.0
- **Full Changelog**: https://github.com/loofiboss-bit/loofi-fedora-tweaks/blob/master/CHANGELOG.md
- **Architecture Guide**: https://github.com/loofiboss-bit/loofi-fedora-tweaks/blob/master/ARCHITECTURE.md
- **Report Issues**: https://github.com/loofiboss-bit/loofi-fedora-tweaks/issues
