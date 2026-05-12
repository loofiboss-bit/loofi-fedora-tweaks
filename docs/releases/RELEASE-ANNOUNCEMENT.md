# Loofi Fedora Tweaks v8.1.0 "Breeze" Release Announcement

## TL;DR

Loofi Fedora Tweaks v8.1.0 "Breeze" is now available as the focused UI/UX redesign release. It keeps the v8 route architecture, but replaces the crowded default menu with five primary areas, roomier pages, clearer headers, and responsive sizing for Wayland and fractional scaling.

**Install:**

```bash
pkexec dnf copr enable loofitheboss/loofi-fedora-tweaks
pkexec dnf install loofi-fedora-tweaks
```

**GitHub Release:** https://github.com/loofiboss-bit/loofi-fedora-tweaks/releases/tag/v8.1.0

---

## What's New

- Five default navigation areas: Home, Software & Updates, System & Hardware, Network & Security, and Desktop & Settings.
- Advanced tools stay searchable, favoriteable, route-compatible, and available in Advanced mode without crowding the sidebar.
- Shared layout primitives for airy page headers, sections, action rows, route cards, and adaptive grids.
- Wayland-friendly sizing based on Qt device-independent units, font metrics, and available screen geometry.
- Dark, light, and high-contrast themes updated with calmer spacing, selected states, card borders, and wrapping rules.
- User guide and wiki screenshots regenerated from the redesigned PyQt UI.

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

- **GitHub Release**: https://github.com/loofiboss-bit/loofi-fedora-tweaks/releases/tag/v8.1.0
- **Full Changelog**: https://github.com/loofiboss-bit/loofi-fedora-tweaks/blob/master/CHANGELOG.md
- **Architecture Guide**: https://github.com/loofiboss-bit/loofi-fedora-tweaks/blob/master/ARCHITECTURE.md
- **Report Issues**: https://github.com/loofiboss-bit/loofi-fedora-tweaks/issues
