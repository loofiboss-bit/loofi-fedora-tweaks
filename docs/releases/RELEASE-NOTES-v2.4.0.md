# Release Notes -- v2.4.0 "Daemon Foundation"

**Release Date:** 2026-02-25
**Codename:** Daemon Foundation
**Theme:** Daemon-first execution boundary and IPC fallback alignment.

## Summary

v2.4.0 establishes the daemon foundation used by later API migration slices.
It introduces daemonized execution boundaries for selected operations while preserving
safe fallback behavior for local execution paths.

## Highlights

- Daemon-first network/firewall execution pathways introduced.
- IPC envelope and fallback semantics aligned for safer migration.
- Baseline stabilization and workflow/reporting consistency improvements.

## Changes

### Changed

- Service pathways updated to support daemon-first execution where available.
- IPC handling refined for strict envelope behavior and safe fallback.

### Added

- Foundation hooks for daemon-backed request routing and compatibility checks.

### Fixed

- Workflow/report consistency gaps that affected release-doc readiness checks.

## Stats

- **Tests:** See `.workflow/reports/test-results-v2.4.json`
- **Lint:** Project lint baseline retained
- **Coverage:** See CI and workflow reports

## Upgrade Notes

No breaking CLI or UI contract changes intended for this foundational release.
