<!-- Hallmark · pre-emit critique: P5 H5 E5 S5 R5 V4 -->

# v16.0.0 "Clarity" Phase 0 Baseline

**Status:** verified baseline and scope lock; no Phase 1 implementation

**Authority:** [`docs/plans/LOOFI_FEDORA_TWEAKS_V16_PLAN.md`](../plans/LOOFI_FEDORA_TWEAKS_V16_PLAN.md)

**Working branch:** `v16-clarity`

**Branch point:** `b96eafec85a3d7e55535201dd7459ef5c9de46b1`

**Product baseline:** annotated `v15.0.0` tag object
`04a4556073b27abb89d2d8ac440c1b05506d8a54`, peeling to
`17aa8aa78cd3ac51d1d63da336ee25d4e5e3b4c1`

## Outcome

Phase 0 records the real v15 product, locks the v16 compatibility boundary,
and adds read-only audit and screenshot evidence. The complete
`loofi-fedora-tweaks/` product tree is byte-identical to the published v15 tag.
The application remains `15.0.0 "Essentials"`; no production behavior, package
split, public API, remote state, release tag, or publication state changed.

Machine-readable evidence:

- [`V16_PHASE0_INVENTORY.json`](V16_PHASE0_INVENTORY.json) — release identity,
  environment, navigation, lazy ownership, schemas, Action Center, UI debt,
  classifications, and QSS debt.
- [`V16_PHASE0_SCREENSHOTS.json`](V16_PHASE0_SCREENSHOTS.json) — source-image
  hashes, the 78-cell capture matrix, per-frame hashes, reproduction policy,
  and contact sheets.

## Release and environment baseline

| Item | Recorded value | Decision |
| --- | --- | --- |
| Source version | `15.0.0 "Essentials"` in Python, RPM spec, and `pyproject.toml` | `KEEP`, Phase 0, critical |
| Installed base RPM | `loofi-fedora-tweaks-15.0.0-1.fc44.noarch` | `KEEP`, Phase 0, critical |
| Installed optional RPMs | API and daemon packages not installed on the capture host | `DEFER` installed-package smoke to Phase 8, medium |
| OS | Fedora Linux 44 KDE Plasma Desktop Edition, Wayland | `KEEP` supported host behavior, critical |
| Kernel | `7.1.3-201.fc44.x86_64` | Evidence only |
| Runtime | Python 3.14.6; Qt/PyQt 6.11.0; x86_64 | Evidence only |
| Product diff | Empty against `v15.0.0`; product Git trees match | `KEEP`, Phase 0, critical |
| Package decision | No physical `-extras` RPM in v16 | `DEFER` reconsideration to v17, high |

Reproduce the inventory:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=loofi-fedora-tweaks \
  python3 scripts/audit_v16_phase0.py \
  --output docs/reports/V16_PHASE0_INVENTORY.json
```

The committed inventory SHA-256 is
`49d1bb5fa16e977d433579a9e41384e77538f5dfab24ce1a3b70b6a2b536f446`.

## Startup and resource baseline

The v15 release gate remains anchored to the published same-host Phase 8
measurement. A fresh two-session run shows meaningful variance and currently
misses the strict relative gate. Phase 0 records that variance; it does not
weaken the acceptance limit.

| Measurement | Published v15 | Phase 0 planning, 20 launches | Final gate rerun, 20 launches | v16 gate |
| --- | ---: | ---: | ---: | ---: |
| Meaningful Home median | 151.924 ms | 195.871 ms | 287.838 ms | **182.309 ms maximum** (20% relative); separate 225 ms absolute limit retained |
| Meaningful Home range | — | 183.457–327.174 ms | 220.838–438.385 ms | Evidence only |
| RSS median | 76,068 KiB | 76,716 KiB | 76,374 KiB | 87,478 KiB maximum (15%) |
| RSS range | 76,040–76,148 KiB | 76,624–76,904 KiB | 76,272–76,624 KiB | Evidence only |

The planning median is 28.93% slower than the published Home baseline and 0.85%
higher in RSS. The later gate rerun is 89.46% slower than the published Home
baseline while RSS is 0.40% higher. Startup variance is an unresolved release
risk, and neither measurement changes the strict acceptance threshold. Every
10-launch batch used one warm-up, a clean temporary Standard profile, the
offscreen Qt backend, and `AtlasDashboardTab realized` as the meaningful-Home
marker.

## Frozen navigation and compatibility surface

- 80 canonical route IDs: 29 top-level and 51 subroutes.
- 438 accepted alias keys and 4 redirects.
- 7 destinations and 28 data-only lazy plugin specifications.
- Exactly one runtime plugin (`atlas_dashboard`) at meaningful Home, with zero
  subprocess probes, active timer intervals, or running worker threads.
- Action Center catalog IDs remain `dnf-clean-all`, `fstrim-all`, and
  `restart-failed-service`; plan schema 1, run schema 1, history schema 3.
- Thirteen state domains and their versions are recorded in the inventory.
- Route history, favorites, settings, state migrations, Action Center
  Review/Plan/Run/Verify/History, Traditional/Atomic behavior, CLI/JSON, API,
  daemon, D-Bus, IPC, and logical component ownership are frozen.

| Destination | Default route | Routes | Sections | Decision |
| --- | --- | ---: | ---: | --- |
| Home | `atlas_dashboard` | 1 | 1 | `ADAPT` presentation in Phase 4; keep route/lazy contract |
| Software & Updates | `software:apps` | 11 | 8 | `ADAPT` presentation in Phase 5 |
| System | `system_info` | 14 | 9 | `REPLACE` peer navigation in Phase 3; adapt page in Phase 4 |
| Network & Security | `network` | 11 | 9 | `ADAPT` presentation in Phase 5 |
| Desktop | `desktop` | 4 | 3 | `ADAPT` presentation in Phase 5 |
| Settings | `settings` | 6 | 5 | `ADAPT` presentation in Phase 5 |
| Advanced | `performance` | 33 | 12 | `DEFER` broad adoption to Phase 6 |

Section IDs remain compatibility data. Phase 3 must add explicit, data-only
section labels and descriptions. It must not derive a section label from the
first route assigned to that section.

System Information currently exposes only its existing format selector and
`Export Report` control. Phase 4 may move that control into the shared header;
it must not invent Refresh or Copy Summary actions.

## Screenshot evidence

The supplied screenshots are preserved under stable names with original bytes:

| Evidence | Dimensions | SHA-256 | Finding |
| --- | ---: | --- | --- |
| [`home-system-theme.png`](../images/v16/phase0/home-system-theme.png) | 1918×1018 | `9614465e0c9e65259a83f77d9c7d914916a98b95872eb1a64c2fb468a254a53b` | System theme loses component hierarchy; Home duplicates its title, omits task icons, and nests full-width buttons in clickable cards |
| [`system-section-overflow.png`](../images/v16/phase0/system-section-overflow.png) | 1918×1018 | `c59acd6a67232452e0e050a413c529ae54b40b0d54cf76fd8e4fb698c866cd52` | System peer sections remain unreadable and elided at a wide viewport |

The real v15 `MainWindow` was captured for all six Standard destination defaults
at 860×720, 1366×768, and 1920×1080 with 100%, 125%, 140%, and 150% application
font proxies, plus 2560×1440 at 200%: 78 frames, 78 unique hashes, and six
contact sheets. Raw frames are intentionally not committed; the manifest keeps
their stable names and hashes while compact contact sheets retain the visual
record.

- [`Home contact sheet`](../images/v16/phase0/contact-sheets/home.png)
- [`Software & Updates contact sheet`](../images/v16/phase0/contact-sheets/software_updates.png)
- [`System contact sheet`](../images/v16/phase0/contact-sheets/system.png)
- [`Network & Security contact sheet`](../images/v16/phase0/contact-sheets/network_security.png)
- [`Desktop contact sheet`](../images/v16/phase0/contact-sheets/desktop.png)
- [`Settings contact sheet`](../images/v16/phase0/contact-sheets/settings.png)

Reproduce the capture:

```bash
PYTHONPATH=loofi-fedora-tweaks QT_QPA_PLATFORM=offscreen \
  python3 scripts/capture_v16_phase0.py
```

The harness uses the real `MainWindow`, stable routes, a disposable HOME/XDG
tree, Standard mode, system theme, disabled background services, and a
fail-closed mutation guard. Application font scaling on the offscreen backend
is a deterministic **proxy**, not real desktop scaling. Live Wayland/X11
compositor and fractional-scaling coverage is explicitly deferred to Phase 7.

## UI and styling debt inventory

| Signal | Count | Classification | Target |
| --- | ---: | --- | --- |
| `QTabWidget` constructions | 16 across 14 UI files | `REPLACE` Standard; `DEFER` specialist cases | Phases 4–6 |
| Application `QTabBar` | 1 | `REPLACE` | Phase 3 |
| Page-title owner candidates | 46 | `ADAPT` | Phases 4–6 |
| Scroll-area owners | 25 | `ADAPT` | Phases 4–7 |
| Explicit `setContentsMargins` review candidates | 65 | `ADAPT` | Phases 4–6 |
| Inline `setStyleSheet` calls | 30 | `REPLACE` | Phases 1–2 |
| Direct hex/numeric `QColor` sites | 163 (at least 13 direct product-color sites were independently verified) | `REPLACE` | Phase 1 |
| Full-width action heuristic | 57 | `ADAPT` | Phases 2–6 |
| QSS lines | 3,358 | `REPLACE` incrementally | Phase 1 onward |
| Broad QSS selectors | 223 | `REPLACE` | Phase 1 |

QSS is split across 1,108 dark, 1,059 light, and 1,191 high-contrast lines.
Counts are syntax-derived review candidates, not claims that every site is a
defect. Every recorded site includes file, line, classification, target phase,
and compatibility risk in the JSON inventory.

## Ranked visual audit

| Rank | Tell | Where | Severity | Classification | Target | Safe correction |
| ---: | --- | --- | --- | --- | --- | --- |
| 1 | All themes target `QListWidget#destinationSidebar`, but the real widget is a `QTreeWidget`; an existing test asserts the wrong selector | Shell sidebar and all three QSS files | Critical | `REPLACE` | Phase 1 | Scope the structural selector to the real component and add a real-shell assertion |
| 2 | System mode clears the component stylesheet, so cards, states, selection, and hierarchy collapse | Whole shell; supplied Home screenshot | Critical | `REPLACE` | Phase 1 | Always load structural QSS and derive semantic colors from `QPalette` |
| 3 | One non-wrapping, eliding `QTabBar` presents nine System peer sections | System shell; supplied System screenshot | Critical | `REPLACE` | Phase 3 | Responsive section navigator with full labels and preserved routes |
| 4 | Shell and pages both own titles; Home visibly renders Home/Home | Home and other page-title owners | Major | `ADAPT` | Phases 2 and 4–6 | One shell-owned page scaffold; plugins provide content and optional existing actions |
| 5 | Home task icons are not rendered and clickable cards also contain redundant full-width Open buttons | Home task and recommendation cards | Major | `ADAPT` | Phase 4 | Render semantic icons and one clear activation affordance |
| 6 | Current section names can inherit the wrong first-route label | Maintenance/Updates, Settings/Desktop/Appearance, Network Privacy/Privacy | Major | `ADAPT` | Phase 3 | Explicit data-only section metadata |
| 7 | Expanded sidebar width is `max(248, line_height * 17)` with no upper clamp | Shell layout metrics | Major | `ADAPT` | Phase 3 | Clamp and responsively collapse without changing destination IDs |
| 8 | Pages mix nested scroll owners, margins, forms, output areas, and action rows | Standard pages and specialist tabs | Major | `ADAPT` | Phases 2, 4–6 | Shared page/component contracts with one intentional scroll owner |
| 9 | System Information separates labels and values excessively; export controls float at the lower edge | System Information | Major | `ADAPT` | Phase 4 | Compact facts layout and move only existing Export Report control |
| 10 | Current visual tests exercise isolated widgets and scroll-button capability, not the complete shell's readability | Visual-system and screenshot tests | Major | `REPLACE` | Phase 7 | Deterministic real-shell matrix plus live Fedora KDE validation |
| 11 | Real Wayland/X11 scaling, keyboard, AT-SPI/Orca, and deterministic compositor coverage are incomplete | Release validation | Major | `DEFER` | Phase 7 | Record installed-app manual evidence on both display stacks |

Audit summary: **3 critical · 8 major · 0 minor**. Phase 0 fixes none of these
production findings; it freezes their evidence and routes each correction to
the smallest compatible implementation phase.

## Plan reconciliation and frozen risks

- The renamed `LOOFI_FEDORA_TWEAKS_V16_PLAN.md` is the sole v16 scope authority.
- The obsolete pre-renormalization Nebula document is explicitly archived as
  legacy; the oversized historical root roadmap is also archived.
- The concise root roadmap records v15 DONE, v16 ACTIVE, and v17 future work.
- v16 workflow architecture/tasks and the active race lock now match the
  roadmap while release-doc validation still requires complete v15 release
  evidence until the deliberate Phase 8 version bump.
- All route IDs, aliases, redirects, lazy ownership, startup budgets, schemas,
  Action Center contracts, Traditional/Atomic behavior, and external execution
  surfaces are compatibility constraints, not redesign opportunities.
- A physical extras RPM is not part of v16.

Unresolved risks:

1. Current startup timing misses the historical relative gate and has a large
   outlier; later phases must recover margin without changing the gate.
2. Offscreen font scaling is only a proxy. Real Wayland/X11 and fractional
   compositor scaling remain unverified until Phase 7.
3. The API and daemon optional RPMs are not installed on this host; source and
   test compatibility are frozen now, with packaged install smoke in Phase 8.
4. Section-label metadata, structural system-theme styling, sidebar clamping,
   and the real-shell validation gap remain production debt by design.

## Phase gate

| Gate | Result |
| --- | --- |
| Phase 0 audit/capture and release-doc tests | 39 passed |
| Focused startup/navigation/migration/lazy/shell/visual/screenshot/`MainWindow` suite | 206 passed |
| Five Standard workflows | 5 passed; 0 host probes; 0 mutations |
| Fresh startup batches | 20 launches; one `atlas_dashboard` runtime plugin; 0 probes; 0 active timers; 0 worker threads; timing risk recorded above |
| `just verify` | Passed: 7,640 tests, 40 skipped, 632 subtests; 85.95% coverage; lint and mypy passed |
| `just validate-release` | Passed; normal, completed-task, and publish-ready modes passed |
| `just check-drift` | Passed; no agent-adapter drift |
| Targeted Phase 0 tooling quality | Flake8, mypy, `py_compile`, and focused tests passed |
| Screenshot evidence | 78 captures, 78 unique hashes, 6 contact sheets; supplied bytes and dimensions verified |
| Version/product identity | `15.0.0 "Essentials"`; product tree `de1d89a5e3a4accee6d8d9d46999411b52376a1b` matches `v15.0.0` |
| Final whitespace/diff review | `git diff --check` and staged-diff review passed immediately before commit |

Phase 0's documentation/evidence gate is green. The startup acceptance gate is
not waived: it remains an explicit unresolved risk for subsequent implementation
phases and must pass before v16 release. Phase 1 remains blocked until this
report is committed locally.

## Changed files

- Authority and history: `ROADMAP.md`, `docs/README.md`, the canonical v16 plan,
  and two explicitly named roadmap archives.
- Workflow contract: v16 architecture/tasks, active race lock, release-doc
  validator, and its focused tests.
- Reproducible evidence: Phase 0 audit/capture scripts, focused tests, two JSON
  reports, two byte-preserved references, and six contact sheets.
- Product code: **none**.

## Deferred work

All production changes are deferred. Theme/tokens start in Phase 1 only after
this report is verified and committed. Shared components, shell, destination
redesign, Advanced cleanup, live accessibility/scaling, packaging, the version
bump, and publication remain Phases 2–8. Extras packaging remains a v17
decision.
