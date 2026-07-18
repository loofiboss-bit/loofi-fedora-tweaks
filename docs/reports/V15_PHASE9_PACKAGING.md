# v15 Phase 9 Packaging and Component Decision

Date: 2026-07-18
Branch: `v15-essentials`
Decision: **NO-GO for a physical `loofi-fedora-tweaks-extras` RPM in v15**

## Scope and authority

This report closes only Phase 9 of
`docs/plans/LOOFI_FEDORA_TWEAKS_V15_PLAN.md`. The task classification and
protected contracts in `docs/reports/V15_PHASE0_BASELINE.md` are authoritative.
There is no version bump, release work, publication, or Phase 10 documentation
work in this phase.

Phase 9 implements logical component availability, verifies core-only runtime,
audits base dependencies, preserves the API and daemon package boundaries,
updates package descriptions, checks v14 state compatibility, and makes the
conditional extras decision. It does not change Action Center behavior or any
CLI, API, daemon, IPC, route, state-schema, or system-operation contract.

## Component and import evidence

Reproduction:

```bash
PYTHONPATH=loofi-fedora-tweaks \
python3 scripts/analyze_component_boundaries.py \
  --output /tmp/loofi-v15-phase9-components.json
```

The deterministic AST graph records:

| Measurement | Result |
| --- | ---: |
| Built-in plugin specifications | 28 |
| Core plugin entries | 17 |
| Specialist plugin entries | 11 |
| Project Python modules | 365 |
| Internal import edges | 910 |
| Core-reachable modules | 163 |
| Specialist-reachable modules | 153 |
| Shared core/specialist modules | 103 |
| Specialist-exclusive modules | 50 |
| Missing plugin entry modules | 0 |
| Direct core-plugin to specialist-entry edges | 0 |
| CLI reach into specialist-exclusive graph | 26 modules |
| API reach into specialist-exclusive graph | 9 modules |
| Daemon reach into specialist-exclusive graph | 11 modules |

The data-only plugin entry boundary is clean enough for lazy loading and for a
core-only runtime. It is not yet a complete RPM ownership boundary. CLI/API/
daemon contracts still reach capabilities that specialist plugins also use,
and 103 imported modules are shared by core and specialist plugin closures.

## Core-only runtime evidence

`tests/test_component_boundaries.py` copies the application tree, removes all
11 specialist plugin entry files, and runs both the component-contract smoke and
the reproducible offscreen Home startup benchmark against that copy.

The result is:

- installed component set: `core` only;
- all six Standard destinations have an available default route;
- all five canonical core workflows have an available preferred route;
- `maintenance:action-center` remains visible on Traditional and Atomic Fedora;
- meaningful Home renders with only `atlas_dashboard` instantiated;
- all 28 data-only plugin specifications remain registered;
- no specialist UI entry module is imported;
- no subprocess probe, mutation, or running `QThread` occurs.

At runtime, `MainWindow` now derives installed components from the complete set
of installed built-in module files. Navigation policy therefore fails closed
with its existing unavailable/explanation behavior when the specialist bundle
is absent or incomplete. Standard builds with all files preserve the existing
`core` plus `specialist` context.

## Dependency and package-description audit

The base RPM no longer requires `google-noto-color-emoji-fonts`. Phase 8 removed
ordinary emoji from built-in GUI labels and replaced them with packaged semantic
icons, so the font was no longer a core runtime requirement.

Python package metadata now keeps only PyQt6 in the base dependency list:

- unused `requests` was removed after a source-wide runtime import audit;
- `dbus-python` moved to a `daemon` optional dependency;
- the compatibility requirements file still includes API and daemon extras for
  CI and full-development environments.

The RPM spec already keeps `python3-dbus` in the daemon subpackage and the API
runtime libraries in the API subpackage. Both subpackages continue to require
the exact base EVR and keep their existing service-file ownership.

The RPM Summary/description and AppStream summary/description now lead with the
six-destination core control-center capability and identify development, AI,
virtualization, automation, and sharing as specialist Advanced-route tools. No
v15 release entry or version metadata was added.

## Section 17 extras go/no-go

| Criterion | Result | Evidence |
| --- | --- | --- |
| 1. Clean import/dependency boundaries | **Fail** | Plugin entries are isolated, but 103 modules are shared and CLI/API/daemon reach specialist-exclusive closures. |
| 2. Core completes six destinations and five workflows without specialist files | **Pass** | Core-only contract and offscreen Home smoke pass with all 11 specialist entry files removed. |
| 3. No cross-package import cycle | **Not proven** | A physical ownership map does not exist and protected non-GUI contracts still reach specialist capability modules. |
| 4. v14 settings/routes/history survive upgrade | **Pass at contract level** | Existing v14 settings migrate through compatibility adapters; v14 Action Center plans/runs/history load read-only without byte changes; protected state and Action Center sources remain unchanged from the v14 tag. |
| 5. Explicit non-overlapping RPM ownership | **Fail** | The base `%files` section owns the complete `%{_prefix}/lib/%{name}` tree and no specialist file manifest exists. |
| 6. Install/remove/reinstall smoke | **Not applicable** | There is intentionally no extras RPM to install or remove. |
| 7. COPR and Fedora review gates stay green | **Not proven for a split** | Existing unsplit Fedora gates are preserved; a new subpackage cannot be evaluated without ownership and upgrade work. |

The physical split is therefore a NO-GO. `V15-P9-006B` applies and
`V15-P9-006A` is `NOT_NEEDED`. v15 ships logical component isolation and true
on-demand specialist loading in the existing base RPM.

## v14 upgrade and state integrity

The integrated Phase 9 fixture covers v14 experience-level settings, legacy
route aliases, favorites, Action Center plan schema 1, run schema 1, history
schema 3, and State Doctor read-only validation. Current readers preserve plan,
run, and history bytes and retain a run waiting for explicit verification.

RPM scriptlets own no XDG user-state path and perform no user-state migration.
The Action Center contracts/stores/history and state/observability services are
unchanged relative to the v14 release tag.

A real `dnf upgrade` from EVR 14 to EVR 15 cannot be executed during Phase 9:
the plan explicitly forbids the version bump until Phase 10. The real Fedora 44
installed-package upgrade remains a blocking release gate rather than being
simulated with a false EVR.

## Compatibility preserved

- Action Center plan/run/verify, expiry, re-preflight, confirmation,
  no-rollback acknowledgement, lease, deny-by-default three-action catalog,
  history, and interrupted-run behavior are unchanged.
- Stable route IDs, aliases, favorites, navigation migrations, and the
  `maintenance:action-center` identity are unchanged.
- Traditional DNF and Atomic rpm-ostree/manual-only behavior are unchanged.
- State schemas, atomic I/O, backup/restore, observability, redaction, and
  Support Bundle contracts are unchanged.
- CLI, authenticated read-only API, daemon, and IPC contracts are unchanged.
- API and daemon RPM subpackages retain their names, exact base dependency,
  runtime dependencies, service files, and scriptlets.
- Version remains `14.0.0` in `version.py`, the RPM spec, and `pyproject.toml`.

## Verification

Targeted tests were run after each logical behavior slice:

- component discovery, core-only contract/startup, policy, search, and settings:
  41 passed;
- import graph analysis and deterministic JSON evidence: 2 passed, followed by
  5 passed for the completed core-only component slice;
- dependency metadata, RPM boundaries, AppStream descriptions, v14 state
  compatibility, Fedora readiness, release-doc contracts, and packaging
  manifest builds: 65 passed, followed by 17 packaging-script checks.

The isolated v14 regression groups passed:

- Action Center, CLI health, and maintenance UI: 219 passed;
- state, observability, and Support Bundle: 37 passed;
- navigation and plugin loading: 198 passed;
- release and package contracts: 61 passed;
- Traditional and Atomic behavior: 116 passed;
- CLI, API, daemon, and IPC: 103 passed;
- component, shell, and workflow contracts: 81 passed.

The complete coverage run passed with 7,616 tests, 40 skips, 616 subtests, and
86.12% coverage against the 85% gate. Release-document validation, agent drift,
packaging checks, Fedora readiness, the five-workflow no-probe validator, and
diff whitespace validation all passed.

Source lint passed with the repository virtual environment. Type checking found
only the four pre-existing Phase 8 findings in `ui/icon_pack.py`,
`utils/command_runner.py`, `ui/confirm_dialog.py`, and `ui/community_tab.py`; no
Phase 9 file introduced a type error.

The Fedora 44 RPM build passed `%check` and produced the unchanged three-package
surface: base (823,253 bytes), API (20,008 bytes), and daemon (20,038 bytes).
The API and daemon RPMs require the exact base EVR
`1:14.0.0-1.fc44`; the base RPM contains the component discovery module and no
XDG user-state path.

## v16 packaging follow-up

Before reconsidering a physical extras RPM:

1. Define file-level ownership for every specialist capability, not only its UI
   entry module.
2. Decouple or explicitly retain the specialist-adjacent CLI, API, and daemon
   contracts in the base package.
3. Resolve shared `services.*`, `core.*`, and `utils.*` imports without creating
   base-to-extras dependencies or import cycles.
4. Align the candidate list with component metadata, including Extensions.
5. Add non-overlap manifest checks plus install, remove, reinstall, downgrade,
   and v15-to-v16 upgrade smoke tests.
6. Run Fedora review, COPR, base-only, extras-installed, API, and daemon matrices.

## Deferred work

- Physical `loofi-fedora-tweaks-extras` RPM and its lifecycle tests: v16.
- A separate `-devel` RPM: beyond v15.
- Version bump, v15 release metadata, real EVR upgrade, final package install,
  screenshots, artifacts, publication, and public readback: Phase 10.
