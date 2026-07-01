# Release Notes -- v11.0.0 "Harbor"

**Release Date:** 2026-07-01
**Codename:** Harbor
**Theme:** Unified Action Center, Daily Maintenance UX, Release Trust

## Summary

v11.0.0 "Harbor" makes existing Fedora maintenance and readiness workflows easier to trust. It adds a unified Action Center model for previewable actions, read-only daily maintenance diagnostics, rollback-first metadata for risky operations, and Support Bundle v7 export data while preserving Fedora KDE 44 as the stable target and Fedora 45 as advisory preview planning.

## Highlights

- Unified Action Center core model, queue, rollback guidance, bounded history, and readiness-action integration
- Maintenance > Action Center GUI surface and `action-center` CLI commands for listing, previewing, and inspecting recent Action Center history
- Daily Maintenance diagnostics for updates, Flatpak, firmware, failed services, journal warnings, disk usage, package health, and rollback availability
- Support Bundle v7 with Action Center summaries, rollback hints, daemon/API status, maintenance data, and GitHub issue text export
- Release validation for AppStream release entries and workflow spec version/codename drift

## Changes

### Changed

- Runtime, package, docs, workflow, and AppStream metadata now target `11.0.0 "Harbor"`.
- Fedora 44 remains the stable supported profile; Fedora 45 remains preview/advisory.
- Support bundle schema is now `11.0.0-harbor-support-v7` with `support_bundle_version: 7`.

### Added

- `core.actions` Action Center service, queue, history, rollback, and model modules plus the Maintenance Action Center sub-tab
- `core.diagnostics.daily_maintenance` read-only maintenance probes
- `core.export.support_bundle_v7` compatibility import path

### Fixed

- Release drift validation now catches missing AppStream v11 entries and workflow spec codename drift.

## Stats

- **Tests:** See release verification output
- **Lint:** 0 errors
- **Coverage:** 84% gate

## Upgrade Notes

No migration is required. Existing readiness CLI commands, support bundle import paths, plugin IDs, route IDs, favorites, and saved settings remain compatible.
