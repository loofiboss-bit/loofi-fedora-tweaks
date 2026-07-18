# v16.0.0 "Clarity" Phase 7 UI and Accessibility Validation

**Status:** implemented and verified locally

**Authority:** [`docs/plans/LOOFI_FEDORA_TWEAKS_V16_PLAN.md`](../plans/LOOFI_FEDORA_TWEAKS_V16_PLAN.md)

**Working branch:** `v16-clarity`

## Outcome

Phase 7 validates the real `MainWindow` across the complete responsive, theme,
mode, font-scale, and English copy matrix. The application is now English-only:
runtime locale loading and the Swedish catalog are removed, while an extended
English fixture continues to stress long-label layouts.

The validation found and fixed two release-blocking overflow classes. Shared
page layouts now shrink before adaptive grids reflow, and the Profiles action
row uses the responsive grid contract instead of a fixed horizontal row. The
application page wrapper and Profiles page explicitly reject horizontal
scrolling. No Standard destination has a remaining P0 or P1 UI defect in the
Phase 7 evidence.

## Accessibility and input contract

- `MainWindow`, its navigation, breadcrumb, live result state, global search,
  and confirmation dialog expose stable accessible names and descriptions.
- The live AT-SPI smoke test resolves the session accessibility bus and
  validates the application, navigation, page title, result state, and
  confirmation surfaces in a 282-node real application tree.
- Keyboard traversal, visible focus, Escape dismissal, mouse activation,
  wheel/touchpad-equivalent navigation, and live resize behavior pass.
- Every semantic palette passes the WCAG-aligned 4.5:1 text and 3:1 interactive
  focus minimums used by the release contract.

## Deterministic matrix

The automated renderer covers the full Cartesian product through the real
`MainWindow`:

| Axis | Values |
| --- | --- |
| Themes | system, dark, light, high contrast |
| Modes | Standard, Advanced |
| Viewports | 860x720, 1280x720, 1366x768, 1920x1080, 2560x1440 |
| Font scales | 100%, 125%, 140%, 150%, 200% |
| Copy fixtures | English, extended English |

All 400 automated cells pass. The signed visual catalog retains 24
representative frames and eight contact sheets, covering every axis and every
Standard destination. The catalog is stored under
[`docs/images/v16/phase7/contact-sheets`](../images/v16/phase7/contact-sheets/).

## Live Fedora KDE evidence

| Backend | Scale | Result | Environment |
| --- | ---: | ---: | --- |
| Wayland | 100% | 40/40 | Isolated nested KWin Wayland compositor |
| Wayland | 125% | 40/40 | Isolated nested KWin Wayland compositor |
| Wayland | 140% | 40/40 | Current physical Fedora KDE Wayland session |
| Wayland | 150% | 40/40 | Isolated nested KWin Wayland compositor |
| Wayland | 200% | 40/40 | Isolated nested KWin Wayland compositor |
| X11 (`xcb`) | 100% | 40/40 | Current KDE XWayland server |
| X11 (`xcb`) | 150% | 40/40 | Current KDE XWayland server |

The X11 protocol and Qt `xcb` path are exercised through XWayland because the
available workstation session is Wayland; this is not evidence from a native
Plasma X11 login. The limitation is explicit rather than inferred as native
session coverage. No physical display setting or user preference was changed.

## Evidence

- [`V16_PHASE7_AUTOMATED.json`](V16_PHASE7_AUTOMATED.json) — 400-cell complete matrix
- [`V16_PHASE7_CATALOG.json`](V16_PHASE7_CATALOG.json) — 24-frame visual catalog and eight contact sheets
- [`V16_PHASE7_ATSPI.json`](V16_PHASE7_ATSPI.json) — live 282-node accessibility tree
- `V16_PHASE7_WAYLAND_{100,125,140,150,200}.json` — live Wayland scale runs
- `V16_PHASE7_X11_{100,150}.json` — live Qt `xcb` runs

Every harness run uses temporary HOME/XDG roots, disables background services,
rejects asynchronous commands, and blocks mutating subprocesses.

## Verification

| Gate | Result |
| --- | --- |
| `just verify` | Passed |
| Full test suite | 7,722 passed, 40 skipped, 851 subtests |
| Coverage | 86.48% (85% required) |
| `python3 scripts/validate_v16_phase7_ui.py --scope contract --json` | Passed; 400 required automated cells and 24 required catalog frames |
| Automated real-shell matrix | 400/400 passed |
| Visual catalog | 24/24 frames and 8/8 contact sheets passed |
| Live Wayland matrix | 200/200 passed across five compositor scales |
| Live Qt `xcb` matrix | 80/80 passed across two scales |
| Live AT-SPI smoke test | Passed; 282 nodes and all required surfaces present |
| English-only runtime and fixtures | Passed |
| `git diff --check` | Passed |

## Deferred work

Phase 8 owns the full regression, startup/resource, Traditional/Atomic,
packaging, release-evidence, security, version-bump, and publication gates.
Phase 7 does not change the current `15.0.0 "Essentials"` package version.

No commit, push, tag, release, or remote mutation is part of this phase.
