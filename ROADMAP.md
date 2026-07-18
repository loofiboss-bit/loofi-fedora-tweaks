# Loofi Fedora Tweaks — Roadmap

<!-- markdownlint-configure-file {"MD024": {"siblings_only": true}, "MD060": false} -->

This file is the current and future release-status index. Completed implementation
history lives in [the archived roadmap](docs/archive/ROADMAP_HISTORY_THROUGH_V15.md),
[the changelog](CHANGELOG.md), and [release notes](docs/releases/RELEASE_NOTES.md).

## Release Index

| Version | Codename | Status | Authority |
| --- | --- | --- | --- |
| v15.0.0 | Essentials | DONE | [Architecture](.workflow/specs/arch-v15.0.0.md), [tasks](.workflow/specs/tasks-v15.0.0.md), [release notes](docs/releases/RELEASE-NOTES-v15.0.0.md) |
| v16.0.0 | Clarity | ACTIVE | [Canonical plan](docs/plans/LOOFI_FEDORA_TWEAKS_V16_PLAN.md), [architecture](.workflow/specs/arch-v16.0.0.md), [tasks](.workflow/specs/tasks-v16.0.0.md) |
| v17.0.0 | Unnamed | FUTURE | Reassess physical component packaging only after v16 consolidation evidence |

## [ACTIVE] v16.0.0 "Clarity" — UI/UX Redesign and Consolidation

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
| 1 — Theme engine and tokens | PENDING | Structural QSS plus semantic palettes |
| 2 — Shared components | PENDING | Accessible reusable page and control primitives |
| 3 — Application shell | PENDING | Responsive section navigation and sidebar behavior |
| 4 — Home and System | PENDING | Priority destination redesigns |
| 5 — Remaining Standard | PENDING | Software, Network/Security, Desktop, Settings |
| 6 — Advanced and cleanup | PENDING | Shared-system adoption and legacy presentation removal |
| 7 — UI/accessibility validation | PENDING | Automated and live Fedora KDE matrices |
| 8 — Regression and release | PENDING | Full gates, packaging, version bump, publication |

The complete scope, gates, and acceptance criteria are defined only in
[the canonical v16 plan](docs/plans/LOOFI_FEDORA_TWEAKS_V16_PLAN.md).

## [DONE] v15.0.0 "Essentials" — Product Simplification

v15 shipped six Standard destinations, optional Advanced mode, one canonical
Home, policy-backed global search, true route-time plugin loading, logical
component isolation, and preserved v14 trust contracts. The canonical annotated
tag `v15.0.0` peels to `17aa8aa78cd3ac51d1d63da336ee25d4e5e3b4c1`.

See [v15 release notes](docs/releases/RELEASE-NOTES-v15.0.0.md) and
[v15 release readiness](docs/reports/V15_PHASE10_RELEASE_READINESS.md).

## [FUTURE] v17.0.0 — Post-consolidation Decisions

- Reassess a physical `-extras` package only if v16 reduces shared ownership and
  CLI/API/daemon dependency overlap enough to make upgrades safe.
- Choose codename and scope only after v16 evidence and release retrospection.

## Execution Rules

- At most one release section may be `ACTIVE`.
- The active release must have matching `.workflow/specs` and race-lock state.
- A completed current package version may coexist with one newer active roadmap
  target before the version bump.
- Commit only after the current phase gate is green.
- Do not tag, publish, or modify remote state from an intermediate phase.
