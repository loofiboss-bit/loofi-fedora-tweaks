# Release Notes -- v16.0.0 "Clarity"

**Release Date:** 2026-07-18
**Codename:** Clarity
**Theme:** A responsive, consistent Fedora control center

## Summary

Clarity redesigns the existing PyQt interface around one responsive shell and
one shared component language. It fixes crowded secondary navigation and
inconsistent page structure without changing the trusted system-operation,
state, route, or headless contracts shipped in v15.

## Highlights

- Responsive full-label section navigation replaces application-level tab rows
  that clipped or became unreadable at smaller sizes and larger font scales.
- Home, Software & Updates, System, Network & Security, Desktop, Settings, and
  Advanced use the same scaffold, cards, actions, notices, states, and spacing.
- System, dark, light, and high-contrast themes retain structural styling while
  semantic palettes supply the colors.
- The real `MainWindow` passed a 400-cell theme, mode, viewport, font-scale, and
  English-copy matrix plus live Wayland, Qt `xcb`, keyboard, and AT-SPI checks.
- Release screenshots were regenerated from the exact v16 release tree.

## Changes

### Changed

- Replaced crowded horizontal route tabs with a section rail that collapses to
  a full-width selector below 900 DIP.
- Added explicit data-only section metadata so labels and ordering no longer
  depend on whichever route happens to be loaded first.
- Moved page hierarchy into the shell and shared `PageScaffold`, with one page
  title, bounded content width, responsive grids, and consistent header actions.
- Consolidated Advanced presentation on the same shared system and removed
  superseded inline styling and application-navigation tabs.
- Removed runtime locale loading and the incomplete Swedish catalog; the
  application and release validation now use one complete English interface.

### Preserved

- All stable route IDs, aliases, redirects, favorites, saved routes, navigation
  values, state schemas, archives, and Action Center plans, runs, and history.
- The three-action Action Center catalog and its plan, confirmation, execution,
  lease, interruption, and separate verification rules.
- Traditional Fedora and Atomic Fedora behavior, list-based commands, timeouts,
  package-manager detection, and the `pkexec` privilege boundary.
- Lazy plugin construction and CLI, JSON, API, daemon, D-Bus, IPC, and external
  plugin interfaces.

## Release Measurements

| Measurement | v15 baseline | v16 release | Gate |
| --- | ---: | ---: | ---: |
| Meaningful Home median | 151.924 ms | 181.011 ms | at most 182.309 ms |
| RSS median | 76068 KiB | 77970 KiB | at most 87478 KiB |
| Runtime plugin instances | 1 | 1 | exactly 1 |
| Startup subprocess probes | 0 | 0 | exactly 0 |
| Active timers / QThreads | 0 / 0 | 0 / 0 | exactly 0 / 0 |

The complete test suite and the enforced 85% coverage gate pass. Packaging
includes the base, API, and daemon RPMs, Flatpak bundle, source distribution,
checksums, CycloneDX SBOM, and release provenance.

## Upgrade Notes

- Existing v15 profiles and state migrate in place; no reset is required.
- Standard remains the default. Enabling or disabling Advanced changes route
  visibility without deleting specialist settings or favorites.
- Specialist modules remain in the base RPM. A physical extras split remains
  deferred until a future release can prove non-overlapping ownership.
- Fedora KDE 44 remains supported and Fedora 45 remains preview/advisory.

## Historical tag note

An older pre-renormalization line used `v16.0.0` for the "Horizon" release. Its
annotated tag is preserved as `legacy-v16.0.0-horizon` before the canonical tag
is reassigned to the exact Clarity release commit.
