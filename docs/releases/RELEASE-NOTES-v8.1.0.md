# Release Notes -- v8.1.0 "Breeze"

**Release Date:** 2026-05-13
**Codename:** Breeze
**Theme:** Focused sidebar, airy desktop layout, and responsive scaling

## Summary

Loofi Fedora Tweaks v8.1.0 "Breeze" is a full UI/UX redesign of the existing PyQt6 control center. It keeps the v8 route architecture and plugin system intact, but makes the app easier to navigate by replacing the crowded default menu with five primary areas and giving pages more space, clearer headers, and safer text wrapping.

Breeze also improves Wayland and fractional-scaling behavior. Window size, sidebar width, header height, status height, and content spacing now derive from Qt device-independent units, font metrics, and available screen geometry instead of hard-coded pixel assumptions.

## Highlights

- Default sidebar now shows five focused areas: Home, Software & Updates, System & Hardware, Network & Security, and Desktop & Settings.
- Advanced and automation-heavy pages remain searchable, favoriteable, and route-addressable, but no longer crowd the default navigation.
- Main window shell now uses a clearer page header, roomier sidebar rows, content stack, and compact footer.
- New shared UI primitives support consistent page headers, sections, action rows, route cards, and adaptive grids.
- Dark, light, and high-contrast themes now share the same airy spacing and selected-state rules.
- Startup honors the saved/system theme instead of always loading the dark theme.
- User-guide and wiki screenshots were regenerated from the redesigned PyQt UI.

## Changes

### Changed

- Bumped runtime, package, workflow, and release metadata to `8.1.0 "Breeze"`.
- Renamed Atlas Home to Home and made it the single launch page.
- Moved the live overview behind a Home route card/subroute instead of exposing a second top-level Home item.
- Reworked `MainWindow` around focused areas while preserving `switch_to_route()`, command palette, quick actions, favorites, and legacy aliases.
- Increased content margins and updated QSS for calmer KDE-native contrast, card borders, sidebar selection, and text wrapping.
- Updated screenshots in `docs/images/user-guide/` and `wiki/images/`.

### Added

- Added `core.navigation.areas.NavigationArea` and area validation helpers.
- Added `ui.layout_primitives` with `LayoutMetrics`, `PageHeader`, `Section`, `ActionRow`, `RouteCard`, and `AdaptiveGrid`.
- Added route/area tests for unique area IDs, default area count, route resolution, hidden advanced route searchability, and real plugin ID visibility.
- Added scaling smoke checks for `QT_SCALE_FACTOR=1`, `1.25`, `1.5`, and `2`.

### Fixed

- Fixed experience-level drift by aligning visible-tab IDs with real plugin IDs such as `system_info` and `snapshots`.
- Fixed hidden route handling so favorites and direct route switching continue to work when pages are not visible in the default sidebar.
- Fixed package manifest checks so the new navigation and layout modules are included in source distributions.

## Stats

- **Tests:** 7,378 passed, 48 skipped, 0 failed
- **Lint:** 0 errors
- **Typecheck:** 0 errors
- **Coverage:** 84.19% total, above the 82% release gate

## Upgrade Notes

No feature is removed. Users who prefer the old broad menu can switch to Advanced mode in Settings, favorite specialized pages, or use search/command palette to jump directly to any route.
