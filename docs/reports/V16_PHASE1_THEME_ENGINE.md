<!-- Hallmark · pre-emit critique: P5 H5 E5 S5 R5 V5 -->

# v16.0.0 "Clarity" Phase 1 Theme Engine

**Status:** implemented and verified locally

**Authority:** [`docs/plans/LOOFI_FEDORA_TWEAKS_V16_PLAN.md`](../plans/LOOFI_FEDORA_TWEAKS_V16_PLAN.md)

**Working branch:** `v16-clarity`

## Outcome

Phase 1 replaces the active three-file theme split with one structural QSS
source and four semantic palettes. System mode now keeps the same cards,
navigation, state surfaces, interaction feedback, and focus treatment as the
explicit themes while deriving colors from Qt's live `QPalette`.

The application version remains `15.0.0 "Essentials"`. This phase does not
change routes, domain behavior, privilege boundaries, packaging layout, remote
state, or the v16 version metadata. Shared components and page redesign remain
Phases 2–6.

## Design contract

| Contract | Implementation |
| --- | --- |
| One active structural source | `assets/base.qss`, rendered by `ui/design/theme_manager.py` |
| Theme fixtures | System, dark, light, and high contrast |
| System theme | Semantic roles derived from `QPalette`; structural QSS always remains active |
| Stable geometry | `DesignTokens` owns spacing, radii, border/focus widths, control heights, navigation height, and content measure |
| Native typography | Weight roles only; no application-level font family or font size |
| Component scoping | Named widgets, object names, and dynamic properties; only a minimal global color baseline |
| Interaction/state roles | Hover, selected, focus, disabled, success, warning, and error contracts |
| Dynamic paint paths | Charts, toasts, overlays, status dots, and icon tints resolve semantic roles at paint or refresh time |

Theme changes therefore change palette values only. The rendered structural
stylesheet and `DesignTokens.geometry_signature()` remain invariant across all
four modes.

## Migration

The Phase 0 inventory recorded 163 direct UI color sites. Phase 1 migrates the
runtime sites in `ui/` to the semantic palette contract, including inline style
paths, chart painters, notification categories, dialog HTML, status indicators,
tour overlays, task/readiness states, and icon tint groups. A focused guard now
fails if direct hex or numeric `QColor` product colors return outside
`ui/design/`.

The legacy `modern.qss`, `light.qss`, and `highcontrast.qss` files remain in the
source tree as historical inputs for later Phase 6 cleanup. They are no longer
loaded by the application or required by the packaging manifest.

The sidebar selector now targets the actual `QTreeWidget#destinationSidebar`
implementation instead of the stale `QListWidget` selector identified in the
Phase 0 audit.

## Accessibility and failure behavior

- Explicit palettes and generated system palettes enforce WCAG contrast floors
  for body text, muted text, selected/focus states, and semantic status pairs.
- Focus treatment uses the semantic focus role consistently across navigation,
  controls, cards, lists, trees, and tables.
- Disabled controls use semantic surface and text roles instead of opacity
  alone.
- Missing or invalid structural QSS fails without clearing the application's
  current stylesheet.
- Unknown saved theme values fall back to the dark fixture.

## Verification

| Gate | Result |
| --- | --- |
| Focused theme/UI regression suite | 818 passed; 2 warnings |
| Theme fixtures and structural invariance | Passed for system, dark, light, and high contrast |
| Real offscreen `QApplication` smoke | All four themes applied; zero Qt messages |
| Direct UI color inventory | Zero runtime violations outside `ui/design/` |
| Modified-source lint and typecheck | Flake8 and mypy passed |
| Syntax and whitespace | `py_compile` and `git diff --check` passed |
| `just verify` | Passed: 7,652 tests, 40 skipped, 632 subtests; 86.16% coverage; lint and mypy passed |
| Release-document validation | `just validate-release` passed |
| Packaging manifest/build | `just check-packaging` passed; theme engine and structural QSS are packaged |
| Agent adapter drift | `just check-drift` passed |

The offscreen smoke proves theme application and QSS parsing, not live
Wayland/X11 compositor behavior. The real-shell scaling, keyboard, AT-SPI/Orca,
and compositor matrix remains Phase 7 by design.

## Deferred work

- Phase 2 creates the shared component and page-scaffold layer on top of these
  tokens.
- Phases 3–6 adopt the system across the shell and destination pages, then
  remove legacy presentation files only after compatibility coverage exists.
- Phase 7 performs live Fedora KDE theme, scaling, keyboard, accessibility, and
  contrast validation.
- Phase 8 owns version bump, packaging/release gates, publication, and remote
  verification.

No commit, push, tag, release, or remote mutation is part of this phase handoff.
