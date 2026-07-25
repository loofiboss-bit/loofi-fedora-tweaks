# Architecture — v20.0.0 "Continuity"

## Objective

Make local change history useful for diagnosis and recovery without restoring
command-bearing history, adding a second execution authority, or weakening
Action Center review and verification.

## Trusted Change Journal

- `core/change_journal` is PyQt-free and composes source-owned records from
  Action Center, DNF5, rpm-ostree, Flatpak, fwupd, and Loofi history.
- The journal has no authoritative database. A 15-second in-memory cache limits
  repeated probes; every durable fact remains owned by its source.
- Events use `loofi.change-journal/v1`, stable hashed IDs, bounded redacted
  facts, explicit source readiness, and closed recovery metadata.
- Correlation is a heuristic time-and-resource match. Interfaces must call it
  “Possibly related” and never claim causality.
- Recovery metadata contains only a registered Action Center action ID and
  typed parameters, manual guidance, or no recovery. It cannot contain a
  command, callback, renderer, or shell fragment.

## History migration

Legacy `history.json` lists migrate atomically to schema v2. A one-time
`history.v1.json.bak` is retained, descriptions are redacted, and every legacy
`undo_command` is discarded. Unknown future schemas are never rewritten.
Compatibility undo methods return guidance or an Action Center identifier and
never execute.

## Safe recovery

- Traditional Fedora system updates stage through DNF5 offline transactions.
- `dnf5-history-undo` accepts one positive transaction ID, refreshes
  `dnf5 history info --json`, and permits only exact successful Install/Remove
  shapes. Upgrade, downgrade, mixed, incomplete, or ambiguous transactions fail
  closed. The inverse is staged offline and verified after a changed boot.
- `rpm-ostree-rollback` binds the current and previous 64-character deployment
  checksums, stages the existing rollback deployment, and succeeds only after a
  changed boot reports the exact expected checksum.
- Neither workflow automatically reboots, retries, resumes, or chains another
  mutation. Flatpak and firmware records provide guidance only.

## Interfaces

- `activity` is a stable route under System and remains lazily loaded.
  Collection starts only from Load activity or Refresh sources and runs in a
  `BaseWorker`.
- CLI supports `activity list`, `show`, `related`, and `recover`. Recover only
  creates a normal plan.
- `/api/activity` and `/api/activity/{event_id}` are bearer-authenticated GET
  routes. No journal mutation API exists.
- Support bundle v12 includes at most 50 redacted events and source statuses,
  with no raw command output or recovery command vector.

## Mutation and navigation boundaries

Legacy battery, DNF tuning, BBR, GameMode, swappiness, and DNS helpers are inert.
CLI requests map to named typed manual Action Center definitions; DNS requires
an exact NetworkManager connection name.

The visible Standard/Advanced switch is retired. The stable `advanced`
destination and old setting values remain compatibility identifiers, while the
surface is labelled Specialist Tools and always loaded in the unified shell.
This does not change per-action risk, privilege, confirmation, or platform
policy.

## Compatibility and non-goals

- Preserve stable route IDs, aliases, favorites, settings readers, Action
  Center plans/runs, System Check, health metrics, and Traditional/Atomic
  behavior.
- No new feature family, external plugin execution, authoritative journal DB,
  physical extras RPM split, or automatic reboot.
