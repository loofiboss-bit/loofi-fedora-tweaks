# Loofi Fedora Tweaks v21.0.0 "Resolve"

## Canonical implementation plan

**Baseline commit:** `841218ef4dbfa6368136bd3d8cbc1c394ec81258`  
**Current product version:** v20.0.0 "Continuity"  
**Active target:** v21.0.0 "Resolve"  
**Primary theme:** See → Understand → Review → Apply → Verify  
**Plan date:** 2026-07-26

## Outcome

Resolve turns the existing safe Fedora control center into one coherent task
journey. It does not add another feature family or execution authority. It
connects current status, explanation, Action Center review, verified execution,
and follow-up evidence through clearer presentation and deterministic runtime
cleanup.

User-visible success means:

- Home presents one useful next step without duplicating the same warning.
- Route and local-view navigation remain visually and semantically distinct.
- Application operations say `Review install` or `Review removal` before the
  Action Center handoff; they never imply immediate execution.
- Activity & Recovery reveals controls, data, and details only when the current
  state supports them.
- Specialist Tools remain fully discoverable without one unstructured list.
- The compact shell has no horizontal scrollbar and exposes understandable
  search and history controls.
- Repeated application startup and teardown leaves no EventBus, scheduler,
  QThread, timer, or plugin-worker resources behind.

## Protected contracts

- Preserve all 81 stable route IDs, aliases, favorites, direct links, saved
  navigation, settings readers, and built-in lazy loading.
- Preserve Action Center schema v4, one action per expiring plan, fresh
  preflight, explicit confirmation, separate verification, and no automatic
  reboot, retry, rollback, resume, or parameter broadening.
- Preserve System Check results and histories, Trusted Change Journal records,
  CLI commands and JSON envelopes, daemon/D-Bus contracts, the authenticated
  loopback-only read-only API, support bundles, and unknown-future-schema
  read-only behavior.
- Preserve Traditional and Atomic Fedora policy branches. Fedora 44 remains the
  supported target; Fedora 45 remains preview-only until a later certification
  gate explicitly promotes it.
- Preserve the cold-start contract: one realized Home provider and zero
  subprocess probes, active hidden timers, or running QThreads.
- Preserve the user's existing workflow edits. Resolve does not take ownership
  of unrelated GitHub Actions retention work.

## Scope

### Included

- Application-owned runtime teardown and exact EventBus subscription cleanup.
- Focused extraction of shell navigation, header, and lifecycle coordination
  from `MainWindow`.
- One `LocalViewSwitcher` for two to five peer views inside a route.
- Home `GuidedTask` presentation over existing route, plan, run, and activity
  identifiers without new persistence.
- Home, Software Apps, System Check, Activity & Recovery, Settings, Specialist
  Tools, responsive-shell, accessibility, and copy improvements.
- Current-shell performance, geometry, state, Wayland/X11, Traditional/Atomic,
  packaging, and release-readiness evidence.

### Explicitly excluded

- New AI, agent, remote-mutation, database, daemon authority, background probe,
  automatic remediation, feature family, UI toolkit, or runtime dependency.
- Changes to public CLI/API wire contracts or Action Center execution policy.
- Physical specialist-package splitting.
- Fedora 45 mutation enablement before post-beta certification.
- Commit, push, canonical tag replacement, package publication, or public
  release without separate authorization.

## Phases

### Phase 0 — Authority, baseline, and scope lock

- Record exact checkout, dirty paths, public V20 state, repository inventory,
  architecture hotspots, route/action counts, performance, System Check, UI,
  geometry-test, and platform evidence.
- Mark V20 as publication-blocked and V21 as the sole active development target
  after the user's explicit override of the original V20 prerequisite.
- Archive historical v21 release notes and record both occupied tag lineages;
  do not mutate tags or remote state.
- Create the v21 plan, architecture, tasks, report, and race lock.
- Make no runtime product, route, state, UI, or execution change.

### Phase 1 — Runtime lifecycle and shell

- Add a PyQt-free `ApplicationRuntime` resource registry and connect
  `QApplication.aboutToQuit` to one idempotent bounded shutdown.
- Make EventBus stop accepting publishes, retain/cancel tracked futures, clear
  subscriptions, and support deterministic test reinitialization.
- Store exact AgentScheduler callbacks and unsubscribe them during unregister
  and shutdown.
- Extract focused shell/header/navigation responsibilities from `MainWindow`
  without changing route behavior.
- Add `LocalViewSwitcher`; reserve `SectionNavigator` for route-level
  navigation.
- Remove internal route IDs from visible labels and eliminate compact-shell
  horizontal scrolling.

### Phase 2 — Guided core journey

- Add immutable, PyQt-free `GuidedTask` presentation composed only from current
  route, Action Center plan/run, reboot, System Check, and activity identifiers.
- Bound Home to one status summary, one primary next step, three attention
  items, four common tasks, active work, and latest activity without collection
  on construction.
- Add explicit application source/installed badges and source/status filters.
  Rename plan handoffs to `Review install` and `Review removal`.
- Apply `LocalViewSwitcher` to System Check Overview, Findings, and History.
- Make Activity & Recovery explicitly state-driven for initial, loading, empty,
  partial, truncated, loaded, selected, recoverable, manual-only, and error
  states.

### Phase 3 — Supporting surfaces and accessibility

- Group and locally filter Specialist Tools while preserving every route and
  direct link.
- Present Settings as consistent rows with dependency, saved, and error
  feedback.
- Validate available-width behavior at 860×560, 900×720, 1366×768, and
  1920×1080 with 100, 125, 150, and 200 percent text scaling.
- Validate keyboard navigation, focus, accessible names, contrast,
  high-contrast, RTL, tooltips, Wayland, and X11. Color is never the sole state
  signal.

### Phase 4 — Platform and quality gates

- Keep Fedora 44 Traditional and Kinoite/Atomic as the supported certification
  targets.
- Keep Fedora 45 preview/read-only until a separate post-beta gate.
- Require meaningful Home median no slower than Phase 0 × 1.10, RSS no greater
  than Phase 0 × 1.10, one realized plugin, and no cold-start probe, timer, or
  worker thread.
- Pass the current-shell screenshot, state, lifecycle, accessibility, package,
  and compatibility matrices.

### Phase 5 — Release readiness

- Synchronize version metadata only after all local gates pass.
- Build RPM, optional API/daemon RPMs, Flatpak, and sdist from the exact
  candidate archive; generate checksums, CycloneDX SBOM, and in-toto
  provenance.
- Preserve historical tag lineages before any canonical v21 tag replacement.
- Treat publication and independent public readback as separately authorized
  work.

## Release gates

- `just verify`, release-document validation, packaging validation, adapter
  drift, security scans, and at least 86 percent coverage pass.
- All 81 routes resolve through navigation, search, favorites, aliases, and
  direct links without exposing internal IDs.
- Repeated open/close/reopen cycles leave zero owned asynchronous resources and
  the seven current geometry tests run without the EventBus skip.
- Software application controls create exactly one review request and never
  execute a system command.
- Home and Activity state matrices cover every defined empty, partial, stale,
  running, reboot, error, and recovery state.
- Fedora 44 Traditional and Atomic package/readback evidence is current.
- No release is called complete from local evidence alone.
