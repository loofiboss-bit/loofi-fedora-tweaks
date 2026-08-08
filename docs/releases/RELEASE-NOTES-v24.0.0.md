# Release Notes v24.0.0 "Flow"

Released: 2026-08-08

v24.0.0 makes the existing product feel like one coherent Fedora desktop
application through shared task hierarchy, semantic actions, explicit states,
and consistent feedback while preserving its routes and execution authority.

## Highlights

- Home is the task-oriented control point: saved system status, one
  deterministic next action, common tasks, outstanding review work, and
  integrated resumable onboarding.
- Applications distinguishes native Discover from Loofi's curated actions and
  uses one source-aware, status-aware review action per application row.
- Updates distinguishes check, availability, review, running, success,
  failure, cancellation, and reboot expectations for Traditional and Atomic
  Fedora.
- Troubleshooting presents Problem → Checks → Results, collects only after an
  explicit start, and keeps technical detail progressive.
- Action Center opens in its Review queue, keeps the Action catalog separate
  and inert, and presents risk, affected scope, requirements, validation, and
  rollback beside the selected item before its one lifecycle action.
- Network, System Information, and Settings use explicit loading, partial,
  changed, saved, error, dependency, and restart-required feedback.

## Safety and compatibility

- The six standard destinations, stable route IDs, all supported features,
  lazy loading, validation, audit logging, public interfaces, and persisted
  user state are preserved.
- Action Center remains the only GUI authority that can prepare and run a
  validated plan. Browsing, selection, search, onboarding, and review do not
  execute or mutate the host.
- Traditional Fedora and Atomic Fedora remain explicit, separate paths.
- No QML rewrite, marketplace, provider layer, runtime dependency, cloud
  requirement, unattended repair, or hidden background mutation was added.

## Qualification boundaries

- The complete local verification gate passes with the enforced 86% coverage
  floor, lint, mypy, architecture, packaging, documentation, and adapter-drift
  checks.
- The five reference screens were captured from the real PyQt application in
  an isolated offscreen profile at 100% and 140% without visible clipping,
  overlap, mnemonic artifacts, or contradictory lifecycle state.
- Deterministic scale contracts cover 100%, 125%, 140%, 150%, and 200%.
- Fresh Atomic, physical Fedora KDE Wayland interaction, manual keyboard
  journeys, and audible Orca output remain unverified and are not inferred from
  offscreen evidence.

The canonical exact-tag workflow publishes release assets, checksums, SBOM,
provenance, attestations, and Fedora packages. See `CHANGELOG.md` and
`docs/reports/V24_RELEASE_QUALIFICATION.md` for the complete local record.
