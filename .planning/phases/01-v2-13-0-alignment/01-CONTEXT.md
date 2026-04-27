# Phase 1: v2.13.0 Alignment - Context

**Gathered:** 2026-04-10
**Status:** Ready for planning

<domain>
## Phase Boundary

Close the active `v2.13.0 "Alignment"` stabilization slice by reconciling release/documentation/workflow drift only. This phase does not add product features, does not expand privilege scope, and does not rename runtime flags unless validation-script correctness explicitly requires it.

</domain>

<decisions>
## Implementation Decisions

### Release truth model
- Treat these as separate facts and present them separately in docs:
  - Active workflow target: `v2.13.0 "Alignment"` from top-level `ROADMAP.md` and `.workflow/specs/.race-lock.json`
  - Latest completed documented release line: `v2.12.0 "API Migration Slice 8"` from `CHANGELOG.md` and `docs/releases/RELEASE-NOTES-v2.12.0.md`
  - Packaged/runtime version files: `2.11.0` from `loofi-fedora-tweaks/version.py`, `pyproject.toml`, and `loofi-fedora-tweaks.spec`
- Do not collapse those three facts into a single "current release" label.

### Command-surface truth
- The runnable headless API flag is `--web` because `loofi-fedora-tweaks/main.py` and `loofi-fedora-tweaks.service` expose `--web` today.
- Do not rename docs or code to `--api` in this slice; only remove stale conflicting references.

### Workflow evidence policy
- Never fabricate `v2.12.0` workflow report files.
- If retained evidence cannot produce canonical `v2.12.0` artifacts, narrow the release note claims and remove direct file-path assertions.
- To close `v2.13.0`, prefer script support that can generate canonical report filenames for a target version rather than hand-written JSON.

### Validation policy
- `scripts/check_release_docs.py` must catch stale release pointers and any doc references to missing `.workflow/reports/*.json` files.
- Regression tests must use deterministic fixture files and mocked inputs only.

### Claude's Discretion
- Exact wording and section placement inside docs
- The most maintainable helper names and internal parser structure for validation scripts

</decisions>

<specifics>
## Specific Ideas

- Observed drift at planning time:
  - `README.md` still brands the repo as `v2.11.0`
  - `docs/releases/RELEASE_NOTES.md` still points to `v45.0.0`
  - `ARCHITECTURE.md` still shows `2.4.0` and `Three Entry Modes`
  - `docs/releases/RELEASE-NOTES-v2.12.0.md` references missing `.workflow/reports/test-results-v2.12.0.json` and `run-manifest-v2.12.0.json`
  - `scripts/check_release_docs.py` reports OK for current runtime docs while these broader drifts remain

</specifics>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Workflow truth
- `ROADMAP.md` — authoritative repo roadmap with active `v2.13.0` slice
- `.workflow/specs/.race-lock.json` — active workflow target lock
- `.workflow/specs/tasks-v2.13.0.md` — bounded task contracts for the alignment slice
- `.workflow/specs/arch-v2.13.0.md` — design rationale and sequencing for the slice

### Release/documentation state
- `README.md` — top-level entrypoint with stale v2.11.0 release branding
- `docs/README.md` — docs index entrypoint
- `docs/releases/RELEASE_NOTES.md` — canonical latest-release index with stale `v45.0.0` pointer
- `docs/releases/RELEASE-NOTES-v2.12.0.md` — latest documented slice note with missing report-file claims
- `CHANGELOG.md` — latest changelog entry already at `2.12.0`
- `ARCHITECTURE.md` — stale architecture banner and entry-mode section

### Runtime truth
- `loofi-fedora-tweaks/main.py` — actual CLI flags (`--cli`, `--daemon`, `--web`)
- `loofi-fedora-tweaks.service` — deployed service ExecStart uses `--web`
- `loofi-fedora-tweaks/version.py` — packaged runtime version `2.11.0`
- `pyproject.toml` — packaged runtime version `2.11.0`
- `loofi-fedora-tweaks.spec` — packaged runtime version `2.11.0`

### Validation/test hooks
- `scripts/check_release_docs.py` — current release-doc gate; must be hardened
- `scripts/generate_workflow_reports.py` — current workflow-report generator; currently tied to runtime version file
- `tests/test_release_doc_check.py` — existing release-doc check regression coverage
- `tests/test_generate_workflow_reports.py` — existing workflow-report generator tests
- `tests/test_workflow_runner_locks.py` — race-lock/workflow contract tests
- `tests/test_main_entry.py` — current command-surface tests for `--web`

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `scripts/check_release_docs.py`: already handles version-sync, release-note existence, and optional workflow-artifact checks; extend it rather than adding a parallel validator.
- `scripts/generate_workflow_reports.py`: already writes canonical `test-results-vX.Y.Z.json` and `run-manifest-vX.Y.Z.json` payloads for the current runtime version.
- `tests/test_release_doc_check.py` / `tests/test_generate_workflow_reports.py`: existing fixture-driven tests can absorb new edge cases without introducing system dependencies.

### Established Patterns
- Workflow/report filenames are canonical `vX.Y.Z`, not short tags.
- Documentation claims must be evidence-backed; if proof is missing, docs narrow rather than invent.
- Test updates should stay deterministic and rootless.

### Integration Points
- README/docs entrypoints must consume the repo's workflow truth, not invent their own.
- Release-document validation must cover both direct artifacts and any file-path claims embedded in release notes.
- Final `v2.13.0` closure depends on generating or validating canonical workflow-report artifacts for that slice.

</code_context>

<deferred>
## Deferred Ideas

- Renaming the Web API flag from `--web` to `--api`
- Broad cleanup of non-authoritative historical docs, wiki pages, or memory-bank files outside the bounded slice
- Runtime/version-file bump beyond the current packaged baseline until the release packaging phase is explicitly scheduled

</deferred>

---

*Phase: 01-v2-13-0-alignment*
*Context gathered: 2026-04-10*
