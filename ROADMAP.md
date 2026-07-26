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
| v17.0.0 | Assurance | DONE | [Canonical plan](docs/plans/LOOFI_FEDORA_TWEAKS_V17_PLAN.md), [architecture](.workflow/specs/arch-v17.0.0.md), [tasks](.workflow/specs/tasks-v17.0.0.md) |
| v18.0.0 | Haven | DONE | [Canonical plan](docs/plans/LOOFI_FEDORA_TWEAKS_V18_PLAN.md), [architecture](.workflow/specs/arch-v18.0.0.md), [tasks](.workflow/specs/tasks-v18.0.0.md) |
| v19.0.0 | Steward | DONE | [Canonical plan](docs/plans/LOOFI_FEDORA_TWEAKS_V19_PLAN.md), [architecture](.workflow/specs/arch-v19.0.0.md), [tasks](.workflow/specs/tasks-v19.0.0.md) |
| v20.0.0 | Continuity | PUBLICATION BLOCKED | [Architecture](.workflow/specs/arch-v20.0.0.md), [tasks](.workflow/specs/tasks-v20.0.0.md), [release notes](docs/releases/RELEASE-NOTES-v20.0.0.md) |
| v21.0.0 | Resolve | ACTIVE | [Canonical plan](docs/plans/LOOFI_FEDORA_TWEAKS_V21_PLAN.md), [architecture](.workflow/specs/arch-v21.0.0.md), [tasks](.workflow/specs/tasks-v21.0.0.md) |

## [ACTIVE] v21.0.0 "Resolve" — Coherent Verified Work

**Objective:** make the existing safe Fedora control center understandable as
one See → Understand → Review → Apply → Verify journey and guarantee
deterministic application teardown.

### Required outcomes

- One truthful Home summary and one primary next step without duplicated work.
- Separate route navigation from small same-context local view switching.
- Truthful Action Center review language for application operations.
- State-driven System Check and Activity & Recovery presentation.
- Grouped, searchable Specialist Tools and consistent Settings feedback.
- No leaked EventBus, scheduler, QThread, timer, or plugin-worker resources.
- Preserve every current route, persisted-data, Action Center, System Check,
  CLI/API/daemon, Traditional/Atomic, and lazy-startup contract.

### Phase status

| Phase | Status | Deliverable |
| --- | --- | --- |
| 0 — Authority, baseline, and scope lock | DONE | [Exact v20 evidence and V21 authority](docs/reports/V21_PHASE0_BASELINE.md) |
| 1 — Runtime lifecycle and shell | DONE | [ApplicationRuntime, exact cleanup, shell extraction, and local view switching](docs/reports/V21_PHASE1_RUNTIME_SHELL.md) |
| 2 — Guided core journey | DONE | [GuidedTask, Home, Apps, System Check, and Activity & Recovery](docs/reports/V21_PHASE2_GUIDED_CORE.md) |
| 3 — Supporting surfaces and accessibility | DONE | [Grouped Specialist Tools, Settings feedback, responsive, AT-SPI, Wayland, and xcb validation](docs/reports/V21_PHASE3_SUPPORTING_SURFACES.md) |
| 4 — Platform and release readiness | NOT STARTED | Lifecycle, performance, Fedora 44, packaging, and local release gates |

The sole scope authority is the
[canonical v21 plan](docs/plans/LOOFI_FEDORA_TWEAKS_V21_PLAN.md). Product
metadata remains v20.0.0 until all local Resolve gates pass. No tag mutation,
commit, push, package publication, or remote release action occurs without
separate authorization.

## [PUBLICATION BLOCKED] v20.0.0 "Continuity" — Trusted Activity and Recovery

**Objective:** compose trusted local change history into one privacy-bounded
review surface and offer only state-verifiable recovery through Action Center.

### Required outcomes

- No command-bearing history or second durable journal database.
- Exact DNF5 offline and rpm-ostree rollback recovery with changed-boot
  verification and no automatic reboot.
- Lazy Activity & Recovery UI, stable CLI, authenticated read-only API, and
  bounded support evidence.
- All legacy presentation mutations either use a named Action Center definition
  or fail closed.
- Specialist Tools remain discoverable without a global mode switch; safety
  remains action-specific.

### Phase status

| Phase | Status | Deliverable |
| --- | --- | --- |
| 0 — Authority and scope lock | DONE | v19 baseline, current checkout, and Continuity contract |
| 1 — Journal and migration | DONE | Inert event model, source adapters, cache, and history schema v2 |
| 2 — Safe recovery | DONE | DNF5 offline undo and exact rpm-ostree rollback |
| 3 — Interfaces and product integration | DONE | UI, CLI, API, catalog, support bundle, unified navigation |
| 4 — Mutation closure | DONE | Named legacy plans and inert direct helpers |
| 5 — Release preparation | PUBLICATION BLOCKED | GitHub published; COPR build `10773551` failed in Pulp and Fedora 44 public metadata remains on v19 |

The exact implementation and acceptance authority is
[the v20 architecture](.workflow/specs/arch-v20.0.0.md) and
[task contract](.workflow/specs/tasks-v20.0.0.md). C11-C13 remain open. The
user explicitly allowed V21 Phase 0 to proceed without treating V20 as
complete.

## [DONE] v19.0.0 "Steward" — Guided System Checks

**Objective:** connect the existing read-only health, Home, diagnostics, and
Action Center foundations into one explicit System Check and verified-resolution
journey without weakening the v18 trust boundary.

### Required outcomes

- Home starts a bounded read-only check only after explicit user action.
- One canonical System Check presentation composes the existing snapshot and
  metric stores without creating a third health database.
- Findings carry privacy-safe evidence and may recommend one existing audited
  Action Center action ID, a navigation-only route, or honest manual guidance.
- Stable routes, aliases, settings, favorites, snapshots, metrics, plans, runs,
  Traditional/Atomic behavior, and startup safety remain compatible.

### Phase status

| Phase | Status | Deliverable |
| --- | --- | --- |
| 0 — Authority, baseline, and scope lock | DONE | [Exact v18 inventories and v19 authority](docs/reports/V19_PHASE0_BASELINE.md) |
| 1 — Canonical System Check domain | DONE | [PyQt-free contracts, bounded collectors, and v18-compatible storage](docs/reports/V19_PHASE1_SYSTEM_CHECK_DOMAIN.md) |
| 2 — Explicit Home check workflow | DONE | [Explicit asynchronous Check now flow and startup evidence](docs/reports/V19_PHASE2_EXPLICIT_HOME_CHECK.md) |
| 3 — Canonical page and compatibility migration | DONE | [One read-only page with preserved routes, snapshots, metrics, and CLI aliases](docs/reports/V19_PHASE3_CANONICAL_SYSTEM_CHECK.md) |
| 4 — Finding-to-Action Center handoff | DONE | [Validated finding handoff and Action Center schema-v4 context](docs/reports/V19_PHASE4_ACTION_HANDOFF.md) |
| 5 — Verified resolution and support evidence | DONE | [Separate verification/resolution facts, bounded support evidence, and read-only API](docs/reports/V19_PHASE5_VERIFIED_RESOLUTION.md) |
| 6 — Accessibility, platform certification, and release | LOCAL READY | [Platform evidence](docs/reports/V19_PHASE6_PLATFORM_CERTIFICATION.md) and [local release readiness](docs/reports/V19_PHASE6_RELEASE_READINESS.md) |

The historical scope authority is the
[canonical v19 plan](docs/plans/LOOFI_FEDORA_TWEAKS_V19_PLAN.md). No product
tag or publication occurs without separate authorization. The synchronized
v19.0.0 metadata was applied only after the local Phase 6 gates passed. The
canonical v19 release, package, and documentation were subsequently published
and independently read back.

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

## [DONE] v17.0.0 "Assurance" — Verified Core Workflows

- Converge the five canonical workflows on preview, explicit confirmation,
  audit, and outcome verification through Action Center.
- Add durable reboot-aware verification for Atomic Fedora and firmware work.
- Enforce the published read-only Web API boundary.
- Keep physical specialist packaging out of scope because ownership and runtime
  overlap remain too high for safe upgrades.

The sole scope authority is the
[canonical v17 plan](docs/plans/LOOFI_FEDORA_TWEAKS_V17_PLAN.md).

The canonical annotated tag `v17.0.0` peels to release commit
`758e7528558daa200989b2d16a333039c020a4dd`. Auto Release Pipeline run
`29716217083`, COPR build `10748977`, the public Fedora 44 package install,
release asset evidence, and wiki readback all passed. The historical Atlas tag
remains available as `legacy-v17.0.0-atlas`.

## [DONE] v18.0.0 "Haven" — Complete Trust Boundary

- Converge every supported host mutation on Action Center plan, confirmation,
  execution, and independent verification.
- Generate product navigation/plugin views from one data-only catalog.
- Retire public Marketplace distribution and executable third-party plugins
  while preserving built-in lazy loading and compatibility routes.
- Move credentials to Secret Service, lock the read-only Web API to loopback,
  and simplify the primary review-run-verify user journey.
- Reduce architectural hotspots and make statistics, security documentation,
  and release gates reflect the actual repository.

The sole scope authority is the
[canonical v18 plan](docs/plans/LOOFI_FEDORA_TWEAKS_V18_PLAN.md). Phase 0
baseline evidence is recorded in
[the scope-lock report](docs/reports/V18_PHASE0_BASELINE.md).

The canonical annotated tag `v18.0.0` peels to release commit
`6cfe11babd502d32bb57f333f1f505615a4f8864`. Auto Release Pipeline run
`29943164217`, CodeQL run `29943164084`, CI run `29943164246`, COPR build
`10764217`, public release artifacts, checksum/SBOM/provenance verification,
the clean Fedora 44 repository install, and wiki readback all passed.
Historical Sentinel remains available as `legacy-v18.0.0-sentinel`.

## Execution Rules

- At most one release section may be `ACTIVE`.
- The active release must have matching `.workflow/specs` and race-lock state.
- A completed current package version may coexist with one newer active roadmap
  target before the version bump.
- Commit only after the current phase gate is green.
- Do not tag, publish, or modify remote state from an intermediate phase.
