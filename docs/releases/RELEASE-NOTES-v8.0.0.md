# Release Notes -- v8.0.0 "Beacon"

**Release Date:** 2026-05-12
**Codename:** Beacon
**Theme:** Navigation reliability, visual clarity, and release trust

## Summary

Loofi Fedora Tweaks v8.0.0 "Beacon" is a navigation-first reliability release. It does not add another major feature tab; instead it makes the existing control center easier to search, route, pin, and validate with a shared navigation manifest and stronger release gates.

Beacon also hardens command safety and packaging confidence. Preview and execute paths now share the same command policy, favorites use stable route IDs, RPM import checks are blocking, and the release gate validates dynamic plugin counts instead of stale tab-count claims.

## Highlights

- Central `core.navigation` manifest with stable plugin and subroute IDs.
- Route-aware command palette, quick actions, dashboard cards, favorites, sidebar selection, and breadcrumbs.
- Favorites v2 migration from legacy display-name-derived IDs.
- Icon-only collapsed sidebar with tooltips, status dots, semantic icons, and QSS-backed styling.
- Shared command allowlist enforced before action previews, action execution, web API executor calls, and ProfileManager snapshot commands.
- Packaging manifest gate for source subpackages, QSS/icons, translations, agent/config resources, and console entry point metadata.
- Release validation now requires exactly one ACTIVE roadmap release and an 82% coverage threshold.

## Changes

### Changed

- Bumped runtime, package, workflow, and release metadata to `8.0.0 "Beacon"`.
- Refactored navigation entry points to use canonical route IDs such as `maintenance:updates`, `software:apps`, `security:firewall`, and `system-monitor:processes`.
- Updated current docs and release gates to validate the live PluginRegistry/PluginLoader surface instead of hardcoded tab counts.
- Raised CI, auto-release, Justfile, and docs validation coverage gates to 82%.

### Added

- Added `NavigationRoute` and manifest APIs: `all_routes()`, `get_route()`, `resolve()`, `routes_for_palette()`, `routes_for_quick_actions()`, and `validate_routes()`.
- Added `MainWindow.switch_to_route(route_id)` with backward-compatible `switch_to_tab(name)` alias handling.
- Added Favorites v2 persistence: `{"version": 2, "favorites": [...]}`.
- Added `core.executor.command_policy` and `scripts/check_packaging_manifest.py`.

### Fixed

- Fixed command palette and quick action drift from legacy tab display names.
- Fixed stale favorites by resolving known aliases and dropping unknown legacy entries with warnings.
- Fixed virtualization tab loading so the built-in plugin remains part of the live navigation count.
- Fixed RPM import validation so import failures block `%check` instead of being ignored.

## Stats

- **Tests:** Pending final release run
- **Lint:** Pending final release run
- **Coverage:** 82% required gate

## Upgrade Notes

Existing favorites migrate automatically on first load. Unknown stale favorites are dropped safely with a warning. No new permanent feature tab is added in this release.
