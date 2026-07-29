# Architecture — v23.0.0 "Compass"

## Authority and current state

Compass is the active implementation target while the installed and public
product remains v22.0.0 "Alignment". The canonical authority is:

- `docs/plans/LOOFI_FEDORA_TWEAKS_V23_PLAN.md`;
- this architecture contract;
- `.workflow/specs/tasks-v23.0.0.md`;
- `.workflow/specs/.race-lock.json`; and
- `docs/reports/V23_PHASE0_BASELINE.md`.

Phases 0 and 1 established authority plus the inert `core.troubleshooting`
domain and one registered, explicit session history store. Phase 2 adds pure
read-only evidence adapters, composition, conservative correlation, and
compatible follow-up comparison. It does not change a route, start collection,
mutate the host, introduce another database, or change product metadata.

## Canonical route decision

The existing `diagnostics` route is the future canonical Troubleshoot surface.
It already belongs to the System destination, is discoverable in the
`troubleshooting` section, and resolves to the built-in `diagnostics` plugin.

- `diagnostics:watchtower` remains a stable same-plugin route.
- `logs` remains a compatibility redirect to `diagnostics:watchtower`.
- `diagnostics:boot` remains the advanced Boot view.
- `health` and `maintenance:health-timeline` remain the canonical System Check
  current and history routes.
- `activity`, `atlas_dashboard`, and `maintenance:action-center` retain their
  existing ownership.

Compass must not add a route, top-level destination, second Troubleshoot page,
or parallel history surface.

## Troubleshooting boundary

`core/troubleshooting/` owns immutable, PyQt-free session, profile,
source-result, finding, next-step, and comparison contracts. Phase 2 composes
source-owned evidence without becoming a new collector or execution authority.

The six closed profiles are `system_slow`, `updates_failed`,
`application_failed`, `network_problem`, `storage_pressure`, and
`boot_or_deployment`. A profile is partial or unavailable when its required
evidence cannot be collected safely. No profile may contain a command vector,
callback, renderer, credential, token, or raw process output.

The profile catalog owns exact Traditional/Atomic source and total budgets.
`application_failed` is reduced because no safe application-journal collector
exists; `network_problem` is reduced because scans remain excluded. The domain
exposes pure queued/running/terminal transitions and a cooperative cancellation
signal, but it starts no worker, timer, thread, or probe.

The optional `loofi.troubleshooting-sessions` schema-v1 store retains at most 20
explicit terminal sessions through existing atomic XDG state infrastructure.
Future schemas remain read-only and are never overwritten. UI, explicit
collection wiring, CLI/API, and support export remain later phases.

## Source ownership

- System Check owns its schema-v1 result and comparison models, five fixed
  collectors, per-source timeouts, cancellation, and health-snapshot
  persistence.
- Trusted Change Journal owns bounded read-only source adapters and
  source-specific events. Correlation remains labelled **Possibly related**.
- Observability owns schema-v1 health snapshots and the existing metric
  timeline. Troubleshooting does not create another database.
- Action Center owns schema-v4 plans and runs, the one-action-per-plan rule,
  preflight, confirmation, mutation lease, execution, and verification.
- Support Bundle v12 is the current writer. Advancing to v13 belongs to Phase
  4; v2-v12 readers remain supported.
- Home, navigation, search, page construction, and authenticated API GET
  requests never start collection.

## Protected behavior

- Preserve all 81 route IDs, ordered projection, aliases, favorites, direct
  links, saved navigation, six destinations, one Home, and lazy loading.
- Preserve Action Center schema v4 and prohibit automatic confirmation,
  execution, reboot, rollback, retry, resume, chaining, or parameter
  broadening.
- Preserve System Check, Trusted Change Journal, observability, CLI JSON,
  daemon, D-Bus, loopback-only read-only API, and future-schema read-only
  behavior.
- Preserve Traditional and Atomic policy separation.
- Preserve one realized Home provider with no cold-start subprocess probe,
  active timer, or running QThread.
- Preserve fixed non-privileged V22 native handoffs and V20's historical
  `PUBLICATION BLOCKED` status.

## Release-lineage blocker

The historical annotated tag `v23.0.0` already exists and peels to
`adc4cef116d147bd5b845f0ec98c3a1970b8b054` ("Architecture Hardening"). Phase
0 does not move, delete, replace, or publish that tag. Compass release naming
and preservation of the historical lineage require separate release authority
before Phase 6 can complete.

## Phase gates

- Product metadata remains v22.0.0 "Alignment" through Phases 0-5.
- Each authorized phase must pass focused tests and the current architecture,
  product, route, release-document, startup, compatibility, and coverage gates.
- Physical Wayland, Orca/AT-SPI, Traditional, Atomic, signing, GitHub, COPR,
  installation, and public readback cannot be inferred from local or offscreen
  evidence.
- Commit, push, tag, publication, host installation, and remote modification
  require separate authorization.
