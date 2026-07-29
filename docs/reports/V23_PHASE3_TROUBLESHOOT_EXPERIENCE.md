# V23 Phase 3 Canonical Troubleshoot Experience

Date: 2026-07-29  
Active target: `v23.0.0 "Compass"`  
Product metadata: `v22.0.0 "Alignment"`  
Scope: local Phase 3 implementation only

## Outcome

Phase 3 turns the existing `diagnostics` route into the single canonical
Troubleshoot experience. It preserves `diagnostics:watchtower`,
`diagnostics:boot`, the `logs` redirect, all 81 route IDs, and the six
top-level destinations.

The page now presents one bounded journey:

1. choose one of the six closed symptom profiles;
2. review the exact sources, Fedora applicability, and source timeouts;
3. explicitly start the read-only session;
4. review current findings, source readiness, freshness, and technical evidence;
5. review changes labelled **Possibly related**;
6. activate exactly one inert next step for the selected finding; and
7. rerun the compatible profile and review the follow-up comparison.

No page, Home, navigation, search, API, timer, or background process starts a
session implicitly.

## Runtime boundary

`core.troubleshooting.service.TroubleshootingService` is PyQt-free and owns:

- explicit queued-to-running activation;
- exact Traditional/Atomic profile source selection;
- per-source and total budgets;
- cooperative cancellation and source isolation;
- source-owned evidence adaptation and deterministic composition;
- terminal session persistence through the existing schema-v1 XDG store; and
- compatible before/after comparison against the previous retained session.

The default collector reuses existing bounded System Check, observability,
Trusted Change Journal, Action Center, package-health, deployment, application
inventory, NetworkManager, DNS metadata, storage reclaim, boot, failed-service,
and package/deployment-history readers. It retains only structured,
privacy-bounded facts. Connection names, DNS server addresses, raw command
output, command vectors, host identifiers, secrets, personal paths, and
credentials are not stored in troubleshooting sessions.

`core.workers.troubleshooting_worker.TroubleshootingWorker` is the explicit Qt
adapter. The UI constructs it only after direct activation and can request
cooperative cancellation. A cancelled session remains terminal evidence and
does not discard or rewrite the previous completed session.

## Presentation

`ui.troubleshoot_widget.TroubleshootWidget` uses one `PageScaffold`, one
`LocalViewSwitcher`, one `PrimaryButton`, and shared status, progress, card,
notice, action, empty-state, and disclosure components.

- Technical evidence is collapsed by default and keyboard reachable.
- Every result shows Fedora variant, completion time, source state, collection
  time, readiness reason, finding freshness, and evidence quality.
- Partial, stale, unavailable, timed-out, failed, cancelled, empty, and
  completed states remain distinct.
- A partial result is explicitly not an all-clear.
- One selected finding exposes one next step. Action steps emit only the
  existing Action Center action ID plus validated typed parameters. Navigation
  steps emit only an existing route plus inert preselection metadata.
- Manual guidance and no-safe-step findings never expose an executable control.
- Follow-up results keep troubleshooting resolution separate from Action Center
  verification.

Home adds a navigation-only **Troubleshoot a problem** common task. Global
search continues to resolve the unchanged, already discoverable `diagnostics`
route. Neither integration creates a worker or probe.

## Protected contracts

Phase 3 changes no route identity, destination, Action Center schema, CLI,
authenticated API, daemon, D-Bus contract, Support Bundle writer, product
version, package, tag, installation, or remote state. Action Center remains the
only host-mutation authority. The historical occupied `v23.0.0` tag remains
unchanged and blocked pending separate Phase 6 authority.

## Verification scope

Focused tests cover:

- construction with no collection, state read, or write;
- exact profile source selection, progress, terminal persistence,
  cancellation, future-schema preservation, and compatible follow-up;
- one page scaffold, one local switcher, one primary action, six profiles,
  explicit worker creation, application-parameter validation, evidence
  disclosure, inert route preselection, keyboard activation, RTL, and absence
  of page timers;
- 900, 1180, and 1366 DIP geometry at 100, 150, and 200 percent font scale
  across system, light, dark, and high-contrast themes;
- unchanged product-catalog serialization, route identities, global search,
  diagnostics subroutes, Home, and architecture import boundaries.

Full repository verification and project-statistics readback are recorded in
the implementation handoff. Offscreen UI evidence is local presentation
evidence only; it is not physical Fedora, Wayland, Orca/AT-SPI, Traditional,
Atomic, installation, artifact, CI, COPR, GitHub, or public-release proof.
Phase 4 remains not started.
