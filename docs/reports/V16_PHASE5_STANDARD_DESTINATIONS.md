<!-- Hallmark · pre-emit critique: P5 H5 E5 S5 R5 V4 -->

# v16.0.0 "Clarity" Phase 5 Standard Destinations

**Status:** implemented and verified locally

**Authority:** [`docs/plans/LOOFI_FEDORA_TWEAKS_V16_PLAN.md`](../plans/LOOFI_FEDORA_TWEAKS_V16_PLAN.md)

**Working branch:** `v16-clarity`

## Outcome

Phase 5 brings Software & Updates, Network & Security, Desktop, and Settings
onto the shell and component contracts established in Phases 2 and 3. Their
application-level `QTabWidget` navigation is replaced by route-owned stacks,
each route renders through `PageScaffold`, shell-owned titles are not repeated,
and destination roots use zero margins.

Maintenance and Backup are included because they are routes within Software &
Updates and Network & Security. All six Standard destinations now use the same
shell navigation and scaffold contract. No Standard route falls back to the
superseded internal-tab presentation.

The application remains `15.0.0 "Essentials"`. Existing operations,
confirmations, routes, aliases, Action Center behavior, Traditional/Atomic
branches, CLI, API, daemon, IPC, and version metadata are unchanged.

## Destination contracts

### Software & Updates

- Applications, Repositories, Flatpak, Updates, Cleanup, Atomic Overlays,
  Upgrade Assistant, and Action Center are scaffolded route pages.
- Search and filtering remain visible before the application catalogue.
- Analysis, review, and mutation controls retain their existing separation and
  safety behavior.
- Action Center remains a distinct review, plan, execute, verify, and recovery
  workflow rather than becoming another update button.

### Network & Security

- Connections, DNS, privacy, monitoring, security overview, firewall, privacy
  controls, and port exposure are separate route pages.
- Raw command output and security activity remain available behind collapsed
  disclosures instead of dominating the initial state.
- Backup now states explicitly that Timeshift, Snapper, and Btrfs backups are
  separate from Loofi recovery points under System.
- Existing firewall, port, privacy, backup, and restore operations are
  unchanged.

### Desktop

- Window rules, appearance, and display management use shell-selected stacked
  pages with one scaffold each.
- Appearance, display, and window-management controls remain grouped by user
  task without a second application navigator.
- Existing preview, apply, detection, and session behavior is unchanged.

### Settings

- Appearance, Behavior, Advanced Tools, Repair Loofi, and About are selected by
  the shell navigator rather than an internal tab bar.
- Theme choice, Follow System Theme, reset actions, and state controls use the
  existing semantic theme and shared action components.
- Follow System Theme behavior and settings persistence are unchanged.

## Shared presentation contract

- `PageScaffold` owns route title, description, content spacing, and optional
  actions.
- `QStackedWidget` owns route content; the application shell remains the sole
  owner of section navigation.
- `DetailsDisclosure` now accepts caller-owned widgets so existing command
  output toolbars and logs can remain accessible while collapsed by default.
- `ActionBar`, shared buttons, notices, loading states, empty states, and
  unavailable states are reused where their established semantics apply.
- No new color, typography, animation, or one-off styling values were added.

## Visual evidence

The reproducible offscreen capture uses the real `MainWindow`, Standard mode,
temporary HOME/XDG state, disabled background services and host probes, and a
guard that rejects asynchronous commands.

| Viewport | Software & Updates | Network & Security | Desktop | Settings |
| --- | --- | --- | --- | --- |
| 860 × 720 | [`software-updates__860x720.png`](../images/v16/phase5/software-updates__860x720.png) | [`network-security__860x720.png`](../images/v16/phase5/network-security__860x720.png) | [`desktop__860x720.png`](../images/v16/phase5/desktop__860x720.png) | [`settings__860x720.png`](../images/v16/phase5/settings__860x720.png) |
| 1918 × 1018 | [`software-updates__1918x1018.png`](../images/v16/phase5/software-updates__1918x1018.png) | [`network-security__1918x1018.png`](../images/v16/phase5/network-security__1918x1018.png) | [`desktop__1918x1018.png`](../images/v16/phase5/desktop__1918x1018.png) | [`settings__1918x1018.png`](../images/v16/phase5/settings__1918x1018.png) |

Hashes, dimensions, capture policy, and the reproduction command are recorded
in [`V16_PHASE5_SCREENSHOTS.json`](V16_PHASE5_SCREENSHOTS.json).

The visual review found no repeated shell titles, nested application tab bars,
dominant raw logs, decorative card nesting, invented product claims, or
destination-specific styling. The desktop application uses its existing KDE
theme, icon, focus, and motion contracts; web-only Hallmark gates are not
applicable.

## Workflow and startup evidence

The five canonical workflows pass with zero host probes and zero mutations:
update system, install application, diagnose a slow system, free disk space,
and protect/recover.

The clean offscreen startup benchmark still realizes only `atlas_dashboard`.
All five measured runs recorded zero subprocess probes, zero active timers, and
zero running `QThread` instances. Timing remains diagnostic in Phase 5; the
controlled performance gate belongs to Phase 8. Raw data is retained in
[`V16_PHASE5_STARTUP.json`](V16_PHASE5_STARTUP.json).

## Verification

| Gate | Result |
| --- | --- |
| `just verify` | Passed |
| Full test suite | 7,713 passed, 40 skipped, 820 subtests |
| Coverage | 86.34% (85% required) |
| Focused Phase 5 destination tests | Passed |
| Existing destination regression tests | Passed |
| Five canonical workflows | Passed; 0 host probes and 0 mutations |
| Eight-frame real-`MainWindow` capture | Passed; hashes and dimensions verified |
| Home startup probes/timers/threads | 0 / 0 / 0 in all five runs |
| `git diff --check` | Passed |
| Hallmark pre-emit and slop review | Passed for the desktop application scope |

## Deferred work

- Phase 6 adopts shared components in Advanced and removes legacy presentation
  only after compatibility coverage proves it unused.
- Phase 7 owns live Fedora KDE, Wayland/X11, compositor scaling, keyboard,
  contrast, and screen-reader validation.
- Phase 8 owns controlled performance gates, coverage and release evidence,
  packaging, the version bump, and publication readiness.

No commit, push, tag, release, or remote mutation is part of this phase.
