# Release Notes -- v21.0.0 "Resolve"

**Release Date:** 2026-07-26
**Codename:** Resolve
**Theme:** Coherent verified work and deterministic application teardown

## Summary

Resolve connects the current Fedora control center into one understandable
See → Understand → Review → Apply → Verify journey. The release changes
presentation and application-owned lifecycle coordination without adding new
execution authority, persistence, remote mutation, or background collection.

## Highlights

- One truthful Home summary and primary next step over existing state.
- Explicit application review handoffs before Action Center confirmation.
- State-driven System Check and Activity & Recovery presentation.
- Grouped, searchable Specialist Tools and consistent Settings feedback.
- Responsive, accessible route and local-view navigation.
- Deterministic cleanup of EventBus, scheduler, QThread, timer, Pulse, and
  plugin resources.

## Changes

### Added

- PyQt-free `ApplicationRuntime` and immutable `GuidedTask` contracts.
- `LocalViewSwitcher` for two to five peer views inside one route.
- Explicit journal presentation states for initial, loading, empty, partial,
  truncated, loaded, selected, recoverable, manual-only, and error cases.
- Release qualification evidence for responsive geometry, RTL, AT-SPI,
  Wayland, X11, startup resources, Fedora 44, and package formats.

### Changed

- Home is bounded to one summary, one primary task, three attention items, four
  common tasks, active work, and latest activity.
- Software application controls now say `Review install` and `Review removal`.
- System Check uses local Overview, Findings, and History views without changing
  its stable routes or persisted results.
- Specialist Tools are grouped and locally filtered; Settings uses shared rows
  with truthful persistence feedback.

### Fixed

- Exact EventBus and AgentScheduler subscriptions are removed during shutdown.
- Meaningful Home starts no hidden probes or timers, and deferred dependency UI
  cannot run after window teardown.
- Compact navigation avoids horizontal scrolling and no longer exposes internal
  route identifiers.
- Lifecycle regression coverage now includes the Ubuntu CI timing that
  previously allowed a deferred dependency check to outlive a closed window.

## Stats

- **Tests:** 6,863 passed, 61 expected skips, 1,057 subtests, 0 failed
- **Lint:** 0 errors
- **Coverage:** 86.57%

## Upgrade Notes

- Existing settings, favorites, routes, aliases, saved navigation, System Check
  results, activity history, Action Center plans/runs, and support evidence are
  retained.
- Fedora 44 remains the supported Traditional and Atomic target. Fedora 45
  remains preview-only.
- No automatic reboot, retry, rollback, resume, or broadened parameter behavior
  is introduced.
- Historical occupied v21 tags are retained as
  `legacy-v21.0.0-ux-stabilization` and
  `legacy-v21.0.1-python-jose-packaging`.
