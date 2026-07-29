# V23 Phase 1 Troubleshooting Domain

Date: 2026-07-29  
Active target: `v23.0.0 "Compass"`  
Product metadata: `v22.0.0 "Alignment"`  
Scope: local Phase 1 implementation only

## Outcome

Phase 1 adds the safe, PyQt-free domain boundary required before any Compass
collector, evidence composition, UI, CLI, API, or support-export work.

`core/troubleshooting/` now owns:

- immutable session, source-result, finding, related-change, next-step,
  compatibility, and comparison contracts;
- the six closed profile definitions and exact Traditional/Atomic source
  budgets;
- strict bounded JSON-like validation for parameters and evidence;
- pure queued, running, completed, partial, cancelled, and failed lifecycle
  transitions;
- one cooperative cancellation signal with no callback or worker ownership;
  and
- an explicit schema-v1 XDG session store with atomic private writes, 20-session
  retention, malformed-input rejection, and future-schema read-only behavior.

The domain starts no collection and contains no command vector, callback,
renderer, credential, token, secret, raw process output, UI object, or execution
authority.

## Closed profile budgets

Budgets are exact maximum wall-clock source budgets for the sources applicable
to one Fedora variant. Mutually exclusive Traditional and Atomic sources do not
inflate the per-variant total.

| Profile | Traditional sources | Atomic sources | Total |
| --- | --- | --- | ---: |
| `system_slow` | System Check 45 s; observability 2 s; change journal 15 s | same | 62 s |
| `updates_failed` | package health 20 s; pending reboot 20 s; change journal 15 s; Action Center 10 s | deployment state 20 s; pending reboot 20 s; change journal 15 s; Action Center 10 s | 65 s |
| `application_failed` | application inventory 20 s; change journal 15 s | same | 35 s |
| `network_problem` | network state 5 s; DNS state 5 s; optional change journal 15 s | same | 25 s |
| `storage_pressure` | System Check 45 s; reclaim analysis 25 s; change journal 15 s | same | 85 s |
| `boot_or_deployment` | boot analysis 30 s; failed services 10 s; pending reboot 20 s; package history 15 s | boot analysis 30 s; failed services 10 s; pending reboot 20 s; deployment history 15 s | 75 s |

`application_failed` remains deliberately reduced because Phase 0 found no safe
closed application-journal collector. `network_problem` remains reduced because
network scans and mixed mutators are excluded. Phase 2 must implement only the
listed read-only adapters.

## State and safety semantics

- A session exists only after an explicit caller invokes `new_session`.
- Importing the package creates no session and starts no probe, write, timer,
  worker, or thread.
- Every applicable profile source receives one terminal result. Missing sources
  become explicitly `unavailable`; they are never interpreted as empty.
- Any unavailable, timed-out, failed, or cancelled evidence prevents
  `completed`.
- A cooperative cancellation request marks unfinished sources `cancelled` and
  produces a cancelled session without retaining facts for those sources.
- Completed results cannot exceed their declared timeout. Timed-out results
  cannot be declared before the timeout.
- Findings require a deterministic privacy-safe fingerprint, source timestamp,
  freshness, evidence quality, Fedora applicability, typed resource IDs, and
  exactly one inert next step.
- Action next steps resolve only against the closed Action Center catalog and
  its typed parameter validator. Navigation resolves only exact canonical route
  IDs.
- Related changes always retain the label **Possibly related** and only the
  closed reasons `time_proximity` or `shared_resource`.
- Comparison is a Phase 1 data contract only. Evidence matching and before/after
  classification remain Phase 2.

## Persistence

The state inventory registers `troubleshooting_sessions` at
`$XDG_DATA_HOME/loofi-fedora-tweaks/troubleshooting_sessions.json` with schema
ID `loofi.troubleshooting-sessions`, schema version 1, private sensitivity, and
20-session retention.

Persistence is explicit and terminal-only. Writes use the existing advisory
lock and atomic readback-verified JSON infrastructure with mode `0600`.
Malformed, oversized, or unknown stores fail closed. A future schema is exposed
as read-only metadata and a save attempt raises before any rewrite.

## Protected contracts

Phase 1 changes no route, destination, UI, CLI, API, daemon, D-Bus, collector,
System Check result, Trusted Change Journal record, Action Center schema,
support bundle, product version, package, tag, installation, or remote state.
All 81 routes remain owned by the existing catalog. Action Center remains the
only host mutation authority.

## Verification

The Phase 1 focused suite covers:

- all six profiles, variant branches, exact source budgets, and reduced-profile
  boundaries;
- immutable contracts, deterministic fingerprints, typed parameters and
  resources, closed next steps, malformed data, authority fields, secrets, raw
  output, personal paths, and bounded text;
- success, partial, unavailable, timeout, failure, and cancellation states;
- atomic private persistence, retention, malformed/oversized input, and future
  schemas;
- import-time probe, write, timer, thread, worker, service, and PyQt absence.

Phase 2 remains not started. No physical Fedora, Wayland, Orca/AT-SPI, Atomic,
artifact, installation, signing, CI, COPR, GitHub, or public-release claim is
made by this local phase.
