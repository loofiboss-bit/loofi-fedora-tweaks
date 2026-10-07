# Loofi Fedora Tweaks 32.3.0 — Clarity

Clarity introduces a polished, compact UI design optimized for zero-scroll navigation on standard desktop displays, alongside first-class Wayland app icon integration.

## Highlights

- **Desktop & Wayland App Icon Integration**: Configured `setDesktopFileName("loofi-fedora-tweaks")` and explicit fallback window icons, ensuring correct icon binding across KDE Plasma KWin, GNOME Shell Mutter, and Wayland docks. High-resolution application icons are installed to both `/usr/share/pixmaps/` and `/usr/share/icons/hicolor/512x512/apps/`.
- **Zero-Scroll Overview Experience**: The Overview page now fits completely without vertical scrolling on 1280x800+ displays:
  - System temperature sensors are presented in a compact 2-column horizontal grid instead of an oversized vertical list.
  - Metric graphs feature anti-aliased gradient area fills and streamlined 44px sparklines.
  - Empty status cards are conditionally hidden during nominal operations to eliminate dead space.
- **Compact & Responsive Tweaks Workflow**:
  - Setting rows dynamically adapt with an intelligent breakpoint (>= 500px), preventing controls from wrapping onto secondary lines on standard windows.
  - Tightened row padding and balanced margins display 8–10 tweaks concurrently in the viewport.
  - Consolidated toolbar with search, refresh, cancel, and profile management on a primary row, and categories and filter pills on a dedicated secondary row.

## Qualification

- All 4,780 unit and integration tests passed.
- Flake8 linting and MyPy static type checking passed with zero errors.
- Architecture validation (module line budgets, stabilization rules, and >= 85% type annotations) fully verified.
- RPM package builds cleanly and installs on Fedora 44 with desktop file integration verified.

## Install

Download the RPM asset below and install it on Fedora with:

```bash
pkexec dnf install ./loofi-fedora-tweaks-32.3.0-*.rpm
```

Existing application settings, presets, and history remain safely preserved in the user's home directory.
