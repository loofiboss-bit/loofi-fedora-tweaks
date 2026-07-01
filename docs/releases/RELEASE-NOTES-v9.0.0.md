# Release Notes -- v9.0.0 "Keystone"

**Release Date:** 2026-07-01
**Codename:** Keystone
**Theme:** Whole-app quality, execution consistency, state reliability, and release hygiene

## Summary

Loofi Fedora Tweaks v9.0.0 "Keystone" is a whole-app quality release. It does not make Fedora 45 the main target: Fedora KDE 44 remains the supported readiness target, while Fedora 45 stays available only as the `45-preview` advisory profile.

Keystone focuses on tightening existing app behavior across GUI, CLI, daemon/API, packaging, state, tests, and docs. It adds a small shared execution facade, raises the release quality gate, improves route/plugin trust checks, and documents the settings/state migration contract for existing users.

## Highlights

- Fedora KDE 44 remains the default supported readiness target.
- Fedora 45 remains `45-preview` and advisory only.
- Shared command facade provides a single list-based preview/execute contract over the existing executor policy.
- Coverage gate raised from 82% to 84% across local and CI release surfaces.
- Route/plugin drift checks now cover hidden advanced routes, command palette routes, quick actions, and plugin metadata.
- v9 workflow specs describe app-wide quality work instead of adding another permanent feature tab.

## Changes

### Changed

- Bumped runtime, package, workflow, and release metadata to `9.0.0 "Keystone"`.
- Updated roadmap, changelog, README, architecture docs, troubleshooting, release checklist, docs index, and wiki-facing release wording for the v9 quality scope.
- Marked the old v10 strategic plan as historical because its version and project-size assumptions are stale.
- Raised coverage enforcement to 84%.

### Added

- Added `CommandFacade` for consistent preview/execute handling with command vectors, privilege flags, timeout, and action IDs.
- Added v9 workflow architecture and task contracts.
- Added regression coverage for readiness defaults, preview target status, route/plugin trust, and command facade policy.

### Fixed

- Clarified explicit Qt runtime exceptions in architecture docs.
- Documented state/settings migration expectations for theme, experience level, favorites, hidden routes, and window geometry.
- Refreshed stale troubleshooting text that referenced older release cycles.

## Stats

- **Tests:** 7,391 passed, 48 skipped, 0 failed
- **Lint:** 0 errors
- **Coverage:** 84.25% total, above the 84% release gate

## Upgrade Notes

No Fedora 45 migration is required for v9. Existing routes, favorites, CLI commands, plugin metadata, and saved settings remain compatible.
