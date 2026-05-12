# Architecture — v8.1.0

## Goals

- Preserve the v8 route manifest as the canonical navigation contract while presenting a smaller, clearer desktop shell.
- Keep all route IDs, favorites, quick actions, command palette entries, and legacy aliases compatible with v8.0.0.
- Make the PyQt6 interface breathe: roomier margins, stronger visual hierarchy, clearer selected states, and no clipped text at Wayland/fractional scale factors.
- Keep advanced, automation, AI, and experimental tools available without making them part of the default visual menu.

## Decisions

- Add `core.navigation.areas.NavigationArea` as a PyQt-free grouping layer beside the route manifest. `NavigationRoute` remains the stable API for route resolution.
- Default navigation exposes five primary areas: Home, Software & Updates, System & Hardware, Network & Security, and Desktop & Settings. Advanced mode adds More.
- Hide advanced routes from the default sidebar only. They remain reachable through search, favorites, command palette, direct routes, and Advanced mode.
- Rename the launch surface to Home. The previous live dashboard behavior stays route-addressable instead of becoming a second top-level Home entry.
- Rework `MainWindow` as a focused shell: sidebar/rail, top page header with search/action affordances, content stack, and compact footer.
- Add `ui.layout_primitives` for page headers, sections, action rows, route cards, adaptive grids, and font/screen-derived metrics.
- Let Qt handle device-independent sizing; derive initial window size from `QScreen.availableGeometry()` and adapt sidebar presentation across narrow, medium, and wide widths.
- Keep UI code inside `ui/`, navigation contracts inside `core/navigation/`, and package/release checks inside scripts/tests.

## Validation Contract

- Navigation tests cover unique area IDs, route resolution, hidden advanced route searchability, favorites overriding hidden defaults, and visible-tab ID drift.
- Geometry tests cover available-screen sizing, sidebar breakpoints, scroll wrapping, and stable widths under `QT_SCALE_FACTOR=1`, `1.25`, `1.5`, and `2`.
- Packaging tests require `core/navigation/areas.py` and `ui/layout_primitives.py` to ship in release artifacts.
- Release gates require updated README, changelog, release notes, roadmap, screenshots, AppStream metadata, RPM spec, and GitHub/COPR package metadata.
