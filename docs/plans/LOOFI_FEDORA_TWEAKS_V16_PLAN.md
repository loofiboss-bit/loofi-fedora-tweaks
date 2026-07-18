# Loofi Fedora Tweaks v16.0.0 "Clarity"

## Full product review and implementation plan

**Reviewed repository:** `loofiboss-bit/loofi-fedora-tweaks`  
**Reviewed revision:** `36de3862ccb87c6c163e5c72a484be62beae6a0d` (`master`, 2026-07-18)  
**Phase 0 authority baseline:** `b96eafec85a3d7e55535201dd7459ef5c9de46b1` (`master`, 2026-07-18)

**Current release:** v15.0.0 "Essentials"  
**Proposed release:** v16.0.0 "Clarity"  
**Primary objective:** a complete, professional, responsive UI/UX redesign without changing trusted system-operation behavior.

This file is the sole v16 scope authority. The earlier review filename was
renamed during Phase 0; do not create a second v16 plan.

---

## 1. Executive verdict

Loofi Fedora Tweaks is technically much stronger than its current visual presentation suggests. v15 has a serious safety model, clear service boundaries, true lazy loading, Fedora Traditional/Atomic awareness, strong packaging automation, and an unusually large test suite. The current application can reasonably be called production-oriented at the backend and workflow level.

The visible frontend is not yet at the same level. The main problem is not merely colors or spacing. It is a mismatch between the information architecture, the shell widgets, and the styling model:

- a simplified six-destination sidebar is followed by an overloaded horizontal secondary tab bar;
- the System destination exposes too many peer sections for a single non-wrapping `QTabBar`;
- structural styling disappears when the application follows the system theme;
- several pages still use basic `QGroupBox`, form, label/value, and full-width button layouts;
- page hierarchy is duplicated between the shell and individual plugins;
- the visual tests prove widget construction and scrolling capability, but not that the resulting UI is readable, unclipped, and professionally composed.

**Overall assessment:** 7/10.  
**Technical foundation:** 9/10.  
**Safety and reliability:** 9/10.  
**Current UI/visual coherence:** 4.5/10.  
**Current information architecture:** 5.5/10.

The best v16 is therefore a design-and-consolidation release. It should add no major product features.

---

## 2. Evidence reviewed

- [README v15 product contract](https://github.com/loofiboss-bit/loofi-fedora-tweaks/blob/36de3862ccb87c6c163e5c72a484be62beae6a0d/README.md)
- [Canonical architecture](https://github.com/loofiboss-bit/loofi-fedora-tweaks/blob/36de3862ccb87c6c163e5c72a484be62beae6a0d/ARCHITECTURE.md)
- [Main window](https://github.com/loofiboss-bit/loofi-fedora-tweaks/blob/36de3862ccb87c6c163e5c72a484be62beae6a0d/loofi-fedora-tweaks/ui/main_window.py)
- [Destination definitions](https://github.com/loofiboss-bit/loofi-fedora-tweaks/blob/36de3862ccb87c6c163e5c72a484be62beae6a0d/loofi-fedora-tweaks/core/navigation/destinations.py)
- [Horizontal secondary navigation](https://github.com/loofiboss-bit/loofi-fedora-tweaks/blob/36de3862ccb87c6c163e5c72a484be62beae6a0d/loofi-fedora-tweaks/ui/navigation/destination_host.py)
- [Destination shell tests](https://github.com/loofiboss-bit/loofi-fedora-tweaks/blob/36de3862ccb87c6c163e5c72a484be62beae6a0d/tests/test_destination_shell.py)
- [Visual-system tests](https://github.com/loofiboss-bit/loofi-fedora-tweaks/blob/36de3862ccb87c6c163e5c72a484be62beae6a0d/tests/test_v15_phase8_visual_system.py)
- [Layout primitives](https://github.com/loofiboss-bit/loofi-fedora-tweaks/blob/36de3862ccb87c6c163e5c72a484be62beae6a0d/loofi-fedora-tweaks/ui/layout_primitives.py)
- [Home implementation](https://github.com/loofiboss-bit/loofi-fedora-tweaks/blob/36de3862ccb87c6c163e5c72a484be62beae6a0d/loofi-fedora-tweaks/ui/atlas_dashboard_tab.py)
- [System Information implementation](https://github.com/loofiboss-bit/loofi-fedora-tweaks/blob/36de3862ccb87c6c163e5c72a484be62beae6a0d/loofi-fedora-tweaks/ui/system_info_tab.py)
- [Theme settings and migration](https://github.com/loofiboss-bit/loofi-fedora-tweaks/blob/36de3862ccb87c6c163e5c72a484be62beae6a0d/loofi-fedora-tweaks/utils/settings.py)
- [Dark theme QSS](https://github.com/loofiboss-bit/loofi-fedora-tweaks/blob/36de3862ccb87c6c163e5c72a484be62beae6a0d/loofi-fedora-tweaks/assets/modern.qss)
- [v15 validation report](https://github.com/loofiboss-bit/loofi-fedora-tweaks/blob/36de3862ccb87c6c163e5c72a484be62beae6a0d/docs/reports/V15_PHASE8_VALIDATION.md)
- [v15 component/package decision](https://github.com/loofiboss-bit/loofi-fedora-tweaks/blob/36de3862ccb87c6c163e5c72a484be62beae6a0d/docs/reports/V15_PHASE9_PACKAGING.md)
- [CI workflow](https://github.com/loofiboss-bit/loofi-fedora-tweaks/blob/36de3862ccb87c6c163e5c72a484be62beae6a0d/.github/workflows/ci.yml)
- the two supplied v15 screenshots at 1918×1018, preserved as
  `docs/images/v16/phase0/home-system-theme.png` and
  `docs/images/v16/phase0/system-section-overflow.png`.
- [Phase 0 baseline and audit report](../reports/V16_PHASE0_BASELINE.md)
- [Phase 0 machine-readable inventory](../reports/V16_PHASE0_INVENTORY.json)
- [Phase 0 screenshot manifest](../reports/V16_PHASE0_SCREENSHOTS.json)

---

## 3. What is already strong

### 3.1 Safety and trust

- Privileged operations are separated from normal UI code and use explicit Polkit elevation.
- The project bans `sudo`, `shell=True`, unbounded subprocesses, and hardcoded package-manager behavior.
- Traditional Fedora and Atomic Fedora are treated as different capability targets.
- Action Center preserves review, planning, confirmation, execution, verification, history, expiry, and lease boundaries.
- Home and search navigate to actions but do not silently plan or execute them.

These contracts must be frozen during v16.

### 3.2 Architecture

- PyQt presentation, services, core policy, utilities, CLI, API, and daemon have documented boundaries.
- The 80 stable route IDs and 438 accepted alias keys provide a good base for a shell redesign without breaking deep links or saved state.
- Data-only plugin specifications and route-time construction are the correct direction.
- Standard and Advanced modes reduce normal-user cognitive load without weakening safety.

### 3.3 Startup and resource use

The v15 report records:

- meaningful Home median reduced from 4552 ms to about 152 ms;
- median RSS reduced by 29.2%;
- startup plugin instances reduced from 29 to 1;
- startup subprocess probes, active timers, and worker threads reduced to zero.

This is excellent and must not be traded away for visual polish.

### 3.4 Test and release engineering

- 7,600+ tests and an 85% coverage gate;
- lint, type checking, stabilization rules, dependency audit, security scan, packaging checks, RPM build, Flatpak build, and Fedora review automation;
- release evidence, checksums, SBOM/provenance, RPM smoke, and COPR publication gates.

The automation is much more mature than the UI.

---

## 4. Main findings and root causes

### P0 — Horizontal secondary navigation does not scale

`DestinationHost` uses one `QTabBar` for every section in a destination. It enables scroll buttons, disables expansion, and elides text. The System destination currently contributes sections for overview, performance, processes, hardware/power, storage, health history, troubleshooting, boot diagnostics, and recovery.

The result is visible in the screenshot: nearly every label is truncated, the active location is difficult to identify, and hidden overflow is not discoverable.

The test suite currently treats `usesScrollButtons() == True` as success. It does not assert that labels remain readable, that overflow controls are visible, or that a user can identify every destination without trial and error.

**Required correction:** replace application-level secondary tabs with a responsive section navigator. Do not attempt to solve this by shrinking fonts, reducing padding, or adding more ellipsis.

### P0 — System theme disables the component design language

New profiles default to `follow_system_theme = True`. In system mode, the application clears its stylesheet. However, Home cards, state panels, route cards, result banners, and shell surfaces depend on QSS object/property selectors for their structure and visual hierarchy.

Consequences visible in the Home screenshot:

- cards look like loose text blocks;
- nested buttons become long grey bars;
- recommendation, attention, and task hierarchy is weak;
- icons and severity states do not create a coherent visual system.

**Required correction:** always load a structural component stylesheet. “Follow system theme” must derive semantic colors from `QPalette`; it must not mean “remove the application’s layout and component styling.”

### P0 — The shell and pages duplicate hierarchy

The shell owns destination, route title, and route description. Some plugin pages also create their own page title and introduction. Home is the clearest example. The result is unnecessary vertical chrome and repeated labels such as Home/Home or System/System Info.

**Required correction:** one authoritative page scaffold. A plugin supplies content and optional header actions; the shell owns the page title, description, navigation, and content width.

### P1 — The primary sidebar becomes too wide at scaled fonts

`LayoutMetrics.sidebar_width` uses approximately 17 line heights. At larger system fonts or fractional scaling, this produces a sidebar around 400 px wide, as visible in the screenshots. Qt already works in device-independent units, so scaling width linearly from font height needs a practical upper bound.

**Required correction:** clamp the expanded sidebar to a usable range and collapse it responsively. Target 232–288 DIP, not an unbounded font-derived width.

### P1 — Pages use inconsistent and dated composition patterns

Examples:

- System Information uses a large `QGroupBox` with bold HTML labels and values spread across the full page width.
- Export controls are detached at the lower right instead of being page-header actions.
- Home cards contain a second full-width button even though the entire card is already keyboard/mouse activatable.
- Several standard and Advanced plugins still own internal `QTabWidget` navigation.
- Forms, output panes, action rows, status blocks, and empty states do not share one complete component contract.

**Required correction:** redesign around a small set of reusable components and page templates.

### P1 — The theme layer is expensive to maintain

The three QSS files are approximately 1,060–1,190 lines each and repeat broad global widget rules. This creates cascade conflicts and allows old selectors to survive long after their widgets change.

**Required correction:** one structural stylesheet plus semantic theme tokens. Scope rules to named components and dynamic properties. Avoid global `QWidget`, `QPushButton`, `QGroupBox`, and `QTabBar` rules except for a very small baseline.

### P1 — Visual validation is incomplete

The v15 “responsive matrix” instantiates `AdaptiveGrid` and four `RouteCard` widgets. It does not render the real `MainWindow`, the real System destination, or all themes at the claimed sizes. The v15 report correctly notes that live Wayland/X11, fractional scaling, Orca/AT-SPI, and automated contrast validation remain untested.

**Required correction:** make actual shell/page rendering a release gate and add a manual Fedora KDE validation record.

### P2 — Repository documentation has conflicting version history

- `docs/ROADMAP_V15.md` still describes the historical pre-renormalization v15 “Nebula”.
- the current v15 plan lives elsewhere and describes “Essentials”.
- `ROADMAP.md` contains a long mix of old v21–v49 history and the renormalized v4–v15 line.
- `main_window.py` still identifies itself as a v25 plugin-architecture file, while many source comments reference v29, v31, v38, and v47.

This is not only cosmetic. It makes agents and contributors likely to plan against obsolete product assumptions.

**Required correction:** archive legacy plans clearly, keep one canonical current roadmap, and remove historical version labels from active source comments.

### P2 — Physical extras packaging is not the next priority

v15 deferred a possible `-extras` RPM to v16, but the package analysis found 103 shared modules plus CLI/API/daemon reach into specialist code. The base RPM was only about 823 KB in the v15 report. A split currently has low user benefit and high ownership/upgrade risk.

**Decision:** do not make a physical extras split a v16 release requirement. Preserve logical isolation and lazy loading. Reconsider the split in v17 after UI consolidation reduces shared ownership.

---

## 5. v16 product direction

### Vision

Make Loofi Fedora Tweaks feel like a focused Fedora-native control center: calm, clear, consistent, safe, and usable without prior Linux expertise, while preserving power-user depth through Advanced mode and search.

### Design principles

1. One visible navigation model at each hierarchy level.
2. Full labels are preferable to hidden overflow.
3. System font and system accent are respected, but component structure remains consistent.
4. Every page has one title, one purpose, and one obvious primary action.
5. Information is grouped into cards or lists only when grouping improves comprehension.
6. Destructive or privileged actions are visually distinct and retain explicit confirmation.
7. Standard mode is designed first; Advanced mode reuses the same shell and components.
8. No new feature is accepted until the six Standard destinations are complete.

### Explicit non-goals

- no rewrite to QML, GTK, Electron, Tauri, or a web frontend;
- no custom/frameless title bar;
- no new AI, agent, marketplace, tuning, networking, or maintenance features;
- no Action Center state-machine or executable-catalog changes;
- no stable route-ID, deep-link, saved-state, CLI, API, daemon, or IPC breakage;
- no physical `-extras` or `-devel` package split;
- no font shrinking as a response to overflow;
- no heavy animation, blur, glass, or new UI dependency.

---

## 6. Target application structure

### Wide layout (recommended at 1180 DIP and above)

- Primary sidebar: 248–272 DIP, six Standard destinations plus optional Advanced.
- Secondary section rail: 208–224 DIP when a destination has multiple sections.
- Content column: centered, maximum width 1120 DIP.
- Page header: route title, concise description, optional compact actions.
- Content: responsive one-, two-, or three-column sections.

### Medium layout (900–1179 DIP)

- Primary sidebar becomes a 64–72 DIP icon rail.
- Secondary section rail remains visible when space allows.
- Full destination labels remain available as tooltips and accessible names.

### Minimum layout (860 DIP)

- Primary sidebar remains an icon rail.
- Secondary section rail becomes a full-width section selector above content.
- No standard page gains a horizontal scrollbar, except deliberately scrollable data tables.

### Navigation rules

- Replace `DestinationHost.tabs` with a `SectionNavigator` backed by the existing destination, placement, route, and policy models.
- Add explicit data-only section presentation metadata for label, icon, order,
  and default route. Do not derive section labels from the first route in a
  section, and do not replace stable route or placement identities.
- Desktop/wide: full-label vertical list with icons and optional textual status.
- Narrow: accessible combo/menu selector with full labels; no ellipsis-only entries.
- Preserve route activation, history, back/forward, search, policy explanations, lazy construction, and deep links.
- Permit content-level tabs only for genuinely related views, with a maximum of four visible choices. They must not duplicate the application section navigator.

---

## 7. Target component system

Create a small `ui/design/` and `ui/components/` layer:

### Design foundation

- `ThemeManager`: builds semantic colors from `QPalette` for system mode and from explicit dark/light/high-contrast palettes otherwise.
- `DesignTokens`: spacing, radii, minimum control sizes, content widths, elevation/border semantics, typography roles.
- `base.qss`: structural component rules always loaded.
- one small palette/token source instead of three duplicated 1,000-line stylesheets.

### Required components

- `PageScaffold`
- `PageHeader`
- `SectionNavigator`
- `ContentColumn`
- `Card` and `ClickableCard`
- `DefinitionList` / property rows
- `StatusBadge`
- `InlineNotice`
- `ActionBar`
- `PrimaryButton`, `SecondaryButton`, `GhostButton`, `DangerButton` roles
- existing loading, empty, unavailable, result, progress, and disclosure states migrated into the same contract

### Baseline visual tokens

- spacing scale: 4, 8, 12, 16, 24, 32 DIP;
- navigation row: minimum 44 DIP;
- normal control: minimum 36 DIP;
- card radius: 10 DIP;
- content max width: 1120 DIP;
- readable body line length: roughly 65–90 characters;
- system font retained;
- system highlight/accent used for selection and primary actions;
- WCAG AA text contrast target and 3:1 non-text control/focus contrast.

---

## 8. Priority page redesigns

### 8.1 Home

Target order:

1. compact status summary: health, updates, storage, recovery protection;
2. one clearly dominant recommended next step;
3. attention list with severity icon, concise text, and one compact action;
4. common tasks as icon-backed clickable cards with no redundant full-width child button;
5. recent activity behind progressive disclosure.

Rules:

- show “Home” once;
- cap common tasks to the most useful six;
- make the whole task card activatable;
- use text plus icon for severity; never color alone;
- do not add live polling or startup probes.

### 8.2 System Information

- Move the existing Export Report control into the page header/action bar.
- Do not add Refresh or Copy Summary in v16; neither action exists in the v15
  baseline, and this release does not expand System Information behavior.
- Replace the wide `QGroupBox` grid with responsive property cards:
  - Operating system: hostname, Fedora version, kernel;
  - Hardware: CPU, RAM, battery;
  - Current state: disk use and uptime.
- Keep values left-aligned near labels; do not stretch them across the complete window.
- Allow value copying through accessible actions.
- One column at minimum width, two or three columns when wide.

### 8.3 Software & Updates

- Use a consistent search/filter header.
- Separate read-only analysis from mutating actions.
- Keep install/remove/update status visible in each row.
- Place batch actions in a contextual action bar only when selections exist.
- Retain Action Center as a distinct Review/Plan/Run/Verify workflow.

### 8.4 Network & Security

- Separate current state, exposure, and changes.
- Lead with plain-language status and next step.
- Put raw ports, logs, and command details behind disclosure.
- Keep backups clearly distinguished from system recovery points.

### 8.5 Desktop

- Use previewable setting rows where feasible.
- Group appearance, displays, and window behavior consistently.
- Show current/applied state and provide reset per group.

### 8.6 Settings

- Remove the internal application-level `QTabWidget` presentation.
- Reuse the standard section navigator for Appearance, Behavior, Advanced Tools, Repair Loofi, and About.
- Keep Follow System Theme, but implement it through semantic palette tokens rather than clearing structural QSS.

### 8.7 Advanced

- Do not redesign every specialist feature from scratch before Standard is complete.
- First apply the shared shell, page scaffold, buttons, states, output panel, and form components.
- Migrate one specialist page per component pattern to prove reuse, then perform mechanical adoption.
- Keep unavailable components explicit and fail closed.

---

## 9. Phased implementation plan

### Phase 0 — Baseline, scope lock, and documentation authority

Tasks:

- Keep this canonical `docs/plans/LOOFI_FEDORA_TWEAKS_V16_PLAN.md` as the sole v16 authority.
- Record exact v15 commit/tag, startup/RSS measurements, workflow counts, and route inventory.
- Capture the six Standard destinations at 860×720, 1366×768, 1920×1080 at 100/125/140/150%, and 2560×1440 at 200% where possible.
- Inventory every `QTabWidget`, `QTabBar`, page title, root margin, broad QSS selector, hardcoded color, and full-width action button.
- Archive the obsolete `docs/ROADMAP_V15.md` as legacy pre-renormalization material.
- Reduce `ROADMAP.md` to current/future authority plus links to history.
- Remove misleading version labels from active source comments only when touched.
- Freeze route IDs, Action Center behavior, state schemas, CLI/API/daemon/IPC, and startup budgets.

Gate:

- No production behavior changed.
- Baseline evidence is committed and reproducible.
- Exactly one canonical v16 plan is named as authority.

### Phase 1 — Theme engine and design tokens

Tasks:

- Introduce semantic `ThemeManager` and `DesignTokens`.
- Split structural component styling from palette choice.
- Ensure system mode always loads structural styling derived from `QPalette`.
- Build dark, light, system, and high-contrast theme fixtures.
- Remove broad global styling where a component selector is appropriate.
- Add contrast, focus, disabled, hover, selected, warning, success, and error token tests.

Gate:

- Switching theme changes colors, not component geometry or hierarchy.
- System mode retains cards, states, navigation selection, and focus treatment.
- No global font family override.

### Phase 2 — Shared component library

Tasks:

- Implement the target components from Section 7.
- Consolidate existing `layout_primitives.py` and `shared_states.py` without parallel duplicate APIs.
- Define button roles and forbid ad-hoc full-width buttons in normal cards.
- Add component gallery/demo available only in development tests, not the shipped navigation.
- Add keyboard and accessibility tests for each interactive component.

Gate:

- Components render in all themes and supported font scales.
- Every component has accessible name/description behavior and visible focus.
- No domain or subprocess logic enters the component layer.

### Phase 3 — Application shell and responsive section navigation

Tasks:

- Decompose `MainWindow` into shell orchestration and focused navigation/header components.
- Replace the secondary `QTabBar` with `SectionNavigator`.
- Clamp primary sidebar width and correct collapse behavior.
- Replace the large `<` button with a compact semantic icon control.
- Add a visible global-search affordance with `Ctrl+K` hint.
- Hide redundant eyebrow/category text when it equals the route title.
- Preserve history, shortcuts, policy explanations, route aliases, favorites, and lazy loading.

Gate:

- Every Standard and Advanced section label is fully discoverable at 860 DIP.
- No application-level route is represented only by truncated text.
- All existing route and deep-link tests pass.
- Startup still constructs only Home and performs zero startup probes/timers/threads.

### Phase 4 — Home and System redesign

Tasks:

- Rebuild Home according to Section 8.1.
- Rebuild System Information according to Section 8.2.
- Apply the new section navigator to all System routes.
- Standardize Performance, Processes, Hardware, Storage, Health, Diagnostics, Boot, and Recovery page scaffolds.
- Remove duplicated page titles and nested application-navigation tabs.

Gate:

- Screenshot issues supplied for v15 are no longer reproducible.
- Home has one dominant recommendation and no grey full-width button bars.
- System section names remain readable without horizontal scrolling.
- System Information has no excessive label/value separation at 1920 px.

### Phase 5 — Remaining Standard destinations

Order:

1. Software & Updates
2. Network & Security
3. Desktop
4. Settings

Tasks:

- Adopt `PageScaffold`, standard cards/lists/forms, action bars, and shared states.
- Remove duplicate headers and root margins.
- Keep all safe-operation and confirmation flows unchanged.
- Verify five canonical workflows after each destination.

Gate:

- All six Standard destinations use the same shell and component contracts.
- No standard route falls back to an unstyled legacy presentation.
- Workflow decisions are no higher than v15, excluding unchanged safety confirmation.

### Phase 6 — Advanced adoption and legacy UI cleanup

Tasks:

- Apply shared primitives to Advanced pages without adding features.
- Replace internal application-navigation `QTabWidget` instances with the shared section/content model where appropriate.
- Retain local tabs only for same-context views and cap them at four.
- Delete dead selectors, duplicate theme rules, obsolete UI helpers, and compatibility presentation code proven unused.
- Fix the four known mypy findings.
- Remove stale version-number comments from touched active code.

Gate:

- Advanced uses the same visual language as Standard.
- No duplicate theme/component system remains.
- Mypy is clean.
- No plugin, CLI, API, daemon, or route contract is removed.

### Phase 7 — Real UI validation and accessibility

Automated matrix:

- actual `MainWindow`, not only isolated cards;
- system/dark/light/high-contrast;
- Standard and Advanced modes;
- 860×720, 1280×720, 1366×768, 1920×1080, 2560×1440;
- 100%, 125%, 140%, 150%, and 200% font/scale fixtures;
- long Swedish strings and English strings;
- keyboard-only navigation and visible focus;
- route labels, controls, dialogs, loading/error/empty states;
- no unintended horizontal scrolling or geometry overflow.

Manual Fedora KDE matrix:

- Wayland at 100%, 125/140%, 150%, and 200%;
- X11 at 100% and one scaled profile;
- Breeze light/dark and explicit Loofi themes;
- screen-reader smoke for navigation, page title, result state, and confirmation dialogs;
- mouse, touchpad, keyboard, and window resize behavior.

Gate:

- A signed-off screenshot catalog and validation report exists.
- Zero P0/P1 visual defects remain in Standard mode.
- Text contrast meets 4.5:1 and interactive/focus indicators meet 3:1 where applicable.

### Phase 8 — Regression, performance, packaging, and release

Tasks:

- Run full test/coverage, lint, mypy, security, dependency, stabilization, docs, packaging, Fedora review, RPM/Flatpak/sdist, and install smoke gates.
- Re-run startup benchmark on the same host and method as v15.
- Re-run five Standard workflows plus full Action Center lifecycle.
- Verify v15 settings, theme choice, navigation mode, favorites, route history, Action Center history, and state archives migrate without loss.
- Update screenshots, README, user guide, architecture, changelog, AppStream, release notes, and version metadata.
- Release only after a real Fedora KDE installed-RPM validation.

Gate:

- full suite green and coverage at least 85%;
- meaningful Home median no slower than 225 ms and no more than 20% slower than the historical 151.924 ms v15 baseline on the same host; the binding relative limit is therefore 182.309 ms;
- RSS no more than 15% above v15 on the same host;
- one startup plugin instance, zero startup subprocess probes, zero active hidden-page timers, and zero running worker threads;
- no route/state/Action Center/CLI/API/daemon/IPC compatibility regression;
- RPM and Flatpak install smoke pass;
- release screenshots match the shipped build.

---

## 10. Objective release acceptance criteria

### Navigation and layout

- Zero clipped or elided Standard section labels at the 860×720 supported minimum.
- Zero application-level horizontal tab bars with more than four peer routes.
- Zero unintended horizontal scrollbars in Standard pages.
- Exactly one visible page title per route.
- Expanded primary sidebar remains between 232 and 288 DIP.
- All interactive targets are at least 36×36 DIP; navigation rows are at least 44 DIP.

### Visual consistency

- Structural component styling is present in system, dark, light, and high-contrast modes.
- All Standard pages use the shared page scaffold, spacing tokens, button roles, notices, states, and focus treatment.
- No redundant full-width action button inside an already clickable card.
- No raw hardcoded color in migrated UI code outside the semantic theme source.

### Accessibility

- Keyboard can reach and activate every destination, section, card, action, disclosure, and dialog control.
- Focus is always visible.
- Result, severity, and availability are communicated through text/icon plus color.
- Long English and Swedish labels remain readable.
- Live screen-reader smoke is recorded for the primary workflows.

### Stability and compatibility

- v15 route IDs and aliases remain valid.
- saved theme, navigation mode, favorites, last route, Action Center history, and app-state archives remain valid.
- Action Center catalog and plan/run/verify contracts are unchanged.
- Traditional and Atomic Fedora behavior remains unchanged.
- CLI, API, daemon, IPC, and plugin interfaces remain compatible.

---

## 11. Work and commit strategy

Use a dedicated `v16-clarity` branch and one draft pull request.

Recommended commits:

1. `docs(v16): record baseline and lock redesign scope`
2. `feat(ui): add semantic theme tokens and structural styles`
3. `feat(ui): introduce shared component system`
4. `refactor(ui): replace secondary tabs with responsive section navigation`
5. `feat(ui): redesign Home and System destinations`
6. `feat(ui): redesign remaining Standard destinations`
7. `refactor(ui): adopt design system across Advanced routes`
8. `test(ui): add real shell visual and accessibility matrix`
9. `release: prepare v16.0.0 Clarity`

Rules:

- Commit after each phase gate is green.
- Do not combine shell, theme, all pages, documentation, and version bump in one commit.
- Do not bump to 16.0.0 until the final release phase.
- Keep the draft PR open for the whole release and record screenshots/measurements in it.
- Do not publish or tag from an intermediate phase.

---

## 12. Definition of done

v16 is done only when:

- the supplied v15 overflow and Home presentation defects cannot be reproduced;
- all six Standard destinations share the new shell and design system;
- Advanced is visually compatible without feature expansion;
- system theme retains professional component structure;
- live Fedora KDE Wayland validation is recorded;
- startup and safety guarantees remain within budget;
- all compatibility and release gates pass;
- documentation names one canonical current roadmap and plan;
- release screenshots come from the exact packaged release build.

---

## 13. Codex planning-mode kickoff prompt

```text
Analyze the current repository at the exact v15.0.0 release before changing anything.
Use docs/plans/LOOFI_FEDORA_TWEAKS_V16_PLAN.md as the v16 scope authority.

Implement v16.0.0 "Clarity" as a UI/UX redesign and consolidation release. Preserve all stable route IDs, lazy-loading behavior, startup budgets, Action Center contracts, state schemas, Fedora Traditional/Atomic behavior, and CLI/API/daemon/IPC compatibility.

Start with Phase 0 only. Record the real v15 baseline, inspect the supplied screenshots, inventory navigation and styling debt, reconcile the plan with current code, and produce a phase report. Do not begin Phase 1, bump the version, publish, tag, or change remote state until Phase 0 is verified.

Use small testable changes. After each phase, run the relevant focused tests plus the phase gate, report changed files, tests, measurements, unresolved risks, and deferred work, then commit the completed phase before continuing.
```
