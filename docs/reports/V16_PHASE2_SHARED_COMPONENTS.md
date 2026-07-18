<!-- Hallmark · pre-emit critique: P5 H5 E5 S5 R5 V5 -->

# v16.0.0 "Clarity" Phase 2 Shared Components

**Status:** implemented and verified locally

**Authority:** [`docs/plans/LOOFI_FEDORA_TWEAKS_V16_PLAN.md`](../plans/LOOFI_FEDORA_TWEAKS_V16_PLAN.md)

**Working branch:** `v16-clarity`

## Outcome

Phase 2 establishes one canonical `ui.components` library on top of the Phase 1
theme engine. It provides accessible page/content structure, presentation-only
section navigation, cards and property rows, status and workflow states, action
layout, and four explicit button roles.

The application remains `15.0.0 "Essentials"`. This phase does not replace the
live secondary tab bar, migrate destination pages, change routes, start probes,
alter system operations, or change version metadata. Shell integration and page
adoption remain Phases 3–6.

## Public component contract

| Area | Components |
| --- | --- |
| Page structure | `PageScaffold`, `PageHeader`, `ContentColumn` |
| Section presentation | `SectionItem`, `SectionNavigator` |
| Content | `Card`, `ClickableCard`, `DefinitionList`, `DefinitionRow` |
| Status and states | `StatusBadge`, `InlineNotice`, `LoadingState`, `EmptyState`, `UnavailableState`, `ActionProgress`, `DetailsDisclosure` |
| Actions | `ActionBar`, `PrimaryButton`, `SecondaryButton`, `GhostButton`, `DangerButton` |

The public package does not export legacy layout names or a generic button base.
`ui/layout_primitives.py` and `ui/shared_states.py` retain thin identity imports
for existing pages and tests, avoiding duplicate implementations during staged
adoption.

## Architecture and interaction boundaries

- `PageHeader` remains shell-owned. `PageScaffold` provides the centered,
  1120-DIP content hierarchy below it, preventing duplicate page titles.
- `SectionNavigator` consumes data-only labels, descriptions, optional textual
  status, and opaque IDs. It has explicit rail and selector modes; the Phase 3
  shell will choose the mode from the application viewport.
- `ClickableCard` supports mouse, Return, Enter, and Space activation and its
  public content API rejects nested interactive controls.
- Definition values remain wrapped and selectable; copy actions emit the value
  for caller-owned clipboard handling.
- Status badges and notices use icon, text, accessibility metadata, and semantic
  properties so color is never the only state signal.
- Buttons expose primary, secondary, ghost, and danger roles with stable
  36-by-36-DIP minimum geometry plus default, hover, focus, active, disabled,
  loading, error, and success styling.
- No component imports `core`, `services`, command runners, subprocess, or
  domain policy. Components own no timers, threads, probes, or execution.

## Development gallery

`tests/support/v16_component_gallery.py` renders the complete component family
for automated development checks. It is absent from runtime navigation, plugin
registration, and packaged product modules.

The offscreen gallery is exercised with system, dark, light, and high-contrast
themes at 100%, 125%, 140%, 150%, and 200% font scales. It includes long English
and Swedish section/property labels, both navigator modes, every button role,
all status kinds, workflow states, progress, and disclosure.

## Verification

| Gate | Result |
| --- | --- |
| Phase 2 plus Phase 1/v15 visual regression suite | 41 passed |
| Impacted MainWindow/Home/workflow UI regression suite | 549 passed; 1 existing deprecation warning |
| Component keyboard and accessibility contracts | Passed |
| Four-theme and five-font-scale gallery matrix | Passed |
| Presentation/domain import boundary | Passed |
| Focused flake8 and mypy | Passed |
| `just verify` | Passed: 7,671 tests, 40 skipped, 680 subtests; 86.24% coverage |
| Packaging manifest and wheel/sdist build | `just check-packaging` passed |
| Syntax and whitespace | `py_compile` and `git diff --check` passed |

Offscreen rendering validates widget structure, policies, accessible metadata,
semantic QSS application, and font-scale layout proxies. Live Wayland/X11,
fractional compositor scaling, AT-SPI/Orca, and human visual review remain Phase
7 release evidence as defined by the canonical plan.

## Deferred work

- Phase 3 connects `SectionNavigator` to destination, placement, route, and
  policy metadata and replaces the live secondary `QTabBar`.
- Phases 4–6 adopt the scaffold and components across Standard and Advanced
  pages and remove superseded presentation only after compatibility coverage.
- Phase 7 records real Fedora KDE responsive, keyboard, accessibility, theme,
  and compositor evidence.
- Phase 8 owns the version bump, final release gates, packaging evidence, and
  publication readiness.

No commit, push, tag, release, or remote mutation is part of this phase handoff.
