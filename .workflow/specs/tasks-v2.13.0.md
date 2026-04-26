# Tasks — v2.13.0

- [ ] ID: TASK-001 | Files: `ROADMAP.md, .workflow/specs/.race-lock.json, .workflow/specs/tasks-v2.13.0.md, .workflow/specs/arch-v2.13.0.md` | Dep: - | Agent: project-coordinator | Description: Activate `v2.13.0` as the single active workflow target and scaffold canonical task/architecture contracts for a documentation/workflow convergence slice.
  Acceptance: `ROADMAP.md` contains exactly one active planning target for `v2.13.0`, race-lock points to `v2.13.0` with `status=active`, and canonical task/arch spec files exist.
  Docs: none
  Tests: `tests/test_workflow_runner_locks.py`

- [ ] ID: TASK-002 | Files: `README.md, docs/README.md, docs/releases/RELEASE_NOTES.md, docs/releases/RELEASE-NOTES-v2.12.0.md, ARCHITECTURE.md, .workflow/reports/` | Dep: TASK-001 | Agent: architecture-advisor | Description: Inventory authoritative documentation and workflow drift against `ROADMAP.md`, race-lock state, and actual repo artifacts.
  Acceptance: A bounded drift matrix identifies stale current-release references, stale architecture/version references, and any docs that cite nonexistent workflow artifacts.
  Docs: none
  Tests: `scripts/check_release_docs.py`

- [ ] ID: TASK-003 | Files: `README.md, docs/releases/RELEASE-NOTES-v2.12.0.md, loofi-fedora-tweaks/main.py` | Dep: TASK-002 | Agent: release-planner | Description: Reconcile the top-level README so its current-release section, badges, linked notes, and run-mode documentation reflect the verified post-`v2.12.0` state.
  Acceptance: `README.md` no longer advertises `v2.11.0`, and linked release notes and run-mode references match the actual app surface.
  Docs: `README.md`
  Tests: `tests/test_release_docs.py`

- [ ] ID: TASK-004 | Files: `docs/README.md, docs/releases/RELEASE_NOTES.md` | Dep: TASK-002 | Agent: release-planner | Description: Refresh documentation entrypoints so the docs index and latest-release index consistently point to the real latest release line and stop claiming outdated alignment.
  Acceptance: `docs/README.md` and `docs/releases/RELEASE_NOTES.md` agree on the current release family and no longer reference outdated releases as current.
  Docs: `docs/README.md, docs/releases/RELEASE_NOTES.md`
  Tests: `tests/test_release_docs.py`

- [ ] ID: TASK-005 | Files: `ARCHITECTURE.md` | Dep: TASK-002 | Agent: architecture-advisor | Description: Refresh the canonical architecture reference so its version banner, entry-mode count, and high-level structure reflect the current repository reality without changing runtime behavior.
  Acceptance: `ARCHITECTURE.md` no longer presents `2.4.0` as the active architecture snapshot, and its entry-mode statements match the actual app surface.
  Docs: `ARCHITECTURE.md`
  Tests: `tests/test_release_docs.py`

- [ ] ID: TASK-006 | Files: `.workflow/reports/run-manifest-v2.12.0.json, .workflow/reports/test-results-v2.12.0.json, docs/releases/RELEASE-NOTES-v2.12.0.md` | Dep: TASK-002 | Agent: backend-builder | Description: Reconcile the `v2.12.0` workflow-report mismatch by generating/backfilling canonical report artifacts from retained evidence where possible, or narrowing docs to verified facts if reconstruction is not possible.
  Acceptance: No release note in the repo references nonexistent `v2.12.0` workflow report files, and any restored report filenames use canonical `vX.Y.Z` naming only.
  Docs: `docs/releases/RELEASE-NOTES-v2.12.0.md`
  Tests: `tests/test_workflow_reports.py, scripts/check_release_docs.py`

- [ ] ID: TASK-007 | Files: `scripts/check_release_docs.py, scripts/generate_workflow_reports.py` | Dep: TASK-003, TASK-004, TASK-006 | Agent: backend-builder | Description: Harden validation scripts so stale current-release pointers, mismatched latest-release indexes, and doc references to missing workflow artifacts fail the release/documentation gate.
  Acceptance: Validation explicitly checks README/docs/release-index consistency and verifies the existence of any referenced workflow report files.
  Docs: none
  Tests: `tests/test_check_release_docs.py, tests/test_generate_workflow_reports.py`

- [ ] ID: TASK-008 | Files: `tests/test_release_docs.py, tests/test_check_release_docs.py, tests/test_workflow_runner_locks.py, tests/test_workflow_reports.py` | Dep: TASK-007 | Agent: test-writer | Description: Add focused regression coverage for documentation/workflow consistency rules using deterministic mocked inputs and fixture files only.
  Acceptance: Tests cover stale README versions, stale latest-release indexes, race-lock/roadmap mismatch, and missing report-file references.
  Docs: none
  Tests: `tests/test_release_docs.py, tests/test_check_release_docs.py, tests/test_workflow_reports.py`

- [ ] ID: TASK-009 | Files: `.workflow/reports/test-results-v2.13.0.json, .workflow/reports/run-manifest-v2.13.0.json` | Dep: TASK-008 | Agent: project-coordinator | Description: Generate canonical `v2.13.0` workflow report artifacts after validation for release-gate and closure compatibility.
  Acceptance: Both `v2.13.0` report files exist with canonical naming and reflect non-zero executed validation/tests for the slice.
  Docs: none
  Tests: `scripts/generate_workflow_reports.py, scripts/check_release_docs.py`

- [ ] ID: TASK-010 | Files: `CHANGELOG.md, README.md, docs/releases/RELEASE-NOTES-v2.13.0.md, ROADMAP.md` | Dep: TASK-009 | Agent: release-planner | Description: Publish verified `v2.13.0` release documentation and close the version in roadmap metadata after the convergence slice is fully validated.
  Acceptance: changelog, README, release notes, and roadmap status all align on `v2.13.0` with verified claims only and no dangling stale current-release references.
  Docs: `CHANGELOG.md, README.md, docs/releases/RELEASE-NOTES-v2.13.0.md, ROADMAP.md`
  Tests: `scripts/check_release_docs.py --require-logs`
