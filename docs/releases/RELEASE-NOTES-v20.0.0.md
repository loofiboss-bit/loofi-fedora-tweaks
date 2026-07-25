# Release Notes -- v20.0.0 "Continuity"

**Release Date:** 2026-07-25
**Codename:** Continuity
**Theme:** Trusted change history and conservative recovery

## Summary

Continuity turns existing local package, deployment, firmware, Flatpak, Loofi,
and Action Center records into one privacy-bounded Activity & Recovery view.
Recovery remains inside Action Center and is offered only when the current
system state can be checked again.

## Highlights

- Trusted Change Journal with source readiness, stable inert event IDs, redacted
  facts, and explicitly heuristic “Possibly related” links.
- Exact DNF5 offline transaction recovery for verifiable install/remove history.
- Exact rpm-ostree previous-deployment rollback with post-reboot checksum
  verification.
- New lazy Activity & Recovery page under System, plus CLI and authenticated
  read-only API access.
- Unified Specialist Tools navigation without a global safety-mode switch.

## Changes

### Added

- `loofi.change-journal/v1` domain contracts and adapters for Action Center,
  DNF5, rpm-ostree, Flatpak, fwupd, and Loofi history.
- `activity list/show/related/recover` CLI commands.
- `GET /api/activity` and `GET /api/activity/{event_id}`.
- Support bundle v12 with at most 50 redacted journal events.

### Changed

- Fedora updates on Traditional systems stage with DNF5 offline transactions.
- Legacy CLI host changes now create exact named Action Center review plans.
- The visible Advanced destination is named Specialist Tools and is always
  available; action-specific confirmation and privilege policy are unchanged.

### Fixed

- Legacy `undo_command` data is no longer persisted or executable. History
  migrates atomically to schema v2 with a retained v1 backup.
- `loofi --cli activity --help` now reaches the real CLI subparser.
- Missing, partial, and unavailable journal sources remain distinct from an
  empty successful source.

## Safety and Upgrade Notes

- No recovery path automatically reboots.
- DNF upgrades/downgrades and ambiguous transactions remain guidance-only.
- Flatpak and firmware records remain guidance-only.
- Existing route IDs and persisted navigation values are retained as
  compatibility inputs.
- The historical Synapse lineage is preserved as
  `legacy-v20.0.0-synapse`.

## Local Verification

The v20 release candidate passed:

- `just verify`: lint, mypy, architecture, 6,822 tests, 68 expected skips,
  1,057 subtests, and 86.10% statement coverage.
- `just validate-release` and `just check-packaging`.
- Product-catalog, project-statistics, version-alignment, and generated-agent
  drift checks.
- 59 focused offscreen Activity & Recovery and UI smoke tests.

The canonical GitHub workflow publishes commit-bound RPM, Flatpak, source
distribution, checksum, CycloneDX SBOM, and in-toto provenance artifacts.
