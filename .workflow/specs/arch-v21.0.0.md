# Architecture — v21.0.0 "Resolve"

## Goal

Make the existing verified Fedora maintenance system understandable as one
See → Understand → Review → Apply → Verify journey, while closing application
lifecycle leaks and preserving every current execution and compatibility
boundary.

## Decisions

- `ApplicationRuntime` is the process-owned registry for GUI resources that
  require teardown. It coordinates existing Pulse, timers, plugin cleanup,
  AgentScheduler, and EventBus; it does not become a feature service.
- EventBus publishes asynchronously only while running. Shutdown stops new
  submissions, snapshots and clears subscriptions, cancels pending futures,
  and completes bounded cleanup. Reinitialization is explicit and test-only.
- AgentScheduler stores the exact `(topic, callback, subscriber_id)` triples it
  subscribes so unregister and shutdown remove real subscriptions.
- `SectionNavigator` remains route-level navigation. `LocalViewSwitcher` owns
  two to five peer views inside one route and never creates a second route
  namespace.
- `GuidedTask` is immutable and PyQt-free. It may reference existing route,
  plan, run, activity, System Check, and reboot identifiers but owns no command,
  callback, persistence, policy, confirmation, or execution behavior.
- Existing Home, System Check, Action Center, and Trusted Change Journal stores
  remain authoritative. Resolve adds no database or migration.
- Specialist grouping and filtering are presentation projections over the
  existing catalog; every route remains policy-resolved and directly
  addressable.

## Protected behavior

- Preserve all 81 routes, aliases, favorites, settings, direct links, lazy
  plugin loading, and one-provider startup.
- Preserve Action Center schema v4 and its plan, confirmation, execution,
  verification, reboot, lease, and fail-closed policies.
- Preserve System Check and Trusted Change Journal schemas, CLI/API/daemon
  interfaces, support evidence, Traditional/Atomic behavior, and read-only
  future-schema handling.
- Keep the Web API loopback-only and non-mutating.
- Keep Fedora 44 supported and Fedora 45 preview-only during implementation.

## Presentation contracts

- Home renders one truthful summary and one primary task. Secondary attention
  and common-task collections remain bounded at three and four.
- Visible labels come from catalog/destination presentation metadata, never
  internal route IDs.
- Software application host changes are always labelled as review handoffs.
- Activity & Recovery renders data and details progressively from an explicit
  presentation state.
- At supported minimum geometry, shell navigation and content never require a
  horizontal scrollbar.
- Status text, iconography, accessible names, and focus state remain usable
  without relying on color.

## Phase gates

- Phase 0 changes authority, evidence, documentation, validator coverage, and
  race-lock state only. It changes no runtime product behavior.
- Each later phase must pass focused tests plus architecture, product,
  stabilization, release-document, route, startup, and coverage gates before
  the next phase starts.
- Product version remains 20.0.0 during implementation. Version bump, tag
  mutation, commit, push, and publication are release-only work.
