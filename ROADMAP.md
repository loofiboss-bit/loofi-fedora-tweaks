# Loofi Fedora Tweaks — Roadmap

<!-- markdownlint-configure-file {"MD024": {"siblings_only": true}, "MD060": false} -->

This file is the current and future release-status index. Completed implementation
history lives in [the archived roadmap](docs/archive/ROADMAP_HISTORY_THROUGH_V15.md),
[the changelog](CHANGELOG.md), and [release notes](docs/releases/RELEASE_NOTES.md).

## Release Index

| Version | Codename | Status | Authority |
| --- | --- | --- | --- |
| v15.0.0 | Essentials | DONE | [Architecture](.workflow/specs/arch-v15.0.0.md), [tasks](.workflow/specs/tasks-v15.0.0.md), [release notes](docs/releases/RELEASE-NOTES-v15.0.0.md) |
| v16.0.0 | Clarity | DONE | [Canonical plan](docs/plans/LOOFI_FEDORA_TWEAKS_V16_PLAN.md), [architecture](.workflow/specs/arch-v16.0.0.md), [tasks](.workflow/specs/tasks-v16.0.0.md) |
| v17.0.0 | Assurance | ACTIVE | [Canonical plan](docs/plans/LOOFI_FEDORA_TWEAKS_V17_PLAN.md), [architecture](.workflow/specs/arch-v17.0.0.md), [tasks](.workflow/specs/tasks-v17.0.0.md) |

## [DONE] v16.0.0 "Clarity" — UI/UX Redesign and Consolidation

**Objective:** make the PyQt application feel like a focused Fedora-native
control center without changing trusted system-operation behavior.

### Required outcomes

- Replace unreadable application-level secondary tabs with responsive,
  full-label section navigation.
- Keep structural component styling in system, dark, light, and high-contrast
  modes.
- Establish one page scaffold and one shared component language across all six
  Standard destinations before broad Advanced adoption.
- Validate the actual `MainWindow` at supported sizes, font scales, themes, and
  keyboard/accessibility states.
- Preserve every v15 route, alias, lazy-loading, startup, state, Action Center,
  Fedora Traditional/Atomic, CLI, API, daemon, IPC, and plugin contract.

### Phase status

| Phase | Status | Deliverable |
| --- | --- | --- |
| 0 — Baseline and scope lock | DONE | Exact v15 evidence, canonical authority, inventories, screenshot matrix |
| 1 — Theme engine and tokens | DONE | [Structural QSS plus semantic palettes](docs/reports/V16_PHASE1_THEME_ENGINE.md) |
| 2 — Shared components | DONE | [Accessible reusable page and control primitives](docs/reports/V16_PHASE2_SHARED_COMPONENTS.md) |
| 3 — Application shell | DONE | [Responsive section navigation and sidebar behavior](docs/reports/V16_PHASE3_APPLICATION_SHELL.md) |
| 4 — Home and System | DONE | [Priority destination redesigns](docs/reports/V16_PHASE4_HOME_SYSTEM.md) |
| 5 — Remaining Standard | DONE | [Software, Network/Security, Desktop, and Settings](docs/reports/V16_PHASE5_STANDARD_DESTINATIONS.md) |
| 6 — Advanced and cleanup | DONE | [Shared-system adoption and legacy presentation removal](docs/reports/V16_PHASE6_ADVANCED_CLEANUP.md) |
| 7 — UI/accessibility validation | DONE | [Real-shell responsive, theme, input, and accessibility matrices](docs/reports/V16_PHASE7_UI_ACCESSIBILITY.md) |
| 8 — Regression and release | DONE | [Full gates, packaging, version bump, and publication readiness](docs/reports/V16_PHASE8_RELEASE_READINESS.md) |

The complete scope, gates, and acceptance criteria are defined only in
[the canonical v16 plan](docs/plans/LOOFI_FEDORA_TWEAKS_V16_PLAN.md).

The canonical annotated tag `v16.0.0` peels to release commit
`56007bf7e5c046f189d2e2284740320ca3e1ebad`. Auto Release Pipeline run
`29641341177`, COPR build `10740581`, the public Fedora 44 package install,
release asset evidence, and wiki readback all passed. The historical Horizon
tag object remains available as `legacy-v16.0.0-horizon`.

## [DONE] v15.0.0 "Essentials" — Product Simplification

v15 shipped six Standard destinations, optional Advanced mode, one canonical
Home, policy-backed global search, true route-time plugin loading, logical
component isolation, and preserved v14 trust contracts. The canonical annotated
tag `v15.0.0` peels to `17aa8aa78cd3ac51d1d63da336ee25d4e5e3b4c1`.

See [v15 release notes](docs/releases/RELEASE-NOTES-v15.0.0.md) and
[v15 release readiness](docs/reports/V15_PHASE10_RELEASE_READINESS.md).

## [ACTIVE] v17.0.0 "Assurance" — Verified Core Workflows

- Converge the five canonical workflows on preview, explicit confirmation,
  audit, and outcome verification through Action Center.
- Add durable reboot-aware verification for Atomic Fedora and firmware work.
- Enforce the published read-only Web API boundary.
- Keep physical specialist packaging out of scope because ownership and runtime
  overlap remain too high for safe upgrades.

The sole scope authority is the
[canonical v17 plan](docs/plans/LOOFI_FEDORA_TWEAKS_V17_PLAN.md).

## Execution Rules

- At most one release section may be `ACTIVE`.
- The active release must have matching `.workflow/specs` and race-lock state.
- A completed current package version may coexist with one newer active roadmap
  target before the version bump.
- Commit only after the current phase gate is green.
- Do not tag, publish, or modify remote state from an intermediate phase.
