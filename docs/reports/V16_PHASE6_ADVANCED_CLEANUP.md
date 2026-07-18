<!-- Hallmark · pre-emit critique: P5 H5 E5 S5 R5 V4 -->

# v16.0.0 "Clarity" Phase 6 Advanced Adoption and Cleanup

**Status:** implemented and verified locally

**Authority:** [`docs/plans/LOOFI_FEDORA_TWEAKS_V16_PLAN.md`](../plans/LOOFI_FEDORA_TWEAKS_V16_PLAN.md)

**Working branch:** `v16-clarity`

## Outcome

Phase 6 brings every Advanced page onto the shell and component contracts used
by Standard destinations. All 12 Advanced modules use `PageScaffold`, shell
sections now select route-owned `QStackedWidget` pages, repeated page headers
and root margins are removed, and existing operations remain unchanged.

The application remains `15.0.0 "Essentials"`. All 80 stable routes, aliases,
lazy ownership, plugin behavior, CLI, API, daemon, IPC, privilege, and
Traditional/Atomic contracts are preserved.

## Advanced navigation contract

The Advanced destination exposes 33 routes through 26 explicit shell sections.
Seven formerly tab-driven modules now provide route activation through a stack:

- Development
- Community
- Loofi Link
- AI Lab
- Agents
- Automation
- Virtualization

Performance, Gaming, Profiles, Extensions, and Teleport use the same scaffold
and zero-margin root contract as the stacked modules. The shell remains the
sole owner of application navigation.

Community Presets retains one local three-view tab group because My Presets,
Community, and Backup & Sync are same-context preset views. No other Advanced
module keeps an application-navigation `QTabWidget`, and the retained group
remains below the four-view cap.

## Legacy presentation cleanup

- Removed the superseded `modern.qss`, `light.qss`, and `highcontrast.qss`
  stylesheets after runtime, packaging, and compatibility checks proved them
  unused.
- Kept `base.qss` as the single structural stylesheet, rendered with system,
  dark, light, or high-contrast semantic palettes.
- Removed the dead `QLabel#sectionTitle` selector.
- Migrated screenshot helpers to `ThemeManager` so they exercise the active
  theme path.
- Removed stale version-number comments from touched active Advanced code.
- Updated active architecture, wiki, and screenshot documentation that still
  described the removed theme files.

The four mypy findings recorded by the original plan were already resolved on
the authoritative Phase 6 starting checkout. Phase 6 introduced no replacement
workaround; both the initial and final type checks are clean.

## Compatibility and behavior

The work changes presentation ownership only. It does not change command
builders, service calls, worker lifecycle, confirmations, mutation policy,
route IDs, plugin contracts, or user data. Existing specialist regression tests
cover Development, Community, Loofi Link, AI Lab, Agents, Automation,
Virtualization, Performance, Gaming, Profiles, Extensions, and Teleport.

Output and diagnostics remain available through existing shared disclosure
components. No new color, typography, animation, feature, operation, or
destination-specific styling system was added.

## Deterministic Phase 6 gate

`scripts/validate_v16_phase6_ui.py` validates the Advanced presentation without
PyQt, host probes, or mutations. Its passing JSON result records:

| Metric | Result |
| --- | ---: |
| Stable routes | 80 |
| Advanced routes | 33 |
| Advanced shell sections | 26 |
| Scaffolded Advanced modules | 12 |
| Application-navigation `QTabWidget` instances | 0 |
| Retained local `QTabWidget` instances | 1 |
| Retained local views | 3 |
| Host probes | 0 |
| Mutations | 0 |

## Verification

| Gate | Result |
| --- | --- |
| `just verify` | Passed |
| Full test suite | 7,716 passed, 40 skipped, 848 subtests |
| Coverage | 86.13% (85% required) |
| `just lint` | Passed |
| `just typecheck` | Passed; no mypy errors |
| Phase 6 navigation/theme tests | 62 passed |
| Advanced regression tests | 357 passed |
| Development regression tests | 112 passed |
| Community regression tests | 107 passed |
| Release-document validation | Passed |
| Agent-adapter drift check | Passed |
| Fedora review check | Passed |
| Stabilization check | Passed |
| `git diff --check` | Passed |
| Hallmark pre-emit and slop review | Passed for the desktop application scope |

## Deferred work

- Phase 7 owns the real `MainWindow` responsive, theme, keyboard,
  accessibility, contrast, Wayland/X11, and compositor-scaling matrices.
- Phase 8 owns controlled startup/resource gates, packaging, release evidence,
  the v16 version bump, and publication readiness.

No commit, push, tag, release, or remote mutation is part of this phase.
