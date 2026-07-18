<!-- Hallmark · pre-emit critique: P5 H5 E5 S5 R5 V5 -->

# v16.0.0 "Clarity" Phase 3 Application Shell

**Status:** implemented and verified locally

**Authority:** [`docs/plans/LOOFI_FEDORA_TWEAKS_V16_PLAN.md`](../plans/LOOFI_FEDORA_TWEAKS_V16_PLAN.md)

**Working branch:** `v16-clarity`

## Outcome

Phase 3 replaces the application-level horizontal route tabs with the shared
responsive `SectionNavigator`. The shell now presents full section labels in a
vertical rail when space permits and a full-width selector above content at the
860-DIP minimum layout. It also clamps the primary sidebar, provides a visible
global-search affordance, uses an accessible native icon control for collapse,
and keeps redundant destination eyebrow text hidden.

The application remains `15.0.0 "Essentials"`. No route, alias, redirect,
favorite, migration, policy, Action Center, state, system-operation, or version
contract changed in this phase.

## Explicit section contract

`core.navigation.SectionDefinition` adds data-only presentation metadata for
all 47 existing destination-owned section IDs:

- destination and section identity;
- full label and description;
- semantic icon;
- stable visual order;
- stable default route.

Validation requires every route placement to resolve to exactly one destination
section and requires every section default route to remain within that section.
Default-route behavior is preserved, including the Updates section continuing
to open the canonical `maintenance` route.

## Responsive shell behavior

| Application width | Primary navigation | Section navigation |
| --- | --- | --- |
| 1180 DIP and above | Expanded, clamped to 248–272 DIP | 208–224 DIP full-label rail beside content |
| 900–1179 DIP | 64–72 DIP icon rail | Full-label rail beside content |
| 860–899 DIP | 64–72 DIP icon rail | Full-width selector above content |

Collapsed destination rows retain accessible text and full-label tooltips.
Section rows and selector entries carry full labels, descriptions, and semantic
icons. Theme changes refresh both destination and section icon tints without
reconstructing navigation.

The visible Search control opens the same policy-backed surface as `Ctrl+K`.
The existing `Ctrl+Shift+K`, destination shortcuts, route history, back/forward,
deep links, favorites, policy explanations, and lazy plugin activation remain
on their existing paths.

## Compatibility evidence

- All 80 canonical route IDs still open or show the same fail-closed policy
  explanation in the relevant navigation context.
- Standard mode remains exactly six destinations; Advanced adds exactly one.
- Redirects and aliases continue through `resolve()` and `NavigationPolicy`.
- Action Center navigation remains navigation-only and never plans or runs an
  action.
- Mode changes reuse existing lazy placeholders and do not construct plugins.
- The `SectionItem` positional status contract remains backward compatible.

## Startup evidence

The clean offscreen benchmark used one warm-up and ten measured runs:

| Measurement | Result |
| --- | --- |
| Meaningful Home median | 180.573 ms |
| Binding relative limit | 182.309 ms |
| RSS median | 78,226 KiB |
| Runtime plugins | `atlas_dashboard` only in 10/10 runs |
| Plugin specs | 28 |
| Subprocess probes | 0 |
| Active timers | 0 |
| Running `QThread` instances | 0 |

The performance margin is small, so Phase 8 must repeat the benchmark on the
same host and method before release. Phase 3 nevertheless preserves the
current startup contract and remains below both the relative and absolute
limits.

## Verification

| Gate | Result |
| --- | --- |
| `just verify` | Passed |
| Full test and coverage suite | 7,681 passed, 40 skipped, 820 subtests; 86.28% coverage |
| Flake8 | Passed |
| Mypy | Passed |
| `git diff --check` | Passed |
| Ten-run startup benchmark | Passed |
| Route/alias/policy/lazy shell regression | Passed |
| 860/900/1180-DIP presentation checks | Passed |
| Search, collapse, accessibility, and theme-icon checks | Passed |

Offscreen tests prove widget structure, responsive policy, full-label metadata,
keyboard signal paths, accessibility metadata, lazy loading, and startup
invariants. Live Wayland/X11 compositor scaling, AT-SPI/Orca, and human visual
review remain Phase 7 evidence.

## Deferred work

- Phase 4 redesigns Home and System content on top of this shell.
- Phase 5 migrates the remaining Standard destinations.
- Phase 6 adopts the shared presentation system in Advanced and removes proven
  dead legacy presentation code.
- Phase 7 owns live Fedora KDE visual, compositor, keyboard, contrast, and
  screen-reader evidence.
- Phase 8 owns the version bump, packaging and release gates, and publication
  readiness.

No commit, push, tag, release, or remote mutation is part of this phase.
