# Release Notes -- v15.0.0 "Essentials"

**Release Date:** 2026-07-18
**Codename:** Essentials
**Theme:** A smaller default surface, true lazy loading, and preserved v14 trust

## Summary

Essentials reorganizes Loofi Fedora Tweaks around six clear destinations, one
Home, one search surface, and Standard or Advanced mode. It removes startup work
and duplicate presentation while keeping every supported v14 route, state,
Action Center, Fedora, CLI, API, daemon, and IPC contract intact.

## Highlights

- Exactly six Standard destinations; Advanced adds one optional destination.
- One Home composed from saved health, state, update, backup, history, and Action
  Center signals without probing or mutating the host during startup.
- Data-only plugin specifications and top-level lazy loading: meaningful Home is
  96.66% faster than the recorded v14 baseline, RSS is 29.20% lower, and startup
  subprocess probes, timers, and worker threads are eliminated.
- One policy-backed global search for routes, settings, and safe action entry
  points. Action Center results navigate only.
- Five guided workflows for updates, application installation, slow-system
  diagnosis, disk reclaim analysis, and recovery protection.
- Logical core/specialist component discovery with fail-closed unavailable
  behavior. The evidence did not justify a physical extras RPM in v15.

## Changes

### Changed

- Replaced the default nested sidebar tree with shared destination and secondary
  navigation while preserving stable route IDs and aliases.
- Replaced Beginner/Intermediate/Advanced presentation with Standard/Advanced;
  legacy values migrate idempotently.
- Consolidated the old dashboard into canonical Home and redirected its route to
  System instead of maintaining a second Home.
- Simplified first run, moved Repair Loofi and About into Settings, removed the
  no-op frameless setting, and made activity UI conditional.
- System theme and font are the default for new profiles; explicit packaged
  themes remain available.
- Removed unused `requests` and the base emoji-font dependency; daemon D-Bus
  support remains an optional/runtime subpackage dependency.

### Added

- Pure destination, navigation-policy, migration, search, Home summary, workflow,
  and logical component contracts.
- Shared accessible loading, empty, unavailable, result, progress, disclosure,
  and route-card presentation.
- Deterministic startup and component-boundary analyzers plus core-only runtime
  verification.

### Preserved

- The v14 Action Center plan/confirm/run/verify lifecycle, three-action
  deny-by-default catalog, expiry, re-preflight, lease, history, and interrupted
  run behavior.
- State schemas, atomic I/O, backup/restore, Support Bundle privacy, Traditional
  and Atomic behavior, stable routes/favorites, CLI JSON, read-only API, daemon,
  and IPC contracts.

## Measurements

| Measurement | v14 baseline | v15 final | Change |
| --- | ---: | ---: | ---: |
| Meaningful Home median | 4552.202 ms | 151.924 ms | 96.66% faster |
| RSS median | 107446 KiB | 76068 KiB | 29.20% lower |
| Imported modules | 527 | 288 | 45.35% lower |
| Runtime plugin instances | 29 | 1 | 96.55% lower |
| Startup subprocess probes | 54 | 0 | eliminated |
| Startup active timers / QThreads | 9 / 2 | 0 / 0 | eliminated |

Final test counts, coverage, RPM sizes, artifact hashes, and Fedora review results
are recorded by the release workflow reports tied to the release commit.

## Upgrade Notes

- Existing settings, favorites, aliases, last routes, profiles, first-run
  sentinels, state archives, Action Center plans/runs/history, and support data
  remain readable.
- Legacy experience values migrate to Standard or Advanced. Returning to
  Standard hides specialist routes without deleting their settings or pins.
- Specialist tools remain in the base RPM for v15 and load only when opened.
  No optional package is installed automatically.
- Fedora 44 remains supported; Fedora 45 remains preview/advisory.

## Historical tag note

An older pre-renormalization release used the `v15.0.0` tag for the 2026-02-08
"Nebula" line. Its annotated tag object is preserved on origin as
`legacy-v15.0.0-nebula`, and the conflicting canonical tag was deliberately
removed before Essentials publication. The release pipeline still fails closed
unless the new `v15.0.0` tag peels to the exact release commit.
