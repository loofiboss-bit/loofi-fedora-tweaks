# Release Notes -- v13.0.0 "Anchor"

**Release Date:** 2026-07-13
**Codename:** Anchor
**Theme:** State integrity, recovery, and release reliability

## Summary

Anchor consolidates v12 observability into a trustworthy local-state system. It adds crash-safe persistence, read-only diagnostics, privacy-safe backup and explicit restore planning while keeping Fedora 44 stable and Fedora 45 advisory.

## Highlights

- State Doctor inventories and validates every registered state domain without mutating it.
- State archives use schema metadata and SHA-256 hashes, exclude secret domains, and require plan-before-apply.
- Structured snapshots use atomic replace, fsync, advisory locking, readback verification, and a last-known-good copy.
- Numeric metric history and structured health snapshots remain separate behind one observability facade.

## Changes

### Changed

- Source install documentation uses `pyproject.toml` as the dependency source of truth.
- Daemon and API snapshot collection now publish the canonical collector status contract.

### Added

- `core/state` path, inventory, schema, migration, atomic I/O, doctor, and archive services.
- CLI `state doctor`, `state backup`, `state restore plan`, and `state restore apply` commands.
- Authenticated read-only `/state/status` and `/observability/status` API routes.

### Fixed

- Corrected architecture, roadmap, security-support, source-install, and release metadata drift.
- Corrupt or future state is surfaced as degraded/read-only instead of silently overwritten.

## Stats

- **Tests:** 7,440 passed, 48 skipped, 0 failed
- **Lint:** 0 errors
- **Coverage:** 84.39%

## Upgrade Notes

v12 structured snapshots and numeric metrics remain in place and are not destructively merged. The first successful v13 write creates a bounded last-known-good copy. Restore rollback archives are stored under the application XDG data directory in `backups/`.
