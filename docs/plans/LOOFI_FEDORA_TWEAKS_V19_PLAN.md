# Loofi Fedora Tweaks v19.0.0 "Steward"

## Implementation plan

**Repository:** `loofiboss-bit/loofi-fedora-tweaks`  
**Reviewed branch:** `master`  
**Reviewed commit:** `9cf7f520a38b089ebffc144041baebae583f4ca4`  
**Current release:** v18.0.0 "Haven"  
**Proposed release:** v19.0.0 "Steward"  
**Primary theme:** Guided system checks and verified resolution  
**Plan date:** 2026-07-24

---

## 1. Outcome

v19 turns the secure maintenance foundation from v18 into one understandable
end-user loop:

1. The user selects **Check now** from Home.
2. Loofi runs one bounded, read-only quick system check.
3. The result explains what is healthy, what needs attention, the evidence, and
   when that evidence was collected.
4. An actionable finding can open one exact, reviewed Action Center plan.
5. The user confirms, runs, and verifies that plan through the existing v18
   trust boundary.
6. A follow-up check shows whether the original finding is resolved, unchanged,
   awaiting reboot, or still needs manual work.

The release does not add another broad feature area. It connects Home, Daily
Maintenance, health snapshots, metrics, diagnostics, Action Center, CLI, and
support bundles into one canonical **System Check** experience.

### User-visible success

- A clean first launch no longer leaves Home at four unavailable statuses with
  only an indirect link to another page.
- Home can start an explicit read-only check without running probes during cold
  startup.
- There is exactly one canonical System Check page in Standard mode.
- Findings use plain explanations and visible evidence rather than only raw
  command output or generic severity labels.
- Supported findings link to one exact Action Center action.
- Unsupported findings provide honest manual guidance and never expose a fake
  Fix button.
- Existing health history, metrics, routes, aliases, and Action Center records
  remain readable.

---

## 2. Current state

### Verified baseline

The review found:

- v18.0.0 "Haven" is the current public release.
- The v18 release commit passed canonical CI, CodeQL, packaging, COPR, checksum,
  SBOM, provenance, and Fedora 44 installation readback.
- `.project-stats.json` reports 6,864 collected tests, 6,796 passed, 68 skipped,
  86.24 percent coverage, 279 test files, and 28 feature tabs.
- The repository exposes 80 stable routes and 56 classified first-party Action
  Center definitions.
- Local read-only checks passed during this review:
  - `scripts/validate_v18_haven.py`
  - `scripts/validate_v18_architecture.py`
  - `scripts/project_stats.py --check`
  - `scripts/sync_ai_adapters.py --check`
  - `scripts/check_stabilization_rules.py`
  - `scripts/check_release_docs.py`
- The GitHub issue and pull-request searches returned no open work items.

### What is complete

| Area | State | Evidence |
| --- | --- | --- |
| Host mutation trust boundary | Complete | GUI, CLI, daemon, automation, and agent host mutations converge on Action Center |
| Action execution | Complete | One action per expiring plan, explicit confirmation, bounded execution, separate verification |
| Fedora variants | Complete for current target | Traditional and Atomic policy branches exist; unsupported work fails closed |
| Read-only health snapshots | Complete | `core/observability/` stores bounded privacy-safe snapshots and trends |
| Home recommendations | Complete but passive | `core/home/service.py` reads saved state and chooses one recommendation |
| Health metrics | Complete but separate | `core/diagnostics/health_timeline.py` maintains a second SQLite metric timeline |
| Support bundle | Complete | Current support bundle includes maintenance and observability context |
| Startup safety | Complete | Meaningful Home stays lazy with one provider and no startup probes, timers, or worker threads |

### What is partial or fragmented

| Problem | Current evidence | User impact |
| --- | --- | --- |
| Empty Home requires manual discovery | `HomeService` returns `first_health_review`; Home only links away to create the first snapshot | First-run status looks unavailable instead of useful |
| Two health histories coexist | `ui/health_timeline_tab.py` uses the metric store; `_HealthTimelineSubTab` in `maintenance_action_center.py` uses observability snapshots | Similar names lead to different data and actions |
| Health, diagnostics, and remediation are separate journeys | Home, System Health History, Troubleshooting, release readiness, and Action Center each present part of the answer | Users must understand internal architecture to complete one task |
| Findings do not own a canonical remedy link | Home recommendations usually route to a page; Action Center then requires manual candidate selection | The safe action catalog is not fully converted into user value |
| Source and freshness are not consistently visible | Home knows fresh/stale/error, but detailed evidence and provenance are spread across stores | Users cannot easily judge why Loofi recommends something |
| Documentation authority has drift | `ARCHITECTURE.md` still identifies release 17.0.0 while runtime and roadmap are v18 | New work could be based on stale contracts |
| Release validators are version-named | CI and `Justfile` still invoke `validate_v18_*` scripts | Every major version encourages another parallel validator |

### Important constraints

- Fedora 44 remains the supported target at the reviewed commit.
- Fedora 45 is preview-only and must not be promoted before upstream stable
  release and project certification.
- Action Center plans must continue to contain exactly one action.
- Background actors may create plans but may not confirm or execute them.
- Home must not collect system data during cold startup.
- The Web API remains loopback-only and non-mutating.
- Existing stable route IDs, aliases, settings, favorites, and persisted data
  must remain readable.

---

## 3. Top priority

### Build one canonical System Check and resolution journey

This outranks a new feature family, an AI assistant, a toolkit rewrite, or an
optional-package split because v18 already contains the difficult safety,
diagnostic, history, and execution foundations. The highest-value missing piece
is the connection between them.

The primary architectural rule for v19 is:

> A finding may recommend or preselect an audited action, but it may never
> execute, confirm, broaden, or rewrite that action.

### Candidate comparison

| Candidate | User value | Risk | Decision |
| --- | ---: | ---: | --- |
| Canonical System Check and guided resolution | High | Medium | **v19 theme** |
| Fedora 45 support | Required when stable | Medium and schedule-dependent | Release gate, not the product theme |
| New AI or agent features | Low for the core Fedora workflow | High scope and trust cost | Exclude |
| Remote mutating API | Low for normal desktop users | Critical trust expansion | Exclude |
| Physical `-extras` RPM split | Low; the base package is already small | High ownership and upgrade risk | Exclude |
| Another UI redesign | Low after v16 | High regression risk | Exclude |
| More standalone Advanced tools | Low and increases product breadth | Medium-high | Exclude |

---

## 4. Scope

### Included

- One canonical, PyQt-free System Check domain model and service.
- One explicit, cancellable, read-only quick check from Home and System.
- Consolidated findings, evidence, freshness, history, and metric context.
- Deterministic finding-to-action mappings validated against the existing
  first-party Action Center catalog.
- Finding context carried into plans and runs as non-authoritative metadata.
- Before/after comparison after a user requests a follow-up check.
- CLI parity for check, findings, history, and machine-readable output.
- Read-only support-bundle and API exposure of the latest bounded result.
- Compatibility redirects/adapters for existing health routes and commands.
- Architecture, documentation, accessibility, performance, and release gates.
- Conditional promotion of the latest stable Fedora release only after
  Traditional and Atomic certification.

### Explicitly excluded

- Automatic Fix All, bulk execution, chained execution, automatic confirmation,
  automatic reboot, retry, rollback, or resume.
- Running a system check automatically during GUI cold startup.
- Continuous polling from Home.
- AI-written diagnoses or cloud analysis.
- New remote mutation endpoints.
- Reintroduction of public Marketplace or executable external plugins.
- Physical specialist-package splitting.
- Deleting old health metrics, snapshots, action history, routes, aliases, or
  legacy user files.
- Broad Advanced-mode redesign.
- PyQt toolkit replacement.
- A new deep security scanner. v19 composes existing bounded checks.

---

## 5. Product contract

### Canonical quick-check areas

The initial quick check should stay bounded to signals already collected by
trusted services:

1. Loofi application-state integrity.
2. Package-manager and update health.
3. Failed services and incomplete maintenance.
4. Root filesystem pressure and reclaimable-space signals.
5. Recovery protection and pending reboot.
6. Existing Action Center failures or interrupted runs.

Security audit, SMART long tests, network scans, release-upgrade readiness,
firmware work, and other expensive or specialized checks remain explicit routes
linked as follow-up actions. They are not silently folded into the quick check.

### Finding contract

Each finding must include:

- stable finding ID;
- category and severity;
- short title and plain-language summary;
- structured, privacy-safe evidence;
- collection source and timestamp;
- freshness state;
- affected resources;
- applicability to Traditional and/or Atomic Fedora;
- one of:
  - an existing audited Action Center action ID;
  - a navigation-only route;
  - manual guidance with a reason code;
- a deterministic fingerprint for before/after comparison.

Finding content is advisory. The Action Center definition, current preflight,
closed parameter schema, command renderer, policy, and verifier remain the only
execution authorities.

### Check-result states

`queued`, `running`, `completed`, `partial`, `cancelled`, and `failed`.

Partial collection must preserve successful findings and visibly list failed
sources. It must never present partial data as an all-clear result.

### Resolution states

`not_reviewed`, `plan_ready`, `running`, `awaiting_reboot`, `verified`,
`resolved`, `unchanged`, `manual_only`, and `verification_failed`.

`verified` describes the Action Center action result. `resolved` describes a
later System Check comparison. They must not be treated as synonyms.

---

## 6. Implementation phases

## Phase 0 — Authority, baseline, and scope lock

### Objective and user value

Establish exact v18 behavior before changing it so v19 does not regress routes,
startup, persisted data, or the Action Center boundary.

### Likely components

- `ROADMAP.md`
- `ARCHITECTURE.md`
- `.workflow/specs/.race-lock.json`
- `.workflow/specs/arch-v19.0.0.md`
- `.workflow/specs/tasks-v19.0.0.md`
- `docs/plans/LOOFI_FEDORA_TWEAKS_V19_PLAN.md`
- `docs/reports/V19_PHASE0_BASELINE.md`
- `scripts/`
- `.project-stats.json`

### Tasks

1. Confirm `master` and the v18 release/tag evidence.
2. Fix the stale current-release and schema statements in `ARCHITECTURE.md`.
3. Inventory:
   - all health, maintenance, diagnostics, readiness, and Home routes;
   - both persisted health stores and their readers/writers;
   - existing finding/recommendation IDs;
   - all finding-to-action candidates;
   - route aliases and saved-navigation compatibility;
   - current startup, scan-duration, memory, and UI screenshot baselines.
4. Record current Traditional and Atomic support evidence without overstating
   carried-forward certification.
5. Mark v19 as the sole active roadmap target and set the race lock.
6. Create version-neutral validator names and keep thin v18 compatibility
   wrappers if external workflows still call them.
7. Make no runtime product changes.

### Acceptance criteria

- Every existing health-related route and data store has a KEEP, ADAPT,
  MIGRATE, REDIRECT, or RETIRE_PRESENTATION classification.
- The baseline records the empty, fresh, stale, partial-error, and critical Home
  states.
- The baseline records quick-check wall time per collector and total duration.
- `ARCHITECTURE.md`, roadmap, workflow specs, and race lock agree on current and
  active versions.
- No route, state, UI, or execution behavior changes in this phase.

### Verification

```bash
git status --short
python3 scripts/check_release_docs.py
PYTHONPATH=loofi-fedora-tweaks python3 scripts/project_stats.py --check
python3 scripts/sync_ai_adapters.py --check
python3 scripts/check_stabilization_rules.py
PYTHONPATH=loofi-fedora-tweaks python3 scripts/validate_product_contract.py
PYTHONPATH=loofi-fedora-tweaks python3 scripts/validate_architecture.py
```

### Checkpoint

Commit only after all authority and drift checks pass.

Suggested commit:

```text
docs(v19): lock Steward baseline and authority
```

---

## Phase 1 — Canonical System Check domain

### Objective and user value

Create one testable definition of a check result and finding without changing
the GUI.

### Likely components

- `loofi-fedora-tweaks/core/system_check/__init__.py`
- `loofi-fedora-tweaks/core/system_check/models.py`
- `loofi-fedora-tweaks/core/system_check/service.py`
- `loofi-fedora-tweaks/core/system_check/mappings.py`
- `loofi-fedora-tweaks/core/diagnostics/daily_maintenance.py`
- `loofi-fedora-tweaks/core/observability/snapshot.py`
- `loofi-fedora-tweaks/core/observability/timeline.py`
- `loofi-fedora-tweaks/core/observability/trends.py`
- `loofi-fedora-tweaks/core/state/`
- `loofi-fedora-tweaks/core/actions/catalog.py`
- `tests/test_system_check_models.py`
- `tests/test_system_check_service.py`
- `tests/test_system_check_mappings.py`

### Tasks

1. Add immutable `SystemCheckResult`, `SystemFinding`, `FindingEvidence`, and
   `CheckSourceError` models.
2. Compose existing trusted collectors; do not duplicate their probes.
3. Keep the quick-check profile closed and explicit.
4. Add per-collector timeouts, duration metadata, cancellation boundaries, and
   partial-result behavior.
5. Create deterministic finding fingerprints from normalized, redacted facts.
6. Define static finding-to-action mappings using existing first-party action
   IDs.
7. Add a gate that fails on:
   - a mapping to an unknown or retired action;
   - an action parameter not derivable from closed evidence;
   - an actionable high-severity finding without action or manual guidance;
   - a finding attempting to carry a command vector.
8. Adapt the current `HealthSnapshot` envelope rather than replacing its store.
   If the schema must advance, migrate one version at a time with atomic
   readback and unknown-future-schema read-only behavior.
9. Preserve the current metric SQLite store. It becomes supporting evidence,
   not a second product-level health authority.

### Acceptance criteria

- The domain imports no PyQt module.
- A clean fixture produces a completed result with no findings.
- One failed collector produces a partial result, not a false healthy result.
- Cancellation stops pending collectors and persists no corrupt envelope.
- Traditional and Atomic applicability is explicit on every finding.
- No finding contains an executable command or callback.
- Existing v18 snapshots remain readable.

### Verification

```bash
just test-file test_system_check_models
just test-file test_system_check_service
just test-file test_system_check_mappings
just test-file test_observability
just test-file test_state_v14
just lint
just typecheck
```

### Checkpoint

```text
feat(core): add canonical read-only system check domain
```

---

## Phase 2 — Explicit Home check workflow

### Objective and user value

Make first-run and stale Home states immediately actionable while preserving the
zero-probe startup contract.

### Likely components

- `loofi-fedora-tweaks/core/home/models.py`
- `loofi-fedora-tweaks/core/home/service.py`
- `loofi-fedora-tweaks/core/home/recommendations.py`
- `loofi-fedora-tweaks/ui/atlas_dashboard_tab.py`
- `loofi-fedora-tweaks/core/workers/`
- `loofi-fedora-tweaks/ui/components/`
- `tests/test_home_service.py`
- `tests/test_home_ui.py`
- `tests/test_system_check_home_flow.py`
- `scripts/benchmark_startup.py`

### Tasks

1. Add a visible **Check now** action for empty, stale, and recoverable-error
   Home states.
2. Start the check only after explicit user activation.
3. Run collection off the UI thread through the existing worker conventions.
4. Show current source, progress, elapsed time, cancellation, and partial
   failures without raw tracebacks.
5. Refresh Home from the completed persisted result.
6. Show **Last checked** and freshness on the status card.
7. Keep one primary recommendation, at most three attention items, and four
   common tasks.
8. Do not add a polling timer or automatic launch-time collection.
9. Ensure closing the page/window cancels or safely detaches the worker.

### Acceptance criteria

- Empty Home offers **Check now** directly.
- Home paints its first meaningful frame before importing collectors.
- No check begins without the user action.
- The UI remains responsive during every collector.
- Cancellation is visible and leaves the previous good snapshot intact.
- A partial result names unavailable sources and never reports overall good.
- Cold-start plugin, probe, timer, thread, and RSS budgets remain within the v18
  gate.

### Verification

```bash
just test-file test_home_service
just test-file test_home_ui
just test-file test_system_check_home_flow
QT_QPA_PLATFORM=offscreen PYTHONPATH=loofi-fedora-tweaks \
  python3 scripts/benchmark_startup.py --runs 10 --warmups 1
just lint
just typecheck
```

### Manual checks

- Empty, fresh, stale, partial, cancelled, failed, and critical states.
- 860, 1180, and 1400 DIP widths.
- 100, 140, and 200 percent scale.
- System, dark, light, and high-contrast themes.
- Keyboard-only start, cancel, result review, and route activation.

### Checkpoint

```text
feat(home): add explicit asynchronous system check
```

---

## Phase 3 — One System Check page and compatibility migration

### Objective and user value

Remove the confusing split between Health Timeline, Health History, metrics,
daily maintenance, and current findings without losing data or stable routes.

### Likely components

- `loofi-fedora-tweaks/ui/system_check_tab.py`
- `loofi-fedora-tweaks/ui/health_timeline_tab.py`
- `loofi-fedora-tweaks/ui/maintenance_action_center.py`
- `loofi-fedora-tweaks/ui/maintenance_tab.py`
- `loofi-fedora-tweaks/core/navigation/`
- `loofi-fedora-tweaks/core/product_catalog.py`
- `loofi-fedora-tweaks/core/product_catalog_records.py`
- `loofi-fedora-tweaks/cli/parser.py`
- `loofi-fedora-tweaks/cli/main.py`
- `tests/test_system_check_ui.py`
- `tests/test_navigation_compatibility.py`
- `tests/test_cli_system_check.py`

### Tasks

1. Add one Standard-mode **System Check** section with:
   - Overview;
   - Current findings;
   - History and before/after state;
   - collapsed metric details when available.
2. Reuse shared v16 components and semantic roles.
3. Move the observability snapshot history out of the Action Center module.
4. Convert the legacy metric `HealthTimelineTab` into a compatibility adapter
   or supporting detail view.
5. Preserve these route contracts:
   - `health`;
   - `maintenance:health-timeline`;
   - existing Home and diagnostics deep links.
6. Make both historical routes resolve to the canonical System Check
   experience with appropriate preselection.
7. Preserve both underlying stores and exports.
8. Consolidate CLI behavior under:
   - `loofi health check`;
   - `loofi health findings`;
   - `loofi health history`;
   - `loofi --json health ...`.
9. Keep existing `health snapshot`, `health timeline`, `health-history`, and
   `maintenance today` contracts as documented compatibility aliases.
10. Do not add a seventh Standard destination.

### Acceptance criteria

- Standard mode exposes exactly one user-facing System Check section.
- Every v18 route and alias still resolves.
- Existing snapshot JSON and metric SQLite data are visible after upgrade.
- No duplicate Record Snapshot action remains in two Standard surfaces.
- The page explains the distinction between a system finding, a sampled metric,
  and an Action Center run.
- CLI JSON uses a versioned stable envelope and never mixes human text into
  machine-readable output.

### Verification

```bash
just test-file test_system_check_ui
just test-file test_navigation_compatibility
just test-file test_cli_system_check
just test-file test_health_timeline
just test-file test_v15_routes
PYTHONPATH=loofi-fedora-tweaks python3 scripts/validate_product_contract.py
just lint
just typecheck
```

### Checkpoint

```text
feat(ui): consolidate system checks and health history
```

---

## Phase 4 — Finding-to-Action Center handoff

### Objective and user value

Let a user move from an explained finding to the correct reviewed action without
manually searching the 56-action catalog.

### Likely components

- `loofi-fedora-tweaks/core/system_check/mappings.py`
- `loofi-fedora-tweaks/core/actions/contracts.py`
- `loofi-fedora-tweaks/core/actions/orchestrator.py`
- `loofi-fedora-tweaks/core/actions/stores.py`
- `loofi-fedora-tweaks/core/actions/center.py`
- `loofi-fedora-tweaks/ui/system_check_tab.py`
- `loofi-fedora-tweaks/ui/maintenance_action_center.py`
- `tests/test_system_check_action_handoff.py`
- `tests/test_action_center_steward.py`
- `tests/test_action_center_migrations.py`

### Tasks

1. Add optional, non-authoritative finding context to Action Center plans/runs:
   - check result ID;
   - finding fingerprint;
   - evidence digest;
   - origin route;
   - affected resources.
2. Advance the Action Center schema only if required; migrate atomically from
   v1-v3 and keep future schemas read-only.
3. Add **Review safe action** only when a valid first-party mapping exists.
4. Open Action Center with the exact action preselected.
5. Run current preflight and render the command from the Action Center
   definition. Never accept a command from the finding.
6. Keep the existing explicit confirmation and no-rollback acknowledgement.
7. For manual-only findings, show the reason, route, and guidance without an
   enabled Run control.
8. Preserve exactly one action per plan and one cross-process mutation lease.
9. Record the relationship between check, finding, plan, and run for later
   display, but do not let context alter execution policy.

### Acceptance criteria

- A mapped finding opens one exact audited action.
- Tampered, stale, unknown, or mismatched finding context cannot produce an
  executable plan.
- Apply still regenerates the command and reruns preflight.
- Background and agent paths still cannot confirm or run plans.
- Manual-only findings cannot reach execution.
- Existing v1-v3 plan/run history remains readable.
- A plan without finding context behaves exactly as in v18.

### Verification

```bash
just test-file test_system_check_action_handoff
just test-file test_action_center_steward
just test-file test_action_center_migrations
just test-file test_action_center_assurance
just test-file test_action_center_v14
PYTHONPATH=loofi-fedora-tweaks python3 scripts/validate_product_contract.py
just lint
just typecheck
```

### Checkpoint

```text
feat(actions): link findings to reviewed maintenance plans
```

---

## Phase 5 — Verified resolution and support evidence

### Objective and user value

Show what changed after maintenance and make unresolved problems easier to
support.

### Likely components

- `loofi-fedora-tweaks/core/system_check/comparison.py`
- `loofi-fedora-tweaks/core/observability/trends.py`
- `loofi-fedora-tweaks/core/home/service.py`
- `loofi-fedora-tweaks/core/actions/orchestrator.py`
- `loofi-fedora-tweaks/core/export/support_bundle_v5.py`
- `loofi-fedora-tweaks/core/export/report_exporter.py`
- `loofi-fedora-tweaks/api/routes/system.py`
- `loofi-fedora-tweaks/ui/system_check_tab.py`
- `tests/test_system_check_comparison.py`
- `tests/test_support_bundle_system_check.py`
- `tests/test_api_system_check.py`

### Tasks

1. Add deterministic comparison of two compatible check results.
2. Classify each original finding as resolved, unchanged, worsened, or not
   comparable.
3. After Action Center verification, offer **Check again** for the affected
   areas.
4. Do not claim resolution from command exit code or verifier success alone.
5. Show pending reboot as a separate state until a later compatible check.
6. Update Home recommendations from the latest comparison and Action Center
   run state.
7. Include bounded result, finding, comparison, and linked plan/run metadata in
   the support bundle.
8. Apply existing redaction to paths, hostnames, emails, tokens, network
   identifiers, and command output.
9. Expose only the latest privacy-safe result through the authenticated,
   loopback-only read API.
10. Do not add an API endpoint that confirms or executes maintenance.

### Acceptance criteria

- Verified action and resolved finding are displayed as separate facts.
- A reboot-required run cannot appear resolved before reboot-aware comparison.
- Comparison tolerates missing sources and schema migrations.
- Support bundles contain no raw secret or unredacted personal path.
- API mutation-route validation remains unchanged and green.
- Home does not show a stale resolved finding as current.

### Verification

```bash
just test-file test_system_check_comparison
just test-file test_support_bundle_system_check
just test-file test_api_system_check
just test-file test_home_service
just test-file test_observability_privacy
just test-file test_api_security
just lint
just typecheck
```

### Checkpoint

```text
feat(system-check): show verified before-and-after outcomes
```

---

## Phase 6 — Accessibility, platform certification, and release

### Objective and user value

Ship v19 as a stable Fedora release with truthful platform claims and complete
regression evidence.

### Likely components

- `loofi-fedora-tweaks/version.py`
- `pyproject.toml`
- `loofi-fedora-tweaks.spec`
- `loofi-fedora-tweaks.metainfo.xml`
- `README.md`
- `ROADMAP.md`
- `ARCHITECTURE.md`
- `CHANGELOG.md`
- `docs/`
- `wiki/`
- `.github/workflows/`
- `.project-stats.json`
- release validation and screenshot scripts

### Tasks

1. Validate the real shell across widths, scaling, themes, keyboard, focus,
   AT-SPI, and screen-reader naming.
2. Capture real Home and System Check screenshots for empty, healthy, partial,
   actionable, awaiting-reboot, and resolved states.
3. Confirm that quick-check runtime stays within the Phase 0 per-collector
   budgets and does not block the UI.
4. Confirm cold-start performance remains inside the v18 release formula.
5. Run Traditional and Atomic Fedora certification against the latest stable
   release available at release-candidate time.
6. Promote Fedora 45 from preview only if:
   - upstream Fedora 45 is stable;
   - Traditional Fedora 45 installation and check/action flows pass;
   - Kinoite/Atomic Fedora 45 stages, reboots, and verifies a real deployment;
   - package, COPR, and documentation targets are synchronized.
7. Otherwise keep Fedora 44 stable and Fedora 45 preview-only. Do not block
   Steward on an unreleased Fedora schedule.
8. Run full tests, coverage, lint, typecheck, architecture, security, dependency,
   packaging, SBOM, provenance, and release-document gates.
9. Bump version and codename only after all local release gates pass.
10. Tag and publish only with separate explicit authorization and exact-commit
    readback.

### Acceptance criteria

- No P0 or P1 UI/accessibility defect remains in the canonical loop.
- Cold startup still creates one Home provider with zero subprocess probes,
  active hidden timers, and running QThreads.
- Coverage remains at least 86 percent with no changed-module regression.
- Zero finding-to-command paths exist outside Action Center.
- Zero unclassified host mutations exist.
- Every v18 route, alias, CLI compatibility command, and readable state schema
  passes regression tests.
- RPM, Flatpak, and sdist build and smoke tests pass.
- Platform support statements match independently recorded evidence.
- Version, codename, AppStream, RPM, Python metadata, docs, workflows, and
  release assets agree.

### Verification

```bash
just verify
just check-packaging
just validate-release
just stats-check
just check-drift
just build-rpm
just build-flatpak
just build-sdist
just release-prep
```

Required additional gates:

```bash
PYTHONPATH=loofi-fedora-tweaks python3 scripts/validate_product_contract.py
PYTHONPATH=loofi-fedora-tweaks python3 scripts/validate_architecture.py
PYTHONPATH=loofi-fedora-tweaks python3 scripts/validate_system_check_contract.py
QT_QPA_PLATFORM=offscreen PYTHONPATH=loofi-fedora-tweaks \
  python3 scripts/benchmark_startup.py --runs 10 --warmups 1
```

### Checkpoint

Use separate commits for final code fixes, release metadata, and publication
evidence. Do not tag from an intermediate commit.

Suggested final local release commit:

```text
release: prepare v19.0.0 Steward
```

---

## 7. Release gate

v19 is complete only when all conditions below are true.

### Product

- [ ] Home provides explicit Check now behavior for empty and stale states.
- [ ] One canonical System Check page owns findings and history.
- [ ] Existing health metrics remain available as supporting evidence.
- [ ] Finding explanations include evidence, source, timestamp, and freshness.
- [ ] Mapped findings open one exact audited Action Center action.
- [ ] Manual-only findings cannot execute.
- [ ] Before/after comparison distinguishes verified from resolved.

### Safety and data

- [ ] No command vector or executable callback is accepted from a finding.
- [ ] Apply regenerates commands and reruns preflight.
- [ ] No automatic confirmation, execution, reboot, retry, rollback, or resume.
- [ ] State migrations are atomic, read back, and preserve unknown future
      schemas as read-only.
- [ ] Existing snapshots, metrics, plans, runs, settings, favorites, and routes
      remain readable.
- [ ] Support and API output remains privacy-safe and bounded.

### Quality

- [ ] Full test suite passes.
- [ ] Coverage is at least 86 percent.
- [ ] Lint and mypy pass.
- [ ] Architecture and stabilization validators pass.
- [ ] Startup and check-duration budgets pass.
- [ ] Accessibility and responsive-shell matrices pass.
- [ ] Bandit, dependency audit, and CodeQL pass.
- [ ] RPM, Flatpak, and sdist build and smoke tests pass.
- [ ] SBOM, provenance, checksums, and exact-commit readback pass.

### Platform

- [ ] Latest claimed stable Fedora Traditional target is physically verified.
- [ ] Latest claimed stable Fedora Atomic target is physically verified.
- [ ] Preview targets remain clearly advisory until certified.
- [ ] No stale Fedora support claim exists in runtime, package metadata, docs,
      screenshots, or workflows.

---

## 8. Risks and open decisions

### Risk: a new model duplicates existing observability

Mitigation: `SystemCheckResult` must compose and adapt existing collectors and
stores. Phase 0 must reject any design that creates a third independent health
database.

### Risk: finding mappings become a second execution catalog

Mitigation: mappings contain only existing action IDs and closed parameters.
They cannot store commands, privileges, risk, verifier logic, or confirmation
policy.

### Risk: quick checks become slow or intrusive

Mitigation: keep the v19 quick profile closed, local, read-only, timeout-bounded,
cancellable, and explicitly user-started. Specialized scans remain separate.

### Risk: route consolidation breaks saved navigation

Mitigation: preserve all stable route IDs and aliases. Redirect or adapt
presentation; do not delete route contracts in v19.

### Risk: verified is confused with fixed

Mitigation: Action Center verification and later finding comparison use
different states and visible language.

### Risk: Fedora 45 timing changes

Mitigation: release against the latest upstream stable Fedora available at RC.
Promotion is evidence-driven and conditional, not hardcoded into early phases.

### Open decision after Phase 0

Decide whether finding context requires Action Center schema v4 or can be stored
in an existing extension-safe metadata field. Choose the smaller option only
after inspecting all v1-v3 migrations and digest rules. Finding context must
remain non-authoritative either way.

---

## 9. Work that must not be repeated

- Do not redesign the six-destination shell again.
- Do not replace the v16 component and theme systems.
- Do not rebuild the v18 Action Center execution boundary.
- Do not revive Marketplace, external executable plugins, remote mutation, or
  unattended agent execution.
- Do not split the RPM without new ownership and user-benefit evidence.
- Do not add another health page, history store, or parallel recommendation
  engine.
- Do not delete legacy routes or user data merely to simplify implementation.
- Do not bump version metadata before the release gate.

---

## 10. Recommended phase order and commits

| Phase | Commit after green gate |
| --- | --- |
| 0 | `docs(v19): lock Steward baseline and authority` |
| 1 | `feat(core): add canonical read-only system check domain` |
| 2 | `feat(home): add explicit asynchronous system check` |
| 3 | `feat(ui): consolidate system checks and health history` |
| 4 | `feat(actions): link findings to reviewed maintenance plans` |
| 5 | `feat(system-check): show verified before-and-after outcomes` |
| 6 | `release: prepare v19.0.0 Steward` |

Commit only when the phase-specific checks pass and the repository remains
runnable. Push completed checkpoints, not unfinished micro-steps.

---

## 11. Codex implementation handoff

Use Goal mode after this plan has been accepted:

```text
Inspect the repository and implement docs/plans/LOOFI_FEDORA_TWEAKS_V19_PLAN.md
one phase at a time. Start with Phase 0 and treat the current master branch,
AGENTS.md, ARCHITECTURE.md, the v18 release evidence, and existing tests as the
source of truth. Preserve all user changes, stable routes, persisted data,
Fedora Traditional/Atomic behavior, startup budgets, and the v18 Action Center
trust boundary.

Do not begin Phase 1 until the Phase 0 inventories, authority files, and gates
are complete. For each phase, inspect before editing, implement the smallest
coherent change, run the phase-specific checks, and stop on conflicting
evidence, data-migration uncertainty, or a failed release gate. After each
phase, report changed files, verification results, unresolved risks, deferred
work, and the proposed commit message. Do not tag or publish without separate
explicit authorization.
```
