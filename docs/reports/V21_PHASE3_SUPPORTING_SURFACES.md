# V21 Phase 3 Supporting Surfaces and Accessibility

Date: 2026-07-26  
Baseline commit: `841218ef4dbfa6368136bd3d8cbc1c394ec81258`  
Product version: `20.0.0 "Continuity"`  
Active target: `21.0.0 "Resolve"`

## Outcome

Phase 3 makes Specialist Tools scannable and Settings feedback explicit while
preserving the current route, policy, persistence, execution, and platform
contracts. It adds no route, command, database, migration, package, version,
tag, or remote-service change.

## Specialist Tools

- The existing policy-visible Specialist sections are projected into six
  presentation groups: Performance & gaming, Development & local AI, Profiles
  & extensions, Devices & sharing, Agents & automation, and Virtualization.
- Search and group selection filter only the local presentation. Canonical
  route IDs, direct links, policy evaluation, and the destination route tuple
  remain unchanged.
- Activating a direct link that is outside the current filter clears the local
  filter and selects the exact section.
- Group headings, search, selector entries, accessible text, descriptions, and
  tooltips remain available in full-rail, compact, LTR, and RTL presentation.

## Settings

- Appearance, Behavior, and Advanced settings use one nearby title,
  description, control, and feedback row contract.
- Every automatic write reports `Saved` or `Error` in text beside the affected
  control. Feedback does not rely on color.
- `SettingsManager.save()`, `reset()`, and `reset_group()` now return a boolean
  persistence result while preserving their atomic JSON storage behavior.
- The manual theme control is disabled with an explicit `Unavailable`
  dependency explanation while Follow system theme is active.
- Existing settings keys, migrations, routes, reset behavior, Specialist
  component guidance, and theme application remain compatible.

## Responsive and accessibility evidence

The committed Phase 3 matrix renders the real `MainWindow` for:

- 860×560, 900×720, 1366×768, and 1920×1080;
- 100, 125, 150, and 200 percent text scaling;
- system, dark, light, and high-contrast themes;
- LTR and RTL layout directions;
- Settings and Specialist Tools.

That complete product contains 256 cells per backend. All 256 cells pass
offscreen, all 256 pass the current KDE Wayland backend, and all 256 pass Qt's
xcb path through XWayland. The xcb result verifies the X11 Qt path on the
current Wayland host; it is not evidence from a separate native X11 login.
Every run uses a temporary HOME/XDG profile, disables background services,
rejects asynchronous commands and mutating subprocesses, and reports zero
horizontal-scroll, geometry, contrast, focus, keyboard, tooltip,
accessible-name, or RTL issues.

The real Wayland AT-SPI tree separately exposes:

- Settings, Theme, System theme, Notifications, shell navigation, activity
  status, and the confirmation dialog across 424 nodes;
- Development, the Specialist filter, group selector/options, shell
  navigation, activity status, and the confirmation dialog across 432 nodes.

Evidence:

- [Automated offscreen matrix](V21_PHASE3_UI_AUTOMATED.json)
- [KDE Wayland matrix](V21_PHASE3_UI_WAYLAND.json)
- [xcb/XWayland matrix](V21_PHASE3_UI_X11.json)
- [Settings AT-SPI tree](V21_PHASE3_ATSPI_SETTINGS.json)
- [Specialist Tools AT-SPI tree](V21_PHASE3_ATSPI_SPECIALIST.json)
- [Cold-start benchmark](V21_PHASE3_STARTUP.json)

## Verification

- Focused Phase 3, Development, Settings, shared-component, shell, and
  accessibility matrix: `186 passed`.
- Full repository verification: `6,859 passed, 61 skipped`, with `1,057`
  subtests passed.
- Full repository coverage: `86.58%`, above the `86%` gate.
- Full repository lint and mypy: passed.
- Architecture validator: passed.
- All three 256-cell real-window matrices: passed with zero issues.
- Both Wayland AT-SPI supporting-surface probes: passed.
- Startup benchmark, two warmups and seven measured offscreen runs:
  - meaningful Home median: `152.846 ms` (ceiling `250.094 ms`);
  - RSS median: `76,100 KiB` (ceiling `83,582 KiB`);
  - one realized Home provider;
  - zero subprocess probes, active timers, running QThreads, and System Check
    runtime imports.

Product metadata remains v20.0.0. Phase 4 has not started. Packaging,
Traditional/Atomic certification, startup/performance requalification, version
synchronization, tags, commits, pushes, and publication remain outside Phase 3.
