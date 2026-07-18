<!-- Hallmark · pre-emit critique: P5 H5 E4 S5 R5 V4 -->

# v16.0.0 "Clarity" Phase 4 Home and System

**Status:** implemented and verified locally

**Authority:** [`docs/plans/LOOFI_FEDORA_TWEAKS_V16_PLAN.md`](../plans/LOOFI_FEDORA_TWEAKS_V16_PLAN.md)

**Working branch:** `v16-clarity`

## Outcome

Phase 4 rebuilds Home around four saved-evidence status signals, one dominant
recommendation, at most three attention items, four whole-card task shortcuts,
and recent activity behind a disclosure. Home does not add startup probes,
polling, execution controls, or invented good states.

System Information now uses three responsive property groups and exposes its
existing format and Export Report controls in the shell header. Refresh and
Copy Summary are removed from the visible action set; the underlying report
formats and export behavior are unchanged.

Performance, Processes, Hardware, Storage, Health History, Troubleshooting,
Boot, and Recovery Points now use the shared page scaffold. Their outer
application-navigation tabs and repeated page titles are removed. Diagnostics
keeps its one content-level tab set for Services, Boot Analysis, and Journal.

The application remains `15.0.0 "Essentials"`. No route, alias, redirect,
Action Center, state, system-operation, Traditional/Atomic, CLI, API, daemon,
IPC, or version contract changed.

## Home contract

- Health, updates, storage, and recovery states are derived only from sources
  already read by `HomeService`.
- Missing or stale evidence stays unknown; Home never converts absence into a
  healthy claim.
- Exactly one primary recommendation can be visible.
- Attention is bounded to three items and each item has one route action.
- Common tasks are icon-backed `ClickableCard` controls without nested buttons.
- Recent activity stays collapsed by default.

## System contract

- System Information remains probe-free during construction and loads once on
  explicit route activation.
- A failed property probe marks only that row unavailable; other copy actions
  remain usable.
- Property groups reflow at explicit one-, two-, and three-column breakpoints.
- Export Format and Export Report move with the active route and return to the
  page owner when the route changes.
- System peer routes activate through stable route IDs in `QStackedWidget`
  containers rather than nested application navigation.

## Visual evidence

The reproducible offscreen capture uses the real `MainWindow`, Standard mode,
temporary HOME/XDG state, deterministic display data, disabled background
services, and rejected mutating subprocesses.

| Viewport | Home | System Information |
| --- | --- | --- |
| 860 × 720 | [`home__860x720.png`](../images/v16/phase4/home__860x720.png) | [`system-info__860x720.png`](../images/v16/phase4/system-info__860x720.png) |
| 1918 × 1018 | [`home__1918x1018.png`](../images/v16/phase4/home__1918x1018.png) | [`system-info__1918x1018.png`](../images/v16/phase4/system-info__1918x1018.png) |

Hashes, dimensions, capture policy, and the reproduction command are recorded
in [`V16_PHASE4_SCREENSHOTS.json`](V16_PHASE4_SCREENSHOTS.json).

The supplied v15 defects are not reproduced: Home has one clear primary next
step and no nested full-width action bars; System labels remain readable; and
System Information uses three compact groups at the wide reference size.

## Startup safety evidence

The clean offscreen benchmark still realizes only `atlas_dashboard`, with zero
startup subprocess probes, zero active timers, and zero running `QThread`
instances in every measured run. Under the current `powersave` governor and a
concurrently loaded workstation, both the unchanged Phase 3 checkout and the
Phase 4 tree measured above the historical 182.309 ms Phase 8 release limit.
The final sequential samples were 202.342 ms for the unchanged Phase 3 checkout
and 277.371 ms for the Phase 4 tree while unrelated workstation load changed
between runs, so they are not accepted as a comparative performance result.
The binding timing gate remains Phase 8 work and must be repeated in a
controlled run.

Raw measurements are retained in
[`V16_PHASE4_STARTUP.json`](V16_PHASE4_STARTUP.json) and
[`V16_PHASE4_STARTUP_HEAD_BASELINE.json`](V16_PHASE4_STARTUP_HEAD_BASELINE.json).

## Verification

| Gate | Result |
| --- | --- |
| `just verify` | Passed |
| Full test suite | 7,699 passed, 40 skipped, 820 subtests |
| Coverage | 86.18% (85% required) |
| Focused Phase 4 Home/System tests | Passed |
| System route/scaffold tests | Passed |
| Flake8 | Passed |
| Mypy | Passed |
| Four-frame screenshot capture | Passed |
| Home startup probes/timers/threads | 0 / 0 / 0 |
| Hallmark pre-emit and slop review | Passed for the desktop application scope |

## Deferred work

- Phase 5 redesigns the remaining Standard destinations.
- Phase 6 migrates Advanced surfaces and removes proven dead legacy styling.
- Phase 7 owns live Fedora KDE, Wayland/X11, compositor scaling, keyboard,
  contrast, and screen-reader validation.
- Phase 8 owns controlled performance gates, coverage/release evidence,
  packaging, the version bump, and publication readiness.

No commit, push, tag, release, or remote mutation is part of this phase.
