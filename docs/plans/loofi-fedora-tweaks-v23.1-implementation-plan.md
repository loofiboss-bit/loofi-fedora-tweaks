# Loofi Fedora Tweaks v23.1 Implementation Plan

## Codex execution brief

Implement a focused trust-and-usability release for Loofi Fedora Tweaks. The target is **v23.1.0**. Do not add a codename.

The release must close the remaining host-mutation boundary gaps, make active documentation match the shipped product, and simplify the five workflows users are most likely to need. Do not add new product areas, routes, providers, agents, marketplaces, or AI features.

Reviewed baseline:

- Repository: `loofiboss-bit/loofi-fedora-tweaks`
- Branch: `master`
- Reviewed commit: `5fe6ce486685df953c81e35a00dd0c7790f995f0`
- Current public version: `23.0.2`
- Product stack: Python 3.12+, PyQt6, Fedora KDE, Traditional and Atomic variants

Re-read the current branch before changing anything. If it has moved beyond the reviewed commit, preserve newer work and reconcile this plan with the current code. Never overwrite unrelated user changes.

## Outcome

At the end of this work:

1. Every public host-changing operation is created, reviewed, applied, and verified through Action Center.
2. Active documentation, metadata, screenshots, help text, and runtime copy describe the current v23 product.
3. Home, Updates, Install App, Troubleshoot, Cleanup, and Action Center form one understandable user journey.
4. KDE-native behavior and plain language replace unnecessary custom styling and internal architecture terminology.
5. The affected CLI and window setup code are easier to maintain without a framework rewrite.
6. All automated gates pass, followed by validation on a clean Fedora 44 KDE Wayland host.

## Working rules

Follow `AGENTS.md`, `ARCHITECTURE.md`, the current workflow specs, and the stabilization guide before editing.

- Use the `Justfile` as the primary command surface.
- Keep UI code in `ui/`; keep domain logic in `services/` and `core/`.
- Use `BaseTab`, `CommandRunner`, and `self.tr()` for user-facing GUI work.
- Never use `sudo`, `shell=True`, or a subprocess without a timeout.
- Use `pkexec` through `utils/commands.py` for privileged execution.
- Use `SystemManager.get_package_manager()` and support both Traditional and Atomic Fedora.
- Write new tests in the repository's `unittest` and `unittest.mock` style.
- Mock system calls, file I/O, OS probes, and network access in tests.
- Do not hardcode versions or codenames in tests.
- Do not bump versions manually. Use `scripts/bump_version.py` only in the release step.
- Do not commit, push, tag, publish, build in COPR, or create a GitHub release unless separately authorized.
- Keep each change small enough to review and verify independently.

## Product constraints

These are non-negotiable for v23.1:

- Keep the six current top-level destinations.
- Do not add routes or visible navigation entries.
- Do not introduce a new daemon, database, privileged API, or generic command runner.
- Do not add AI, agent, marketplace, provider, or GNOME expansion work.
- Do not rewrite the application in QML or Kirigami.
- Do not perform a repository-wide refactor or typing rewrite.
- Do not expose raw shell commands as Action Center definitions.
- Do not delete compatibility aliases without a deprecation path.
- Do not rewrite historical tags or old release records. Archive or label historical material instead.
- Do not use `v24.0.0`; that tag already exists. The intended release is `v23.1.0`.

## Anti-slop rules

- Every change must correspond to a finding, an acceptance criterion, or a failing test.
- Prefer improving an existing canonical file over adding another report, guide, or duplicate abstraction.
- Do not add phase names, model names, generated codenames, self-congratulatory comments, or implementation-history comments to runtime code.
- Remove stale comments such as “v25”, “v35”, “phase”, or “Hallmark” when they do not explain a current invariant.
- Do not leave TODOs, placeholders, speculative features, or empty UI panels in active user-facing work.
- User-facing text should say what the user can do and what will happen. Put diagnostic detail behind disclosure controls.
- Avoid generic names such as `manager`, `helper`, or `processor` when a domain-specific name is available.
- Do not create a new abstraction until at least two current call sites need the same behavior.
- Do not produce extra completion reports in the repository. Update the canonical changelog and release notes only when the work is ready.

## Phase 0 — Re-baseline and map the work

### 0.1 Confirm repository state

Before editing:

```bash
git status --short
git branch --show-current
git rev-parse HEAD
git log -1 --oneline
```

Read:

- `AGENTS.md`
- `ARCHITECTURE.md`
- `ROADMAP.md`
- `docs/README.md`
- `.github/instructions/system_hardening_and_stabilization_guide.md`
- `.github/instructions/test.instructions.md`
- `.workflow/specs/.race-lock.json`
- the current release's task and architecture specs, if present

Stop if a race lock or active workflow makes the target ambiguous.

### 0.2 Establish a passing baseline

Run the cheapest deterministic gates first:

```bash
PYTHONPATH=loofi-fedora-tweaks python3 scripts/validate_architecture.py
PYTHONPATH=loofi-fedora-tweaks python3 scripts/check_stabilization_rules.py
PYTHONPATH=loofi-fedora-tweaks python3 scripts/validate_product_contract.py
just lint
just typecheck
```

Then run the relevant Action Center, CLI, Home, Troubleshoot, Settings, and architecture tests. Run the full suite when dependencies are available.

Record existing failures in the work log. Do not mix unrelated pre-existing failures into v23.1 changes.

### 0.3 Produce the mutation inventory

Create one machine-readable registry in the existing product-contract or safety-contract area. Do not create a second competing source of truth.

Classify every public CLI and API operation as exactly one of:

- `read_only`
- `plan_only`
- `manual_only`
- `mutating`

For every `mutating` operation, record:

- public command or endpoint
- domain owner
- Action Center definition ID
- privilege requirement
- Traditional Fedora behavior
- Atomic Fedora behavior
- confirmation requirement
- verification/readback method
- rollback or recovery guidance
- compatibility alias, if any

Inventory at least:

- tuner apply operations
- service start, stop, restart, enable, disable, mask, and unmask
- firewall port open and close
- display and fractional-scaling changes
- boot timeout and boot configuration apply operations
- backup restore and delete
- snapshot operations
- extension operations
- Flatpak install, remove, and update operations
- package and system update operations
- cleanup operations
- self-update operations
- any Bluetooth, storage, hardware, plugin, or agent command that changes host state

### Phase 0 acceptance

- The reviewed baseline is reproducible.
- Every public command and endpoint has one classification.
- Every mutating entry has an owner and a verification method.
- Any discrepancy between architecture claims and current behavior is visible in the inventory.

## Phase 1 — Close the host-mutation boundary

This phase is P0. Do not begin visual polish until it is complete.

### 1.1 Make Action Center the only mutation authority

Public handlers may:

- inspect state;
- validate arguments;
- create a closed Action Center plan;
- return a plan ID and summary;
- query or render plan status.

Public handlers must not:

- execute a privileged command directly;
- call `run_operation()` or an equivalent mutation method directly;
- bypass review or verification;
- construct an arbitrary shell-command plan;
- auto-apply a newly created plan.

Use the existing Action Center model, definition catalog, assurance, migration, and verification paths. Add domain definitions only when the operation can be represented as a closed, validated action with deterministic parameters and readback.

If a safe definition does not exist:

1. classify the operation as `manual_only`;
2. return clear manual guidance or route the user to the relevant UI;
3. do not preserve unsafe direct mutation merely for compatibility.

### 1.2 Convert CLI mutation paths

Inspect and update:

- `loofi-fedora-tweaks/cli/main.py`
- `loofi-fedora-tweaks/cli/commands/service_package_commands.py`
- `loofi-fedora-tweaks/cli/commands/firewall_commands.py`
- `loofi-fedora-tweaks/cli/commands/tuning_commands.py`
- `loofi-fedora-tweaks/cli/commands/update_commands.py`
- other command modules identified by the inventory

For each public legacy mutation command:

1. retain the existing parse shape when practical;
2. validate the same user input;
3. create an Action Center plan;
4. print a concise human summary by default;
5. return stable structured data under JSON output, including the plan ID, state, definition ID, review requirement, and next action;
6. exit successfully when the plan was created successfully;
7. never apply the plan as a side effect.

If behavior must change incompatibly, add an explicit deprecation message and document the migration.

### 1.3 Convert API mutation paths

Inspect all API routes, not only `api/routes/action_center.py`.

- Read-only endpoints may remain read-only.
- Mutation requests must create or operate on Action Center plans.
- Reject arbitrary commands and unknown definition IDs.
- Preserve authentication, authorization, confirmation, and audit behavior.
- Do not create a parallel API-specific mutation engine.

### 1.4 Strengthen the boundary test

Extend `tests/test_v20_mutation_boundary.py` or replace its implementation while preserving it as the canonical boundary gate.

The test must fail if a public CLI or API handler:

- imports a known privileged execution helper outside approved Action Center modules;
- calls a known direct mutation service;
- invokes `subprocess`, `pkexec`, package managers, `systemctl`, `firewall-cmd`, `flatpak`, or equivalent execution from a public handler;
- creates an open-ended command definition;
- creates and applies a plan in the same public request.

Use a small allowlist of explicit, reviewed modules. Avoid a broad directory allowlist.

Add behavioral tests for:

- human CLI output;
- JSON CLI output;
- plan creation without execution;
- invalid parameter rejection;
- unknown definition rejection;
- Traditional Fedora;
- Atomic Fedora;
- verification/readback;
- compatibility aliases;
- API plan creation;
- manual-only fallbacks.

### 1.5 Update architecture claims

After the boundary is true in code, update `ARCHITECTURE.md`, CLI docs, API docs, and the product contract. Do not weaken the architecture wording to accommodate unsafe paths.

### Phase 1 acceptance

- Mutation inventory reports zero public direct host mutations.
- Every public mutating request produces a reviewed plan or safe manual guidance.
- Legacy aliases return plan IDs and do not auto-apply.
- Boundary tests fail on an intentionally introduced direct mutation.
- Action Center verification/readback is tested for each migrated domain.
- Traditional and Atomic Fedora behaviors are both covered.

## Phase 2 — Make the product tell the truth

### 2.1 Fix active metadata and copy

Correct the device-specific desktop metadata:

- Replace `System tweaks and maintenance for HP Elitebook 840 G8` in `loofi-fedora-tweaks.desktop` with durable product copy.

Audit active user-facing text for:

- old versions;
- obsolete wizard flows;
- retired Advanced routes;
- direct-mutation CLI examples;
- internal phase terminology;
- unsupported product claims;
- TODO placeholders;
- copied release language that no longer helps the user.

### 2.2 Establish one documentation source of truth

Use:

- `README.md` for product overview and quick start;
- `docs/README.md` for the documentation map;
- `CONTRIBUTING.md` for contributor workflow;
- `docs/TROUBLESHOOTING.md` for operational help;
- `CHANGELOG.md` and `docs/releases/` for release history.

Choose one canonical source for content mirrored into `wiki/`. Generate or validate mirrors in CI instead of maintaining two divergent copies manually.

Update or replace obsolete content in `wiki/Getting-Started.md`, including:

- the obsolete five-step wizard;
- stale JSON examples;
- old Advanced-mode navigation;
- direct CLI mutation examples.

The actual welcome wizard is a safe one-page introduction. Documentation must show that behavior.

### 2.3 Archive historical material cleanly

- Move superseded implementation reports and release-planning documents out of active navigation.
- Keep historical files available under a clearly named archive when they have lasting value.
- Remove exact-content duplicates, especially duplicated screenshots, only after confirming no active link depends on them.
- Do not edit Git tags or rewrite released history.
- Do not create a new “cleanup report”.

### 2.4 Remove runtime AI residue

Remove non-informative generated comments and labels from active code and stylesheets, including the `Hallmark · pre-emit critique...` text in `base.qss`.

Keep comments that explain:

- safety invariants;
- non-obvious Fedora differences;
- compatibility constraints;
- why a workaround is still necessary.

Convert version- or phase-based comments into statements of the current invariant.

### 2.5 Add documentation gates

Add or extend deterministic checks for:

- the canonical current version source;
- stale active version strings;
- device-specific product metadata;
- TODO or placeholder text in active release documentation;
- documented CLI examples that fail to parse;
- broken internal links;
- wiki drift;
- screenshots referenced but missing;
- visible routes that the product contract marks retired.

Do not scan archives with rules intended for active documentation.

### 2.6 Refresh screenshots

Capture real Fedora 44 KDE Wayland screenshots after Phase 3 UI work:

- Home
- Updates
- Install App
- Troubleshoot
- Cleanup
- Action Center with a meaningful non-destructive example plan

Requirements:

- current product copy and version;
- no mock data presented as real state;
- no personal hostnames, usernames, IP addresses, package history, or unique identifiers;
- consistent window size;
- both standard and high-DPI legibility checked;
- README includes one strong product screenshot near the overview.

### Phase 2 acceptance

- Active documentation contains no obsolete product flow or direct-mutation example.
- Active docs contain no old version, TODO, device-specific metadata, or unexplained phase labels.
- Wiki drift is prevented automatically.
- Retired routes do not appear in active navigation or getting-started content.
- README shows the current product.
- Historical material remains available without competing with current guidance.

## Phase 3 — Simplify the core user experience

Limit UI work to the existing shell and the six core workflows. Preserve lazy loading and current plugin boundaries.

### 3.1 Home

Goal: tell the user what is healthy, what needs attention, and what to do next.

- Replace repeated “Status unavailable” cards with one calm empty or unavailable state.
- Show no more than one primary recommendation at a time.
- Keep common tasks visible: check updates, install an app, troubleshoot a problem, free space, review planned changes.
- Use plain labels and one-sentence supporting text.
- Distinguish “not checked yet” from “check failed”.
- Do not manufacture health scores when evidence is incomplete.

### 3.2 Updates and Install App

- Make state and next action obvious before showing package-manager detail.
- Explain Traditional versus Atomic behavior only when it changes the user's next step.
- Route all changes to an Action Center plan.
- Show planned packages, source, restart requirement, and verification outcome.
- Preserve useful search and filtering; remove secondary copy that repeats labels.

### 3.3 Troubleshoot

Lead with symptoms, not internal architecture.

Suggested symptom entry points:

- No internet
- Sound is not working
- Bluetooth is not working
- Updates failed
- An app will not start
- The system feels slow
- Storage is full
- Something else

Move terms such as evidence quality, freshness, source ownership, schema, correlation, and bounded execution into an expandable technical-details section where they are genuinely useful.

Every result must distinguish:

- what was checked;
- what was found;
- confidence or missing evidence;
- safe next action;
- whether the next action creates an Action Center plan.

### 3.4 Cleanup

- Preview what will be removed and estimated reclaimable space.
- Separate safe defaults from advanced choices.
- Never preselect destructive or hard-to-recover categories.
- Create a plan before mutation.
- Verify reclaimed space and report partial failures accurately.

### 3.5 Action Center

Change the primary presentation from form-like controls and empty panes to a state-led work list:

- Needs review
- Ready
- Running
- Waiting for restart
- Completed
- Failed

Show plan details after selection. The summary should prioritize:

- intended outcome;
- affected components;
- privilege requirement;
- restart requirement;
- verification;
- rollback or recovery guidance.

Keep definition selectors and developer-oriented metadata out of the default user flow. They may remain in an advanced or diagnostic surface if required.

### 3.6 Settings and shell

- Constrain Settings content to a readable form width of roughly 640–720 device-independent pixels.
- Use consistent form rows and native spacing instead of filling the entire canvas.
- Remove the version from the main window title; keep it in About and diagnostic output.
- Prefer `QIcon.fromTheme()` with current custom icons as fallback.
- Reduce custom QSS only where native Plasma behavior now covers the requirement.
- Preserve semantic design tokens, high contrast, keyboard focus, RTL, and responsive behavior.

Do not replace the complete stylesheet in one change.

### 3.7 UI verification

Add focused tests for:

- the consolidated Home unavailable state;
- recommendation priority;
- symptom-first Troubleshoot navigation;
- Action Center state grouping;
- Settings maximum content width;
- window title;
- theme icon fallback;
- keyboard focus order;
- translated and RTL strings;
- 860-pixel-wide responsive layout;
- 100% and 140% scaling assumptions;
- high-contrast visibility.

Use screenshots for human review, not as the sole automated assertion.

### Phase 3 acceptance

- A new user can reach each core workflow from Home or in no more than two navigation actions.
- No core page opens as an unexplained blank canvas.
- Host-changing actions visibly become plans before execution.
- Default Troubleshoot copy contains no unexplained architecture jargon.
- Action Center is understandable without knowing definition IDs.
- Settings remains readable at wide and narrow supported window sizes.
- Keyboard-only, high-contrast, RTL, 100%, and 140% checks pass.

## Phase 4 — Reduce maintenance risk in touched areas

This is a constrained refactor. It must not delay the safety and UX outcomes.

### 4.1 Split CLI parser registration

`cli/main.py` currently has an oversized parser builder. Split registration into domain-owned functions or modules while preserving:

- command names;
- aliases;
- help order where users depend on it;
- defaults;
- JSON behavior;
- exit codes.

The root parser should compose domain registrations and contain no domain mutation logic.

Add parser snapshot or parse-contract tests for the public command surface.

### 4.2 Split MainWindow initialization

Reduce `ui/main_window.py` initialization into named responsibilities, for example:

- shell construction;
- navigation registration;
- lazy-page wiring;
- shared service construction;
- persisted-state restoration;
- accessibility and responsive setup.

Do not change startup order accidentally. Preserve lazy page creation and avoid new eager system probes.

### 4.3 Refactor only affected large functions

When a Phase 1–3 change touches a function over roughly 80 lines:

- extract domain-specific validation, mapping, or presentation functions;
- keep side effects at the boundary;
- add tests before changing behavior;
- stop once the modified path is clear and testable.

Do not reformat or reorganize unrelated modules.

### 4.4 Improve typing at the changed boundaries

Add useful types to new and modified public functions, plan payloads, and result models. Avoid repository-wide annotation churn.

### Phase 4 acceptance

- CLI parser registration is domain-separated and compatibility-tested.
- MainWindow initialization has clear named responsibilities.
- No new oversized handler is introduced.
- Lazy startup behavior is preserved.
- Lint and typecheck pass without new suppressions that hide real errors.

## Phase 5 — Integrated validation and release readiness

### 5.1 Automated validation

Run:

```bash
just lint
just typecheck
PYTHONPATH=loofi-fedora-tweaks python3 scripts/validate_architecture.py
PYTHONPATH=loofi-fedora-tweaks python3 scripts/check_stabilization_rules.py
PYTHONPATH=loofi-fedora-tweaks python3 scripts/validate_product_contract.py
just check-drift
just test
just test-coverage
just validate-release
just build-rpm
```

Run focused tests after each phase rather than waiting for the full suite.

Do not lower coverage thresholds, remove tests, expand broad allowlists, or add skips merely to make the gates pass.

### 5.2 Physical-host validation

Validate the built RPM on a clean Fedora 44 KDE Wayland host:

- fresh install;
- first launch;
- one-page welcome;
- all six top-level destinations;
- Home unavailable and healthy states;
- update inspection and plan creation;
- app search and install plan creation;
- each Troubleshoot symptom entry;
- Cleanup preview and plan creation;
- Action Center review, apply, verify, failure, and restart states;
- keyboard-only navigation;
- screen-reader labels;
- high-contrast theme;
- 100% and 140% scaling;
- desktop file and application launcher metadata;
- daemon readback where supported.

Validate Traditional Fedora behavior. Validate Atomic behavior on a real Atomic host, or narrow product claims if that environment cannot be tested.

### 5.3 Release metadata

Only after all acceptance criteria pass and release authorization is explicit:

1. run `scripts/bump_version.py` for `23.1.0`;
2. verify synchronization across `version.py`, the RPM spec, and `pyproject.toml`;
3. write concise release notes organized by user outcome;
4. update `CHANGELOG.md`;
5. rerun all release validation;
6. build final artifacts from the exact release commit.

Do not create a tag, GitHub release, COPR build, or public announcement as part of this plan unless the user explicitly asks for release execution.

## Suggested pull-request sequence

Keep the work reviewable in this order:

1. **Mutation inventory and enforcement test**
2. **CLI and API migration to Action Center**
3. **Documentation truth and metadata cleanup**
4. **Home, Updates, and Install App simplification**
5. **Troubleshoot and Cleanup simplification**
6. **Action Center, Settings, and shell polish**
7. **Parser and MainWindow extraction**
8. **Screenshots, integrated validation, and release metadata**

Each pull request should:

- have one primary outcome;
- include focused tests;
- list Traditional and Atomic impact;
- state whether it changes a public CLI or API contract;
- avoid unrelated formatting changes;
- include before/after screenshots only for visible UI changes.

## Release definition of done

All boxes must be true:

- [ ] Zero public host mutations occur outside Action Center.
- [ ] Every mutating CLI and API path returns a plan or safe manual guidance.
- [ ] No new plan can contain an arbitrary shell command.
- [ ] Compatibility aliases do not auto-apply.
- [ ] Traditional and Atomic behavior is explicit and tested.
- [ ] Active docs match the current wizard, navigation, CLI, and product contract.
- [ ] Active docs contain no stale version, TODO, device-specific metadata, or generated phase residue.
- [ ] Retired features are absent from visible navigation and current onboarding.
- [ ] README contains current, privacy-safe product screenshots.
- [ ] The five core tasks are reachable from Home or within two navigation actions.
- [ ] Home has one coherent unavailable state.
- [ ] Troubleshoot is symptom-first and uses plain language.
- [ ] Action Center is state-led and explains review, restart, verification, and failure.
- [ ] Settings uses a readable form width.
- [ ] Window title and icons follow KDE conventions.
- [ ] Architecture, stabilization, product-contract, drift, lint, and type gates pass.
- [ ] Full tests and coverage gates pass without weakened thresholds.
- [ ] RPM builds and installs cleanly.
- [ ] Fedora 44 KDE Wayland validation passes at 100% and 140% scaling.
- [ ] Keyboard-only, screen-reader-label, high-contrast, and RTL checks pass.
- [ ] Version metadata remains unchanged until release authorization.

## Stop conditions

Stop and report before proceeding if:

- current branch changes conflict with the reviewed architecture;
- a race lock or active workflow owns the same files;
- a mutation cannot be represented as a closed, validated Action Center definition;
- preserving compatibility would require silent direct mutation;
- Atomic behavior cannot be made safe or truthfully verified;
- a requested UI change requires a framework rewrite;
- a test can pass only by weakening a safety gate;
- release work would require credentials, publishing, tagging, or external writes not explicitly authorized.

## Codex handoff format

After each phase, report:

1. user-visible outcome;
2. files changed;
3. public contract changes;
4. tests and validators run, with results;
5. remaining risks or blockers;
6. the next phase, but do not begin it if a stop condition applies.

At completion, provide one concise summary and the exact commands needed for any validation that could not be run locally. Do not claim Fedora host, Wayland, scaling, accessibility, RPM installation, signing, COPR, or release validation unless it actually ran.
