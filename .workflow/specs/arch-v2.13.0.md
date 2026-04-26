# Architecture Spec — v2.13.0 "Alignment"

## Design Rationale

`v2.13.0` is a stabilization-only documentation/workflow convergence slice. After `v2.12.0`
completed the bounded daemon-first parity work, the highest-value next step is restoring a
single authoritative current-release story across roadmap metadata, workflow artifacts,
documentation entrypoints, and architecture references. This slice must not add new features,
expand privileges, or change runtime behavior except where validation-script correctness
requires it.

## Reviewed Inputs

- `ROADMAP.md`
- `.workflow/specs/.race-lock.json`
- `.workflow/specs/tasks-v2.12.0.md`
- `.workflow/specs/arch-v2.12.0.md`
- `README.md`
- `docs/README.md`
- `docs/releases/RELEASE_NOTES.md`
- `docs/releases/RELEASE-NOTES-v2.12.0.md`
- `ARCHITECTURE.md`
- `AGENTS.md`

## Scope

- TASK-001: activate `v2.13.0` workflow metadata and canonical planning artifacts.
- TASK-002: inventory authoritative release/doc/workflow drift.
- TASK-003/TASK-004: reconcile README and docs entrypoints with the real latest release line.
- TASK-005: refresh `ARCHITECTURE.md` statements to match the current app surface.
- TASK-006: resolve `v2.12.0` workflow-report reference drift with evidence-backed artifacts or narrower claims.
- TASK-007/TASK-008: harden validation scripts and add regression tests for documentation/workflow consistency.
- TASK-009/TASK-010: generate canonical `v2.13.0` workflow reports and close release metadata once validated.

## Non-Goals

1. No new UI tabs, CLI commands, or user-facing features.
2. No daemon/API surface expansion or privilege-model changes.
3. No broad rewrite of historical docs beyond authoritative entrypoints and directly referenced release artifacts.
4. No fabricated workflow evidence; if proof is missing, docs must be narrowed to verified claims.
5. No unrelated runtime refactors under the guise of “alignment”.

## Dependency Graph and Sequencing (Acyclic)

```text
TASK-001 -> TASK-002 -> {TASK-003, TASK-004, TASK-005, TASK-006}
{TASK-003, TASK-004, TASK-006} -> TASK-007 -> TASK-008 -> TASK-009 -> TASK-010
```

## Design Decisions

### D1 - Roadmap + race-lock stay authoritative

- **Layer**: workflow metadata
- **Files**: `ROADMAP.md`, `.workflow/specs/.race-lock.json`
- **Decision**: README/docs/release indexes consume the workflow truth; they do not maintain a parallel “current release” state.
- **Why**: release drift accumulates when entrypoint docs become an unsupervised second source of truth.

### D2 - Architecture refresh is documentation-first

- **Layer**: architecture reference
- **Files**: `ARCHITECTURE.md`
- **Decision**: update version/entry-mode/summary statements to match repository reality without using this slice for structural refactors.
- **Why**: the architecture doc is authoritative, but this slice is about restoring trust in docs, not redesigning the app.

### D3 - Workflow-report references must be evidence-backed

- **Layer**: workflow reports + release docs
- **Files**: `.workflow/reports/*.json`, `docs/releases/RELEASE-NOTES-v2.12.0.md`
- **Decision**: backfill `v2.12.0` report artifacts only from retained evidence; otherwise correct docs to verified claims instead of inventing files.
- **Why**: fabricated evidence is worse than explicit narrowing.

### D4 - Validation gets stricter, not noisier

- **Layer**: release/documentation validation scripts
- **Files**: `scripts/check_release_docs.py`, `scripts/generate_workflow_reports.py`
- **Decision**: add checks for stale latest-release references, cross-doc consistency, canonical `vX.Y.Z` naming, and existence of any referenced report artifacts.
- **Why**: preventing recurrence is the whole point of the slice.

### D5 - Regression coverage targets invariants, not prose

- **Layer**: tests
- **Files**: `tests/test_release_docs.py`, `tests/test_check_release_docs.py`, `tests/test_workflow_reports.py`, `tests/test_workflow_runner_locks.py`
- **Decision**: encode negative cases for stale versions, missing artifacts, and roadmap/race-lock mismatch using deterministic fixtures and mocks.
- **Why**: the gate should fail because authority drift is detected, not because someone remembers the lore.

## Risk Review and Mitigation

- **Risk R1**: scope creep into a general documentation rewrite.
  - **Mitigation**: touch only authoritative entrypoints and directly referenced release artifacts.
- **Risk R2**: incorrect reconstruction of missing `v2.12.0` workflow evidence.
  - **Mitigation**: restore only from retained logs/artifacts; otherwise narrow docs to verified facts.
- **Risk R3**: future drift reappears silently.
  - **Mitigation**: encode consistency checks in validation scripts and regression tests.

## Verification Outline

- `ROADMAP.md` and `.workflow/specs/.race-lock.json` agree on `v2.13.0` as the active slice.
- `README.md`, `docs/README.md`, `docs/releases/RELEASE_NOTES.md`, and `ARCHITECTURE.md` no longer contradict workflow truth.
- Any referenced `v2.12.0` workflow report file either exists or is no longer referenced.
- Validation scripts fail when release/doc/workflow drift is reintroduced.
- Regression tests cover negative cases for stale references and missing report artifacts.

## Blocking Concerns

The only known ambiguity is whether retained evidence exists to regenerate canonical `v2.12.0` workflow report artifacts. The slice is still unblocked because the fallback path is to narrow docs to verified claims rather than invent artifacts.
