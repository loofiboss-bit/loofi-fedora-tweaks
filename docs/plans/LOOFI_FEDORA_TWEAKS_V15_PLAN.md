---
title: Loofi Fedora Tweaks v15.0.0 "Essentials"
version: 15.0.0
codename: Essentials
revision: 2
status: PLANNED
release_type: Product simplification, UX architecture, and startup-efficiency release
created: 2026-07-17
revised: 2026-07-17
owner: Loofi Fedora Tweaks
reviewed_against_release: v14.0.0 "Helm"
reviewed_against_tag_commit: 4f0c09174e0c1a7abe0e09f810795ea2f8d3a830
reviewed_against_master_commit: fe774cfa9f0916a9214a42a3c1125a26680e0351
primary_goal: Make Loofi Fedora Tweaks substantially simpler, faster, and more logical for end users while preserving the verified-maintenance, state-integrity, Fedora, CLI, API, daemon, and release contracts completed in v14.
---

# Loofi Fedora Tweaks v15.0.0 "Essentials"

> Revision 2 supersedes the earlier v15 draft. It has been reconciled against the
> live v14.0.0 "Helm" release and the post-release `master` state listed above.

## 1. Executive decision

v15.0.0 is a **subtraction, consolidation, and startup-architecture release**.

The application already has strong safety, recovery, diagnostics, Fedora variant
handling, stable route IDs, CLI/API/daemon compatibility, and a mature verified
maintenance lifecycle. The remaining product problem is not lack of capability.
It is that too many pages, labels, navigation surfaces, dashboards, startup tasks,
and specialist features compete for the user's attention.

v15 must improve the default product without weakening v14.

The release must deliver:

1. One canonical Home experience.
2. Six standard sidebar destinations.
3. One centralized navigation and visibility policy.
4. One global route/action search surface.
5. Standard and Advanced modes instead of three exposed experience levels.
6. True top-level lazy loading and reduced startup work.
7. Five polished end-to-end user workflows.
8. A simpler shell with conditional activity UI and fewer permanent controls.
9. Safe migrations for saved routes, favorites, settings, and existing users.
10. Measured startup, memory, navigation, and workflow improvements.
11. Full preservation of v14 Action Center, state, release-lineage, CLI, API,
    daemon, and Fedora safety contracts.

**No new major feature area is allowed in v15.**

---

## 2. Verified v14 baseline

### 2.1 Baseline authority

Implementation starts from the current post-release `master` state:

```text
master: fe774cfa9f0916a9214a42a3c1125a26680e0351
release: v14.0.0 "Helm"
tag baseline: 4f0c09174e0c1a7abe0e09f810795ea2f8d3a830
```

The two commits after the release tag are release-workflow/documentation closure
changes, not a new product feature baseline. Codex must still verify the actual
HEAD before implementation and record it in the Phase 0 report.

### 2.2 What v14 completed and v15 must preserve

v14 completed the following contracts:

- Durable `ActionDefinition`, `ActionPlan`, `ActionRun`, and `PolicyDecision`
  models.
- Expiring Action Center plans with fresh re-preflight before execution.
- Explicit confirmation and separate verification before success.
- Cross-process single-mutation lease behavior.
- Interrupted-run preservation without automatic retry or resume.
- A deny-by-default executable catalog limited to:
  - `dnf-clean-all`
  - `restart-failed-service`
  - `fstrim-all`
- Manual-only behavior for all other recommendations.
- Action Center GUI Review/Plan/Run/Verify/History flow.
- Compatible CLI, read-only API, support-bundle, route, settings, and state
  behavior.
- Schema-aware State Doctor checks and snapshot-consistent backup/restore.
- Collector lease and observability convergence.
- Exact release source/tag/artifact/COPR lineage and public readback gates.
- Fedora 44 as the supported target and Fedora 45 as preview/advisory.
- An 85% release coverage floor.

### 2.3 What v14 did not solve

The following remain valid v15 targets:

- Two independently maintained Home/dashboard experiences.
- A tree sidebar containing many child pages in the default experience.
- Beginner, Intermediate, and Advanced visibility systems.
- Separate sidebar search, command palette, and quick-action surfaces.
- Eager import and construction of all built-in top-level plugins.
- Unconditional startup initialization of Pulse, tray, dependency checks,
  notification UI, and status timers.
- A fixed-size multi-step first-run wizard.
- Duplicate version/footer/status chrome.
- Broad base-RPM ownership of the complete application tree.
- Specialist features present in the core runtime even when hidden.
- Accumulated QSS, emoji labels, fixed sizing, and inconsistent feedback states.

### 2.4 v14 reconciliation matrix

| Area | Classification | v15 decision |
| --- | --- | --- |
| Action Center contracts/orchestrator/stores | `KEEP` | Do not rewrite, rename internally, or bypass. |
| Action Center GUI route | `KEEP + ADAPT` | Keep `maintenance:action-center`; improve placement and entry points only. |
| Executable action catalog | `KEEP` | Do not add new executable definitions in this release. |
| Action confirmation/verification/lease rules | `KEEP` | Treat as non-negotiable release invariants. |
| Maintenance sub-tab lazy factories | `KEEP` | Reuse as the reference pattern for deferred subpage construction. |
| State Doctor and app-state archive formats | `KEEP + ADAPT UI` | Rename presentation to Repair Loofi; preserve schemas and service contracts. |
| Observability and health snapshots | `KEEP` | Compose into Home/System Health; do not create another store. |
| Route IDs and compatibility aliases | `KEEP` | Add destination mapping; do not replace all canonical IDs. |
| Five-area tree shell | `DELETE/REPLACE` | Replace default shell with six flat destinations. |
| Atlas Home + Live Overview duplication | `MERGE` | Keep one Home implementation and one compatibility redirect. |
| Sidebar search + palette + quick actions | `MERGE` | One policy-backed search/action model. |
| Top-level plugin loading | `ADAPT/BUILD` | Introduce data-only specs and instantiate on activation. |
| First-run wizard | `DELETE/REPLACE` | Replace with a short responsive welcome surface. |
| QSS/theme layer | `ADAPT` | Reduce global overrides; follow system defaults. |
| Existing API/daemon subpackages | `KEEP` | Do not disturb their package boundaries. |
| New `-extras` RPM | `CONDITIONAL` | Go/no-go after lazy-loading/component-boundary evidence. |
| New `-devel` RPM | `DEFER` | Not required for v15. |
| Release lineage and Fedora review gates | `KEEP` | Inherit v14 gates exactly and extend only where needed. |

---

## 3. Non-negotiable v14 invariants

The following may not regress during v15:

1. `maintenance:action-center` remains resolvable.
2. Action Center execution remains plan-based and deny-by-default.
3. Home, search, and deep links may navigate to Action Center, but may not
   execute an action or silently create/apply a plan.
4. Exit code zero alone never means an Action Center run succeeded.
5. Plans expire and are re-preflighted before execution.
6. Medium-risk actions without rollback require explicit acknowledgement.
7. Interrupted runs remain inspectable and never auto-resume.
8. Only one Action Center mutation may run across GUI/CLI processes.
9. The remote API remains non-mutating unless a separate future release changes
   that contract explicitly.
10. Plugin or AI content may not provide executable Action Center commands.
11. State Doctor, backup, restore planning, and state schemas remain compatible.
12. Traditional and Atomic Fedora behavior remains capability-aware.
13. `pkexec`, command allowlists, list-based vectors, timeouts, and audit metadata
    remain enforced.
14. CLI JSON envelopes and supported command names remain compatible.
15. Support-bundle privacy/redaction remains intact.
16. Coverage remains at or above 85%.
17. Exact release lineage, Fedora review, RPM/COPR, and public readback gates remain
    blocking.

---

## 4. Product principles

All implementation decisions follow these principles, in order:

1. The next useful action must be obvious.
2. Standard mode must be sufficient for normal Fedora desktop maintenance.
3. Advanced capability remains available without dominating the default UI.
4. One concept gets one user-facing name and one primary location.
5. One workflow gets one preferred entry point.
6. Read-only inspection comes before mutation.
7. Existing v14 action safety is reused, not reproduced in UI code.
8. Unavailable functionality is hidden or clearly explained.
9. Startup work is limited to what is required to display Home.
10. Compatibility is preserved through mappings and adapters, not duplicate visible
    pages.
11. No remote analytics or telemetry is added.
12. Success is measured by reduced complexity and task completion, not feature
    count.

---

## 5. Non-goals

The following are explicitly out of scope:

- Rewriting PyQt6 to QML, GTK, Electron, Tauri, or a web frontend.
- Replacing the v14 Action Center orchestrator, contracts, stores, or policy model.
- Expanding the Action Center executable catalog beyond its three v14 actions.
- Adding fix-all, autonomous repair, automatic rollback, automatic retry, or
  automatic plan execution.
- Adding remote API mutation.
- New AI providers, agents, marketplaces, mesh capabilities, virtualization
  capabilities, or automation engines.
- New top-level feature tabs.
- Breaking stable route IDs to obtain cleaner names.
- Replacing trusted service/core backends solely because their current UI is
  confusing.
- Removing CLI, daemon, Web API, state recovery, support bundles, history, undo,
  or Atomic support.
- Lowering coverage, Fedora review, packaging, security, or release gates.
- Making `loofi-fedora-tweaks-extras` mandatory for the standard experience.
- Creating a `loofi-fedora-tweaks-devel` package in v15.

---

## 6. Success metrics

Phase 0 records reproducible v14 measurements. Final validation uses the same
machine, launch method, profile state, and measurement commands.

### 6.1 Product complexity targets

- Standard sidebar contains exactly six primary destinations.
- Advanced mode may add one `Advanced` destination.
- There is exactly one visible Home.
- There is exactly one global route/action search surface.
- The user-facing mode selector contains only Standard and Advanced.
- No separate top-level rows exist in Standard mode for System Info, Monitor,
  Hardware, Storage, Health, Diagnostics, Backup, Profiles, Gaming, Development,
  Virtualization, AI Lab, Agents, Automation, Mesh, Teleport, Community, or
  Marketplace.
- Home displays at most:
  - one primary recommendation,
  - three attention items,
  - four common task shortcuts,
  - one recent-change/undo section when relevant.
- Version/build data appears under About and the window title, not duplicated in
  sidebar and status footer.
- Idle status/activity chrome is hidden.

### 6.2 Performance targets

Measure at least ten clean launches and report median plus range.

- Improve first meaningful Home render by at least 25% against v14.
- If v14 is already below 1.0 second, require no regression and at least 10% less
  startup CPU work or imported UI-module count.
- Reduce initial RSS by at least 15%, or document why the current baseline is
  already low and show no regression.
- Startup imports only shell, Home, navigation contracts, settings, and required
  platform-detection modules.
- Specialist UI modules remain absent from `sys.modules` until activation.
- No Home-owned 2-second polling timer runs.
- Page-specific timers/workers stop or suspend while their page is hidden when
  technically safe.

### 6.3 Workflow targets

- System update: no more than three user decisions before reviewed execution.
- Application install: no more than three decisions from Applications.
- Slow-system diagnosis: one guided entry point with a plain-language summary.
- Disk cleanup: analysis and reclaim preview before confirmation.
- Protection/recovery: backup, recovery points, rollback guidance, support export,
  and Loofi app-state repair are visibly distinct.
- Action Center: one clear path to Review/Plan/Run/Verify/History, with no duplicate
  planner UI elsewhere.

### 6.4 Quality targets

- Overall coverage remains at least 85%.
- New/changed navigation, migration, Home, and plugin-spec modules target at least
  90% branch coverage.
- All v14 Action Center and state regression suites pass unchanged unless a test
  is deliberately adapted to a moved UI entry point.
- Core-only runtime smoke passes when optional specialist components are absent.
- Upgrade smoke from v14 preserves settings, favorites, history, action plans/runs,
  and supported state.
- No unresolved critical accessibility issue remains in standard workflows.
- Canonical screenshots are regenerated from the real v15 application.

---

## 7. Target information architecture

### 7.1 Standard destinations

The default sidebar is flat and contains exactly:

1. **Home**
2. **Software & Updates**
3. **System**
4. **Network & Security**
5. **Desktop**
6. **Settings**

When Advanced mode is active, one additional destination may appear:

7. **Advanced**

These are shell destination IDs, not replacements for every existing route ID.

Suggested destination IDs:

```text
home
software_updates
system
network_security
desktop
settings
advanced
```

### 7.2 Route strategy

Do not create a parallel replacement route namespace for all existing pages.

- Existing plugin and subroute IDs remain canonical wherever possible.
- A new destination/section mapping groups existing routes into the six-destination
  shell.
- Current aliases, favorites, CLI references, and deep links continue to resolve.
- Only genuinely duplicate implementations may redirect to another route.

Examples:

| Existing route | v15 destination | v15 presentation |
| --- | --- | --- |
| `atlas_dashboard` | Home | Canonical Home implementation. |
| `dashboard` | System | Compatibility route to System Overview; no second Home. |
| `software:apps` | Software & Updates | Applications section. |
| `software:repos` | Software & Updates | Repositories section. |
| `maintenance:updates` | Software & Updates | Updates section. |
| `maintenance:cleanup` | Software & Updates | Cleanup section. |
| `maintenance:smart-updates` | Software & Updates | Advanced update options, not a competing workflow. |
| `maintenance:action-center` | Software & Updates | Action Center remains a dedicated section. |
| `maintenance:health-timeline` | System | System Health > History. |
| `maintenance:upgrade-assistant` | Software & Updates | Fedora Upgrade section. |
| `system_info` | System | Overview/details. |
| `monitor` and its subroutes | System | Performance & Processes. |
| `hardware` | System | Hardware & Power. |
| `storage` | System | Storage. |
| `health` | System | System Health. |
| `diagnostics` | System | Troubleshooting. |
| `snapshots` | System | Recovery Points. |
| `network` | Network & Security | Connections/DNS/privacy. |
| `security` | Network & Security | Security findings/firewall/exposure. |
| `backup` | Network & Security | Backups. |
| `desktop` | Desktop | Appearance/displays/windows. |
| `settings` | Settings | App settings, Repair Loofi, About. |
| specialist routes | Advanced | Only when policy and component availability allow. |

### 7.3 Secondary navigation

Every destination uses one shared secondary-navigation model.

Requirements:

- Stable route IDs.
- Keyboard navigation.
- Clear selected state.
- Narrow-width overflow handling.
- Capability-aware hiding.
- No nested tabs inside nested tabs where a simple section list is sufficient.
- A page may keep internal tabs temporarily when replacing them creates excessive
  regression risk, but the exception must be documented and tested.

---

## 8. Navigation and visibility architecture

### 8.1 Destination model

Introduce a PyQt-free destination mapping, for example:

- `core/navigation/destinations.py`
- `core/navigation/policy.py`
- `core/navigation/migrations.py`
- `core/navigation/models.py`

A destination references existing route IDs instead of replacing them.

Example:

```python
@dataclass(frozen=True)
class Destination:
    id: str
    label: str
    icon: str
    default_route_id: str
    route_ids: tuple[str, ...]
    advanced_only: bool = False
```

### 8.2 NavigationPolicy

One pure policy contract must serve:

- primary sidebar,
- secondary navigation,
- global search,
- action-filtered search,
- Home links,
- favorites/pins,
- recent routes,
- internal deep links,
- restored last route,
- screenshot routing,
- documentation route validation.

Required inputs:

- requested route,
- Standard or Advanced mode,
- installed component set,
- Fedora variant/capabilities,
- plugin compatibility,
- route metadata/risk,
- favorite/pin state.

Required outcomes:

```python
class NavigationDecision(Enum):
    VISIBLE = "visible"
    HIDDEN = "hidden"
    GATED = "gated"
    UNAVAILABLE = "unavailable"
```

The result also includes:

- human-readable reason,
- required mode,
- required component/package,
- fallback route,
- search visibility,
- direct-link behavior.

### 8.3 Policy rules

- Standard mode never leaks advanced-only results through search or favorites.
- Favorites do not bypass missing components or incompatibility.
- Atomic-only options remain hidden on Traditional Fedora and vice versa.
- A gated deep link shows a compact explanation and safe next step.
- Direct navigation never executes a mutating action.
- `maintenance:action-center` remains visible where appropriate in Standard mode;
  safety comes from the v14 plan lifecycle, not by hiding the page.
- Policy evaluation remains PyQt-free and deterministic.

### 8.4 Saved-state migration

Migrate or adapt:

- last active route,
- favorites/pinned routes,
- experience level,
- quick-action configuration,
- stored sidebar expansion/collapse state,
- first-run sentinel,
- route references in recent UI state.

Mode mapping:

```text
beginner     -> standard
intermediate -> advanced
advanced     -> advanced
missing/bad  -> standard
```

The migration must be idempotent. Intermediate-to-Advanced behavior must be
explicitly covered by tests and release notes because it may expose additional
specialist routes.

Do not migrate Action Center plan/run/state records into a new format unless the
v14 service layer requires a schema migration for an independent reason.

---

## 9. One canonical Home

### 9.1 Canonical identity

- Keep `atlas_dashboard` as the canonical Home route/plugin identity unless Phase
  0 proves a safer compatibility strategy.
- Replace its current implementation with the final v15 Home experience.
- Retire the independent `DashboardTab` implementation as a second Home.
- Preserve the `dashboard` route as a compatibility route to System Overview or a
  small compatibility adapter.
- Do not maintain two full Home widgets behind aliases.

### 9.2 Home data contract

Create a PyQt-free composition service:

- `core/home/models.py`
- `core/home/service.py`
- `core/home/recommendations.py`

Example:

```python
@dataclass(frozen=True)
class HomeSummary:
    overall_state: Literal["good", "attention", "critical", "unknown"]
    summary: str
    generated_at: datetime
    primary_recommendation: Recommendation | None
    attention_items: tuple[AttentionItem, ...]
    common_tasks: tuple[HomeTask, ...]
    recent_change: RecentChange | None
```

Compose existing trusted services:

- observability/health snapshots,
- update state,
- storage pressure,
- backup/recovery status,
- Action Center candidate/plan/run status,
- history/undo state.

Do not create duplicate stores or diagnostic engines.

### 9.3 Recommendation order

1. Critical state-integrity or corruption finding.
2. Interrupted/failed Action Center run requiring review.
3. Pending reboot required to complete an existing operation.
4. Critical disk pressure.
5. Failed update or incomplete recovery state.
6. Important pending updates.
7. Stale/missing backup or recovery protection.
8. Repeated health issue.
9. Ready Action Center plan requiring explicit user review.
10. No action required.

### 9.4 Action Center behavior on Home

Home may show:

- a count of reviewable/manual Action Center candidates,
- interrupted or verification-failed run status,
- a link to `maintenance:action-center`,
- a concise explanation of why review is recommended.

Home may not:

- create a plan automatically,
- apply a plan,
- execute a command,
- mark a run successful,
- duplicate the full Action Center planner UI.

### 9.5 Remove from Home

- live process table,
- live CPU/RAM sparkline grid,
- full mount-point storage list,
- configurable eight-button quick-action grid,
- duplicate Recent Actions and Recent Changes cards,
- focus-mode control unless Phase 0 proves it is a core workflow,
- release codename as the primary page title,
- duplicate Upgrade/Health/Action Center cards when one recommendation can express
  the next useful step.

Detailed live data moves to System.

---

## 10. Action Center integration rules

v14 makes Action Center a core product contract. v15 improves its discoverability
and presentation without replacing it.

### 10.1 Required placement

- Keep `maintenance:action-center` as a dedicated route.
- Present it under Software & Updates, inside the Maintenance/Review area.
- Link to it contextually from Home, Troubleshooting, Updates, and Storage only
  when relevant.
- Keep Review/Plan/Run/Verify/History together.

### 10.2 Required implementation reuse

Preserve:

- `core/actions/contracts.py`
- `core/actions/catalog.py`
- `core/actions/orchestrator.py`
- `core/actions/stores.py`
- `core/actions/center.py`
- `CommandFacade`/`CommandRunner` boundaries
- v14 asynchronous operation worker behavior
- separate verification UI
- plan/run history
- v14 CLI/API/support contracts

### 10.3 Catalog boundary

No new executable action definition is required for v15.

- DNF cache cleanup and supported SSD trim may be reached from the cleanup/storage
  workflow through their v14 Action Center definitions.
- Failed-service repair may be reached from Troubleshooting through
  `restart-failed-service`.
- Journal vacuum, autoremove, RPM database repair, update scheduling, snapshots,
  and other operations do not automatically become Action Center definitions in
  this release.
- Existing non-Action-Center operations retain their current safety path until a
  separately reviewed future migration.

### 10.4 UI adaptation allowed

Allowed:

- clearer grouped details,
- responsive button layout,
- shared loading/result states,
- contextual preselection of a candidate,
- better empty/manual-only explanations,
- destination/section relocation,
- removing duplicate headers created by the new shell.

Not allowed:

- bypassing plan creation,
- combining Run and Verify into one success step,
- executing directly from search/Home,
- changing expiry/lease semantics,
- weakening manual-only policy,
- exposing remote mutation.

---

## 11. Five core end-to-end workflows

### 11.1 Update the system

Preferred entry points:

- Home recommendation when updates matter.
- Software & Updates > Updates.

Flow:

1. Read current update state.
2. Group system, Flatpak, and firmware updates.
3. Explain Traditional/Atomic behavior and reboot expectations.
4. Preview selected work.
5. Confirm privileged execution.
6. Run with progress.
7. Verify the result.
8. Show reboot/rollback guidance only when applicable.

`Smart Updates` becomes an Advanced Options section inside Updates. Do not delete
its backend before all scheduling/conflict/rollback behavior is mapped and tested.
Action Center remains separate because it covers maintenance beyond package
updates.

### 11.2 Install an application

Preferred entry point:

- Software & Updates > Applications.

Requirements:

- one search field,
- source shown clearly,
- installed state visible,
- one primary install/remove action,
- repository enablement explained before mutation,
- actionable missing-source/dependency state,
- summarized result with raw output under Details.

### 11.3 Diagnose a slow system

Preferred entry points:

- Home common task,
- System > Performance & Processes.

Flow:

1. Capture a bounded read-only snapshot.
2. Summarize CPU, memory, storage pressure, top processes, failed services, and
   recent recurring signals.
3. Explain the most likely bottleneck in plain language.
4. Offer safe next steps.
5. If a currently failed service matches v14 policy, link to Action Center with
   that exact unit preselected.
6. Keep termination/tuning controls behind confirmation or Advanced mode.

No AI diagnosis dependency is added.

### 11.4 Free disk space

Preferred entry points:

- Home when disk pressure exists,
- System > Storage,
- Software & Updates > Cleanup.

Flow:

1. Analyze reclaimable categories.
2. Show estimated size and risk.
3. Select safe categories by default.
4. Preview actions.
5. Confirm cleanup.
6. Verify reclaimed space.
7. Show remaining pressure and next safe step.

Use existing v14 Action Center definitions for `dnf-clean-all` and `fstrim-all`
when those operations are selected. Do not combine snapshot/recovery-point deletion
with ordinary cache cleanup.

### 11.5 Protect or recover the system

Preferred entry points:

- Network & Security > Backups,
- System > Recovery Points,
- Settings > Repair Loofi.

The UI must distinguish:

- user/system backup,
- recovery point/snapshot,
- rollback guidance,
- Action Center recovery guidance,
- Loofi application-state backup/restore,
- support bundle/export.

`Repair Loofi` is a presentation and navigation change. It must reuse v14 State
Doctor and archive services without changing their schemas unnecessarily.

---

## 12. True top-level lazy loading

### 12.1 Preserve the v14 sub-tab pattern

Maintenance already stores sub-tab factories, creates placeholders, and
instantiates a sub-tab on first visit. Keep this behavior and use it as a reference
pattern.

Do not replace a working deferred sub-tab implementation solely to introduce a
new abstraction.

### 12.2 Eliminate eager top-level plugin construction

Current top-level loading imports every built-in UI module and constructs every
plugin class before wrapping it in `LazyWidget`. v15 must replace that behavior.

Introduce a data-only specification:

```python
@dataclass(frozen=True)
class PluginSpec:
    id: str
    name: str
    description: str
    icon: str
    destination_id: str
    module: str
    class_name: str
    component: str
    visibility: Literal["standard", "advanced"]
    compat: CompatibilitySpec
```

The registry stores specifications separately from runtime instances.

### 12.3 Required loading flow

1. Load data-only built-in specs.
2. Load installed optional component specs, if supported.
3. Build destination and route models.
4. Apply NavigationPolicy.
5. Render shell and canonical Home host.
6. Import and construct a plugin only when its route is first activated.
7. Cache the valid instance.
8. Stop/suspend page-owned timers/workers while hidden when safe.

### 12.4 Constructor rules

Plugin constructors must not:

- execute subprocesses,
- perform broad filesystem scans,
- query package databases,
- start timers/threads,
- create tray icons,
- initialize network clients,
- mutate settings,
- run expensive compatibility checks.

Heavy work belongs in explicit first-show/async load methods.

### 12.5 Startup deferrals

Audit and defer or conditionally initialize:

- Pulse listener,
- tray icon,
- dependency checks,
- notification panel/bell,
- status refresh timer,
- update checks,
- external plugin/marketplace scans,
- nonessential background collectors.

Tray creation must be conditional on tray/background settings.

### 12.6 Required tests

- Specialist UI modules absent from `sys.modules` after shell startup.
- Activating a route imports only the required plugin module.
- Reopening a route reuses its instance.
- Import failure yields a useful page-level error.
- Missing optional components do not break startup.
- Maintenance sub-tab lazy behavior remains intact.
- Action Center is not constructed until its subroute is opened.
- Timers/workers obey visibility lifecycle.
- Legacy routes trigger correct deferred activation.

---

## 13. Application shell simplification

### 13.1 Sidebar

Replace the default expandable tree with a flat destination list.

Requirements:

- six standard rows,
- optional Advanced row,
- stable destination IDs,
- clear expanded/collapsed state,
- icon-only collapsed mode with tooltips,
- keyboard focus and navigation,
- no Favorites category,
- no version footer,
- collapse action integrated into compact sidebar chrome.

Favorites remain stored but appear in Home/global search rather than as a second
navigation tree.

### 13.2 Shared secondary navigation

A destination host displays its mapped routes using one shared component.
Do not duplicate tab/section logic per feature.

The host must:

- activate current stable routes,
- support deferred plugin construction,
- show unavailable/gated explanations,
- maintain history/back behavior,
- work at narrow widths.

### 13.3 One global search/action surface

Unify:

- sidebar filtering,
- command palette,
- quick-action dialog/grid.

Behavior:

- `Ctrl+K`: global route/settings search.
- `Ctrl+Shift+K`: same surface filtered to safe actions.
- Results obey NavigationPolicy.
- Results show destination and short explanation.
- Risky/mutating actions navigate to their normal preview workflow.
- Action Center actions open `maintenance:action-center`; they never run directly.
- Existing configured quick actions migrate to pins/suggestions when meaningful.

### 13.4 Header and activity

Use one page header containing:

- destination/section context,
- page title,
- one short description when useful,
- contextual actions on the right.

Replace the permanent footer with conditional activity UI shown only for:

- running work,
- success/failure result,
- cancellation when safe,
- valid undo.

Remove permanent shortcut hints and duplicate version labels.

### 13.5 Notifications

Remove the permanent notification bell unless Phase 0 proves unique, actionable
value not represented on Home or desktop notifications.

Do not remove backend notification support when it has a validated use case.

### 13.6 Remove no-op shell settings

Retire the frameless-window flag/stub unless it becomes a fully supported feature.
No user-facing setting may remain when it has no effect.

---

## 14. Standard and Advanced modes

### 14.1 Mode contract

Replace the exposed three-tier selector with:

```text
ui_mode = standard | advanced
```

- Standard is the default.
- Advanced adds specialist routes allowed by policy.
- Advanced never disables safety confirmation.
- Advanced does not install optional packages automatically.
- Returning to Standard preserves hidden preferences and pins.

### 14.2 Compatibility adapter

Keep old experience-level parsing for one release as a migration adapter only.
There must be one new source of truth after migration.

Delete duplicated visibility lists from:

- Settings,
- wizard,
- navigation areas,
- feature-specific code,

once tests prove the new policy covers them.

### 14.3 Settings presentation

Settings > Advanced Tools contains:

- Standard/Advanced selector,
- concise description,
- optional component status,
- install guidance where relevant,
- immediate navigation refresh.

---

## 15. First-run and onboarding

Replace the fixed-size multi-step wizard with one responsive welcome surface.

Show:

- detected Fedora variant,
- package-management mode,
- Atomic or Traditional behavior,
- support status,
- short privacy/safety statement,
- primary action: **Open Loofi**,
- optional secondary action: **View system details**.

Rules:

- no mutating first-run actions,
- no experience-level question,
- no gaming/development/profile setup,
- existing completion sentinel remains honored,
- existing profile data is preserved,
- existing users do not see onboarding again,
- 1280x720 and high-scaling layouts work,
- semantic icons replace emoji headings,
- full keyboard navigation.

A one-time non-blocking "Navigation simplified" notice may be shown after upgrade
when it provides useful migration context.

---

## 16. Visual system and accessibility

### 16.1 Theme behavior

- Follow system theme by default.
- Use system font by default.
- Preserve explicit dark/light/high-contrast modes when reliable.
- Keep a Loofi accent layer without replacing the full KDE/Qt palette.
- Custom QSS becomes a semantic component layer rather than a desktop-theme
  replacement.

### 16.2 QSS cleanup

- remove superseded/duplicate selectors,
- scope by stable object names,
- remove global hardcoded font-family,
- use dynamic properties for state/risk,
- document component states,
- validate system/dark/light/high-contrast rendering.

### 16.3 Icons and controls

- semantic icon IDs everywhere,
- remove emojis from ordinary buttons/titles/lists,
- never communicate status by color alone,
- one primary action per section,
- technical output under Details,
- route cards use real signals and keyboard activation,
- do not monkey-patch `mousePressEvent` on individual card instances.

### 16.4 Shared states

Add reusable components:

- `LoadingState`
- `EmptyState`
- `UnavailableState`
- `ResultBanner`
- `ActionProgress`
- `DetailsDisclosure`

Do not replace Action Center's domain state machine with generic UI state.
These components present results; they do not own execution semantics.

### 16.5 Responsive/accessibility matrix

Validate at minimum:

- 1280x720 @ 100%
- 1366x768 @ 100%
- 1920x1080 @ 100% and 125%
- 2560x1440 @ 125%, 150%, and 200%
- minimum supported window width
- Wayland and X11 where still supported

Check:

- logical tab order,
- visible focus,
- accessible names/descriptions,
- screen-reader-friendly status changes,
- sufficient contrast,
- target sizes,
- no hover-only action,
- text alternatives for icons/custom painting.

---

## 17. Packaging strategy

### 17.1 Mandatory v15 packaging work

Mandatory:

- preserve existing `loofi-fedora-tweaks-api` and
  `loofi-fedora-tweaks-daemon` boundaries,
- introduce runtime component metadata independent of UI imports,
- ensure specialist components can be absent without core import failure,
- audit base dependencies,
- remove the emoji-font requirement when core no longer needs it,
- add core-with-specialists-disabled smoke tests,
- replace misleading package descriptions that market every specialist feature as
  core.

### 17.2 Conditional `-extras` split

A physical `loofi-fedora-tweaks-extras` RPM is a **go/no-go checkpoint**, not an
unconditional v15 release blocker.

Proceed only when all are true after true lazy loading lands:

1. Import/dependency graph shows clean component boundaries.
2. Core completes all six destinations and five workflows without specialist
   files.
3. No cross-package import cycle exists.
4. Upgrade from v14 preserves settings/routes/history.
5. RPM file ownership can be made explicit without overlap.
6. Install/remove/reinstall smoke is reliable.
7. COPR and Fedora review gates remain green.

If any condition fails, v15 ships logical/component isolation and lazy loading,
while the physical RPM split is documented for v16. This deferral does not block
v15 when the default UI and startup footprint meet their targets.

### 17.3 Candidate extras

Candidates, subject to dependency-graph evidence:

- Gaming
- Development Tools
- Performance Tuning
- Virtualization/VFIO
- Extensions
- Local AI
- Agents
- Automation
- Device Sharing/Mesh
- Workspace Transfer/Teleport
- Community/Marketplace

### 17.4 No `-devel` package in v15

Plugin SDK templates and hot-reload tooling may remain source/developer assets.
A separate devel RPM is deferred to a future release unless Fedora packaging rules
require it.

---

## 18. Implementation phases

Each phase is implemented as small, independently testable slices. Keep the branch
green after every slice. Use Planning mode for Phase 0 and bounded Goal-mode
implementation for later phases.

## Phase 0 — Baseline evidence and final task classification

The v14 architecture classification in this document is prefilled. Phase 0 adds
runtime measurements and confirms current HEAD.

### Tasks

- [ ] `V15-P0-001` Record actual implementation HEAD, v14 tag commit, Fedora test
  environment, and installed package version.
- [ ] `V15-P0-002` Read `AGENTS.md`, `ARCHITECTURE.md`, `ROADMAP.md`, v14 specs,
  release notes, verified-maintenance docs, migrations, and release evidence.
- [ ] `V15-P0-003` Inventory visible destinations/routes, Home surfaces, shell
  controls, startup services, plugin specs/instances, and packages.
- [ ] `V15-P0-004` Capture Standard/Intermediate/Advanced screenshots from a clean
  profile.
- [ ] `V15-P0-005` Measure startup milestones, first meaningful Home render, RSS,
  imported modules, timers, threads, and subprocess/service probes.
- [ ] `V15-P0-006` Trace the five workflows plus Action Center and count user
  decisions/clicks.
- [ ] `V15-P0-007` Validate the reconciliation matrix and mark every later task
  `KEEP`, `ADAPT`, `BUILD`, `DELETE`, `DEFER`, or `NOT_NEEDED`.
- [ ] `V15-P0-008` Record exact v14 regression tests and release gates that must
  remain blocking.
- [ ] `V15-P0-009` Create `docs/reports/V15_PHASE0_BASELINE.md` with commands,
  evidence, screenshots, and approved phase order.

### Exit criteria

- Reproducible baseline exists.
- Current HEAD and release tag are unambiguous.
- Every later task has a classification.
- No production code changed.

## Phase 1 — Destination, policy, and migration contracts

### Tasks

- [ ] `V15-P1-001` Add six destination definitions that reference existing route
  IDs.
- [ ] `V15-P1-002` Add the pure NavigationPolicy contract and result model.
- [ ] `V15-P1-003` Add route-to-destination/section mappings.
- [ ] `V15-P1-004` Add compatibility handling for duplicate/retired visible routes,
  especially `dashboard`.
- [ ] `V15-P1-005` Add Standard/Advanced mode contract.
- [ ] `V15-P1-006` Add idempotent settings/favorites/last-route/quick-action
  migration.
- [ ] `V15-P1-007` Preserve `maintenance:action-center` as a Standard-visible
  canonical route.
- [ ] `V15-P1-008` Add exhaustive policy/migration tests for Traditional, Atomic,
  missing component, incompatible plugin, favorite, and deep-link cases.
- [ ] `V15-P1-009` Add validation that every registered route has a destination and
  policy outcome.

### Exit criteria

- Contracts are PyQt-free.
- Existing route IDs continue to resolve.
- Standard mode cannot leak advanced routes.
- Action Center remains reachable and unchanged behaviorally.

## Phase 2 — True top-level lazy loading and startup deferral

This phase precedes the shell rewrite so the new shell is not built on the eager
registry and then rewritten again.

### Tasks

- [ ] `V15-P2-001` Introduce data-only built-in `PluginSpec` definitions.
- [ ] `V15-P2-002` Separate registry specs from runtime plugin instances.
- [ ] `V15-P2-003` Build navigation from specs without importing UI modules.
- [ ] `V15-P2-004` Import/construct a plugin only on route activation.
- [ ] `V15-P2-005` Preserve Maintenance sub-tab factory loading and tests.
- [ ] `V15-P2-006` Remove constructor-time heavy work from affected built-ins.
- [ ] `V15-P2-007` Defer Pulse, tray, dependency checks, notification UI, status
  refresh, update checks, and optional scans.
- [ ] `V15-P2-008` Make tray initialization conditional on settings.
- [ ] `V15-P2-009` Add import-audit, instance-cache, error-state, and timer-lifecycle
  tests.
- [ ] `V15-P2-010` Add stable startup benchmark markers/tooling.
- [ ] `V15-P2-011` Run v14 Action Center/state/CLI regressions after loader changes.

### Exit criteria

- Specialist UI modules are not imported at startup.
- Home/shell display without constructing unused plugins.
- Maintenance/Action Center deferred loading remains correct.
- Startup is measurably improved or an evidence-backed blocker is documented.

## Phase 3 — Six-destination shell and shared secondary navigation

### Tasks

- [ ] `V15-P3-001` Add flat destination sidebar/model.
- [ ] `V15-P3-002` Add shared destination host and secondary navigation.
- [ ] `V15-P3-003` Remove expandable child-page tree from Standard mode.
- [ ] `V15-P3-004` Add optional Advanced destination.
- [ ] `V15-P3-005` Move favorites/pins out of the sidebar.
- [ ] `V15-P3-006` Integrate collapse control into compact sidebar chrome.
- [ ] `V15-P3-007` Remove sidebar/footer version duplication and permanent hints.
- [ ] `V15-P3-008` Make status/activity chrome conditional.
- [ ] `V15-P3-009` Update shortcuts to destination-aware navigation.
- [ ] `V15-P3-010` Add normal/narrow/high-scaling shell tests.
- [ ] `V15-P3-011` Verify every v14 route can still be opened through direct
  navigation or a documented gate.

### Exit criteria

- Exactly six Standard destinations.
- At most one Advanced destination.
- No route behavior is lost.
- Shell remains compatible with deferred plugin construction.

## Phase 4 — Global search consolidation

### Tasks

- [ ] `V15-P4-001` Create one route/settings/action search model.
- [ ] `V15-P4-002` Apply NavigationPolicy to every result.
- [ ] `V15-P4-003` Bind `Ctrl+K` to global search.
- [ ] `V15-P4-004` Bind `Ctrl+Shift+K` to the same model filtered to actions.
- [ ] `V15-P4-005` Remove independent sidebar filtering and quick-action UI after
  migration.
- [ ] `V15-P4-006` Migrate useful configured quick actions to pins/suggestions.
- [ ] `V15-P4-007` Ensure Action Center search results only navigate/preselect.
- [ ] `V15-P4-008` Add keyboard, policy, risk, missing-component, and Action Center
  non-execution tests.

### Exit criteria

- One search implementation owns discovery.
- Search cannot bypass mode, component, Fedora, or safety policy.
- No action runs directly from search.

## Phase 5 — Canonical Home

### Tasks

- [ ] `V15-P5-001` Add PyQt-free HomeSummary/recommendation contracts.
- [ ] `V15-P5-002` Compose existing health, update, storage, backup, history, state,
  and Action Center sources.
- [ ] `V15-P5-003` Add deterministic recommendation ordering.
- [ ] `V15-P5-004` Replace Atlas Home UI with the canonical v15 Home.
- [ ] `V15-P5-005` Move live metrics/process details to System.
- [ ] `V15-P5-006` Redirect/adapt `dashboard` without breaking saved routes.
- [ ] `V15-P5-007` Remove duplicate recent-action/recent-change presentation.
- [ ] `V15-P5-008` Add Action Center attention/link behavior without planner
  duplication.
- [ ] `V15-P5-009` Retire duplicate Home implementation/imports safely.
- [ ] `V15-P5-010` Add fresh/stale/error/empty/critical/interrupted-run Home tests.

### Exit criteria

- One visible and maintained Home.
- No fast polling on Home.
- Action Center status is informative but never executable from Home.

## Phase 6 — Core workflow consolidation and Action Center placement

Implement as multiple PR-sized Goals; do not land all workflows in one large
change.

### Tasks

- [ ] `V15-P6-001` Place Action Center as a dedicated Software & Updates section
  while preserving route, lifecycle, and history.
- [ ] `V15-P6-002` Improve Action Center responsive/loading/manual-only presentation
  without changing domain semantics.
- [ ] `V15-P6-003` Consolidate Updates and Smart Updates presentation.
- [ ] `V15-P6-004` Simplify application installation flow.
- [ ] `V15-P6-005` Build slow-system guided summary from existing diagnostics.
- [ ] `V15-P6-006` Link failed-service findings to the existing v14 Action Center
  definition when eligible.
- [ ] `V15-P6-007` Add reclaim analysis/preview for disk cleanup.
- [ ] `V15-P6-008` Route DNF cache and supported trim through existing v14 action
  definitions.
- [ ] `V15-P6-009` Clarify Backup, Recovery Points, rollback guidance, support
  export, and Repair Loofi.
- [ ] `V15-P6-010` Consolidate Health/Diagnostics/Logs presentation without deleting
  trusted backends.
- [ ] `V15-P6-011` Apply canonical terminology across UI/tooltips/search/docs
  aliases.
- [ ] `V15-P6-012` Add end-to-end workflow tests and manual validation scripts.
- [ ] `V15-P6-013` Run all v14 Action Center tests unchanged after each relevant
  slice.

### Exit criteria

- Each workflow has one preferred route.
- Action Center remains the only plan/run/verify UI.
- No new executable action is introduced.
- Existing safety behavior remains identical.

## Phase 7 — Modes, onboarding, settings, and shell cleanup

### Tasks

- [ ] `V15-P7-001` Add Standard/Advanced Settings UI.
- [ ] `V15-P7-002` Retain old experience parsing as migration-only compatibility.
- [ ] `V15-P7-003` Remove old duplicated visibility lists after migration tests.
- [ ] `V15-P7-004` Replace multi-step first-run wizard with responsive welcome.
- [ ] `V15-P7-005` Preserve existing first-run sentinels/profile data.
- [ ] `V15-P7-006` Rename State Doctor presentation to Repair Loofi while reusing
  v14 services.
- [ ] `V15-P7-007` Add About page with version/build/support information.
- [ ] `V15-P7-008` Remove frameless no-op setting/stub.
- [ ] `V15-P7-009` Remove permanent notification bell unless Phase 0 proves unique
  value.
- [ ] `V15-P7-010` Add existing-user, mode-migration, and onboarding tests.

### Exit criteria

- New users reach Home with one primary action.
- Existing users do not repeat onboarding.
- No visible setting is a no-op.

## Phase 8 — Visual system, shared states, and accessibility

### Tasks

- [ ] `V15-P8-001` Make system theme/font default.
- [ ] `V15-P8-002` Consolidate QSS and remove obsolete selectors.
- [ ] `V15-P8-003` Replace ordinary emoji labels with semantic icons.
- [ ] `V15-P8-004` Upgrade shared route cards to accessible signal-based controls.
- [ ] `V15-P8-005` Add shared loading/empty/unavailable/result/details components.
- [ ] `V15-P8-006` Apply shared states to standard workflows and Action Center
  presentation without replacing its state machine.
- [ ] `V15-P8-007` Validate responsive/scaling matrix.
- [ ] `V15-P8-008` Run keyboard/focus/accessibility review.
- [ ] `V15-P8-009` Re-run startup/RSS/import measurements and workflow click counts.
- [ ] `V15-P8-010` Document accepted exceptions with evidence.

### Exit criteria

- Complexity/performance targets are met or explicitly approved with evidence.
- Standard workflows have no critical accessibility defect.
- Themes preserve the same information hierarchy.

## Phase 9 — Packaging/component go-no-go

### Tasks

- [ ] `V15-P9-001` Build import/dependency graph for specialist components.
- [ ] `V15-P9-002` Verify core runtime with specialist components disabled/absent.
- [ ] `V15-P9-003` Audit and reduce base RPM requirements, including emoji font.
- [ ] `V15-P9-004` Preserve API/daemon subpackage independence.
- [ ] `V15-P9-005` Run explicit `-extras` go/no-go review against Section 17.
- [ ] `V15-P9-006A` If GO: add `loofi-fedora-tweaks-extras` with non-overlapping
  ownership and install/remove/upgrade smoke.
- [ ] `V15-P9-006B` If NO-GO: document v16 packaging follow-up and ship logical
  component isolation only.
- [ ] `V15-P9-007` Update package/AppStream descriptions to distinguish core and
  specialist capability.
- [ ] `V15-P9-008` Verify v14-to-v15 RPM upgrade preserves all supported state and
  Action Center history.

### Exit criteria

- Core behavior never depends on optional specialist imports.
- Existing API/daemon packaging remains valid.
- Extras split ships only when evidence proves it safe.

## Phase 10 — Documentation and release

### Tasks

- [ ] `V15-P10-001` Update version/codename metadata through
  `scripts/bump_version.py` only when implementation is release-ready.
- [ ] `V15-P10-002` Add v15 entry/specs to roadmap/workflow state and mark scope
  accurately.
- [ ] `V15-P10-003` Add release notes and migration notes.
- [ ] `V15-P10-004` Rewrite README around the six-destination experience and v14
  verified-maintenance preservation.
- [ ] `V15-P10-005` Document Standard/Advanced and optional component behavior.
- [ ] `V15-P10-006` Update Beginner/Advanced/Troubleshooting/Verified Maintenance
  guides.
- [ ] `V15-P10-007` Update architecture docs for destinations, policy, PluginSpec,
  Home composition, and optional components.
- [ ] `V15-P10-008` Regenerate canonical screenshots from the real v15 app.
- [ ] `V15-P10-009` Validate AppStream, desktop entry, RPM, source archive, SBOM,
  provenance, and release artifacts.
- [ ] `V15-P10-010` Run full v14-inherited CI, 85% coverage, security, Fedora review,
  RPM/COPR, install, upgrade, and public readback gates.

### Exit criteria

- Documentation matches shipped UI and package layout.
- Release artifacts are reproducible and tied to the exact release commit.
- No document advertises retired default surfaces as core.

---

## 19. Likely file changes

Final paths follow the actual v14 architecture and Phase 0 findings.

### Navigation/contracts

- `loofi-fedora-tweaks/core/navigation/destinations.py`
- `loofi-fedora-tweaks/core/navigation/policy.py`
- `loofi-fedora-tweaks/core/navigation/migrations.py`
- `loofi-fedora-tweaks/core/navigation/models.py`
- existing manifest/areas compatibility modules

### Plugin/startup

- `loofi-fedora-tweaks/core/plugins/spec.py`
- `loofi-fedora-tweaks/core/plugins/registry.py`
- `loofi-fedora-tweaks/core/plugins/loader.py`
- `loofi-fedora-tweaks/ui/lazy_widget.py`
- `loofi-fedora-tweaks/ui/main_window.py`
- affected plugin constructors/lifecycle hooks

### Home/shell/search

- `loofi-fedora-tweaks/core/home/models.py`
- `loofi-fedora-tweaks/core/home/service.py`
- `loofi-fedora-tweaks/core/home/recommendations.py`
- `loofi-fedora-tweaks/ui/atlas_dashboard_tab.py` or a compatible new Home module
- `loofi-fedora-tweaks/ui/dashboard_tab.py` compatibility adapter/removal target
- `loofi-fedora-tweaks/ui/navigation/destination_sidebar.py`
- `loofi-fedora-tweaks/ui/navigation/destination_host.py`
- `loofi-fedora-tweaks/ui/global_search.py`
- `loofi-fedora-tweaks/ui/layout_primitives.py`

### Workflows/settings

- `loofi-fedora-tweaks/ui/maintenance_tab.py`
- `loofi-fedora-tweaks/ui/software_tab.py`
- `loofi-fedora-tweaks/ui/monitor_tab.py`
- `loofi-fedora-tweaks/ui/storage_tab.py`
- `loofi-fedora-tweaks/ui/diagnostics_tab.py`
- `loofi-fedora-tweaks/ui/health_timeline_tab.py`
- `loofi-fedora-tweaks/ui/backup_tab.py`
- `loofi-fedora-tweaks/ui/settings_tab.py`
- `loofi-fedora-tweaks/ui/wizard.py`
- `loofi-fedora-tweaks/utils/experience_level.py`
- `loofi-fedora-tweaks/utils/favorites.py`
- `loofi-fedora-tweaks/utils/settings.py`

### Action Center files protected from unnecessary rewrite

- `loofi-fedora-tweaks/core/actions/contracts.py`
- `loofi-fedora-tweaks/core/actions/catalog.py`
- `loofi-fedora-tweaks/core/actions/orchestrator.py`
- `loofi-fedora-tweaks/core/actions/stores.py`
- `loofi-fedora-tweaks/core/actions/center.py`

Changes to these files require an explicit v14 invariant justification and focused
regression tests. UI placement changes should normally not require changing them.

### Themes/assets/packaging

- QSS theme files
- semantic icon map/assets
- `pyproject.toml`
- `loofi-fedora-tweaks.spec`
- AppStream metadata
- package/release scripts only when Phase 9/10 requires them

---

## 20. Deletion and merge candidates

Every deletion requires code search, route mapping, state migration, and tests.

Candidates:

- duplicate full Home/dashboard implementation,
- separate visible Live Overview as a second Home,
- standalone quick-actions dialog/grid,
- sidebar-only search implementation,
- Favorites sidebar category,
- permanent shortcut/footer/version chrome,
- permanent notification bell,
- first-run experience/use-case/action wizard steps,
- frameless no-op setting/stub,
- duplicate Health/Diagnostics/Logs presentation,
- separate Smart Updates presentation after behavior mapping,
- eager top-level plugin imports/instances,
- unconditional tray/Pulse/dependency/status initialization,
- obsolete QSS sections and emoji labels.

Not deletion candidates in v15:

- Action Center orchestrator/contracts/stores/catalog,
- Action Center dedicated Review/Plan/Run/Verify/History route,
- v14 state/observability services,
- CLI/API/daemon contracts,
- v14 release gates,
- trusted backends whose visible UI is being consolidated.

---

## 21. Test strategy

### 21.1 Required v14 regressions

At minimum preserve and run relevant suites covering:

- Action Center v14 contracts/lifecycle,
- Action Center API/CLI behavior,
- Maintenance Action Center UI,
- state v13/v14 migration/backup/doctor behavior,
- observability collection,
- support bundle v10,
- release-doc checks,
- SRPM/RPM/Fedora review contracts,
- route/favorite/sidebar behavior.

### 21.2 New unit tests

- destination model,
- NavigationPolicy decisions,
- route/destination mapping,
- mode/settings/favorites migration,
- HomeSummary/recommendation ordering,
- PluginSpec parsing/registration,
- lazy import/instance cache,
- optional component discovery,
- result-state formatting.

### 21.3 New UI tests

- exact six Standard destinations,
- optional Advanced destination,
- shared secondary navigation,
- collapsed sidebar,
- global search/action filter,
- gated/unavailable routes,
- Home content limits,
- Action Center navigation without execution,
- keyboard navigation,
- conditional activity UI,
- missing-dependency states,
- narrow/high-scale layouts.

### 21.4 Lifecycle tests

- clean first run,
- existing v14 upgrade,
- invalid settings recovery,
- Standard -> Advanced -> Standard,
- old intermediate migration,
- Action Center stored plan/run history after upgrade,
- core with specialist components absent,
- optional extras install/remove only if Phase 9 GO.

### 21.5 Performance evidence

Record:

- process start,
- QApplication creation,
- MainWindow creation,
- first show,
- first meaningful Home content,
- Home refresh completion,
- RSS,
- imported UI/plugin modules,
- active timers/threads,
- nonessential probes started before first render.

Store raw measurements and medians locally in release evidence. Add no telemetry.

---

## 22. Release gates

v15 cannot release until all mandatory gates are true:

- [ ] Phase 0 evidence exists and identifies exact HEAD/tag.
- [ ] Six Standard destinations are enforced by tests.
- [ ] One maintained Home remains.
- [ ] One global search/action model remains.
- [ ] Standard/Advanced migration is tested.
- [ ] NavigationPolicy governs every route-discovery surface.
- [ ] Existing route IDs, including `maintenance:action-center`, resolve safely.
- [ ] Action Center v14 plan/run/verify/lease/catalog invariants pass unchanged.
- [ ] Home/search cannot execute or auto-plan an Action Center action.
- [ ] Core startup does not import specialist UI modules.
- [ ] Startup/RSS targets are met or an explicit evidence-backed exception is
  approved.
- [ ] Five core workflows pass automated and manual validation.
- [ ] v14 settings, favorites, history, Action Center records, and state upgrade
  correctly.
- [ ] Coverage is at least 85%.
- [ ] No critical accessibility issue remains.
- [ ] Existing API/daemon subpackages still build and run independently.
- [ ] Physical extras split, if shipped, passes every go/no-go and ownership test.
- [ ] Full CI, security, Fedora review, RPM/COPR, install, upgrade, provenance,
  checksum, and public readback gates pass.
- [ ] README, guides, architecture, roadmap, changelog, screenshots, AppStream,
  and release notes agree.
- [ ] No duplicate visible workflow remains without documented justification.

---

## 23. Definition of Done

v15.0.0 "Essentials" is complete when a normal Fedora user can open the app and
understand, without prior knowledge:

- whether anything needs attention,
- where to update the system,
- where to install applications,
- where to inspect performance and storage,
- where to manage security and backup,
- where to review verified maintenance actions,
- where to change desktop and application settings.

The release is not complete merely because pages were hidden or the sidebar was
restyled. It must demonstrate:

- reduced startup work,
- real top-level on-demand plugin loading,
- one coherent Home,
- consolidated workflows,
- consistent terminology,
- preserved v14 safety and compatibility,
- measured improvement against the live v14 baseline.

A physical extras RPM is not required for Definition of Done when Phase 9 produces
an evidence-backed NO-GO and logical component isolation meets the UX/startup
objectives.

---

## 24. Codex execution rules

1. Start from current `master`, not a pre-v14 checkout.
2. Use Planning mode for Phase 0 only.
3. Do not modify production code before the baseline report is approved.
4. Use one bounded Goal per implementation slice or workflow.
5. Preserve current route IDs unless a tested compatibility adapter exists.
6. Treat Action Center v14 contracts as protected architecture.
7. Never execute Action Center actions from Home or search.
8. Do not expand the executable action catalog.
9. Implement true plugin lazy loading before the new shell.
10. Keep changes small, reviewable, and green.
11. Add tests before deleting compatibility paths.
12. Reuse trusted services/core backends instead of creating parallel systems.
13. Do not mix shell rewrite, workflow behavior, loader architecture, and RPM split
    in one change.
14. Do not lower safety, coverage, Fedora review, packaging, or release gates.
15. Do not version-bump until final release phase.
16. After each Goal report:
    - files changed,
    - behavior changed,
    - compatibility preserved,
    - tests run,
    - measured impact,
    - unresolved risks,
    - deferred work.

---

## 25. Planning-mode kickoff prompt

```text
Read AGENTS.md, ARCHITECTURE.md, ROADMAP.md, CHANGELOG.md,
docs/VERIFIED_MAINTENANCE.md, docs/releases/RELEASE-NOTES-v14.0.0.md,
the v14 workflow specs, and LOOFI_FEDORA_TWEAKS_V15_PLAN.md.

Perform Phase 0 only against the current master branch.

The reviewed reference state was:
- v14.0.0 "Helm"
- tag baseline 4f0c09174e0c1a7abe0e09f810795ea2f8d3a830
- post-release master fe774cfa9f0916a9214a42a3c1125a26680e0351

Verify the actual current HEAD before relying on those values.

Measure startup, first meaningful Home render, RSS, imported modules, timers,
threads, startup probes, visible routes, and workflow decision counts.

Validate every task classification as KEEP, ADAPT, BUILD, DELETE, DEFER, or
NOT_NEEDED. Pay special attention to these mandatory corrections:

- preserve Action Center contracts, route, bounded catalog, explicit confirmation,
  separate verification, expiry, lease, interruption, CLI/API/support behavior
- preserve State Doctor/archive and v14 release-lineage contracts
- preserve existing route IDs and add destination mapping rather than replacing
  the route namespace
- reuse Maintenance sub-tab lazy loading
- implement top-level PluginSpec lazy loading before rebuilding the shell
- treat a physical extras RPM as a later go/no-go decision

Do not modify production code.
Do not bump the version.
Do not start Phase 1.

The only allowed repository change is:
docs/reports/V15_PHASE0_BASELINE.md
```

---

## 26. Goal-mode implementation template

```text
Implement only Phase <N> / slice <NAME> from
LOOFI_FEDORA_TWEAKS_V15_PLAN.md, using
docs/reports/V15_PHASE0_BASELINE.md as the authoritative adaptation to the
current repository state.

Preserve all v14 invariants, especially Action Center, state integrity, route
compatibility, Traditional/Atomic behavior, CLI/API/daemon contracts, and release
gates.

Requirements:
- small reviewable changes
- tests with every behavior change
- targeted tests after each logical slice
- relevant v14 regressions before completion
- no later-phase work
- no unrelated features
- no version bump
- no commit/push unless explicitly requested

Final report:
- files changed
- behavior changed
- compatibility preserved
- tests run and results
- measurements where applicable
- remaining issues
- deferred work
```
