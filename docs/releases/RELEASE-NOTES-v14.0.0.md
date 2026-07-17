# Release Notes -- v14.0.0 "Helm"

**Release Date:** 2026-07-17
**Codename:** Helm
**Theme:** Verified guided maintenance and exact release assurance

## Summary

Helm turns selected maintenance findings into expiring, reviewable plans with
explicit confirmation, bounded execution, separate verification, and durable
recovery evidence. Fedora 44 remains supported while Fedora 45 stays advisory.

## Highlights

- Review preflight, exact command, privilege, risk, rollback readiness, execution, and verification in one Action Center flow.
- Execute only the deny-by-default DNF cache, selected failed-service, and supported SSD trim definitions.
- Preserve interrupted runs without automatic retry or rollback.
- Verify release source, tag, GitHub assets, and Fedora 44/COPR packages against the same commit.

## Changes

### Changed

- Existing Action Center items, readiness CLI aliases, route IDs, plugin IDs, favorites, settings, API envelopes, and D-Bus methods remain compatible.
- Fedora 44 remains the blocking supported target and Fedora 45 remains preview/advisory.

### Added

- Canonical action definitions, expiring plans, durable runs, policy decisions, and verification states.
- CLI plan/show/apply/verify commands and authenticated read-only API plan/run routes.
- Support Bundle v10 action lifecycle evidence with privacy redaction.

### Fixed

- Corrected state inventory paths, schema-aware doctor checks, collector locking, and atomic restore behavior.
- Prevented stale or mismatched Git tags from supplying release source archives.

## Stats

- **Tests:** Final count recorded by the release gate
- **Lint:** 0 errors
- **Coverage:** 85% minimum

## Upgrade Notes

Existing state and action history remain readable. Plans expire after 30 minutes;
an interrupted run is preserved for inspection and is never resumed automatically.
