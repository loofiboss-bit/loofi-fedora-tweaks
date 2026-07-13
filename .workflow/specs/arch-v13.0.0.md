# Architecture — v13.0.0 "Anchor"

## Goals

Make application-owned state crash-safe, inspectable, migratable, privacy-safe, and recoverable without expanding privilege or daemon mutation scope.

## Decisions

- `core/state` owns XDG paths, registered state domains, schemas, migrations, atomic writes, advisory locks, doctor results, and state archives.
- Numeric SQLite metrics remain `MetricTimelineStore`; structured JSON snapshots remain `HealthSnapshotStore`; `ObservabilityService` provides a shared status and collection facade.
- Future schemas are read-only. Migration advances one version at a time and records completion only after readback.
- Restore is always plan then explicit apply, rejects unsafe archives, and creates a rollback archive first.
- State Doctor and background collection are read-only. No fix-all, automatic reset, restore, upgrade, cleanup, or restart exists.
- Fedora 44 remains supported; Fedora 45 remains preview until every promotion criterion has evidence and a maintainer changes the typed registry.

## Compatibility

v12 files remain at their existing paths, legacy imports remain for the v13 cycle, stable route/CLI/plugin IDs are unchanged, and support exports preserve earlier fields.
