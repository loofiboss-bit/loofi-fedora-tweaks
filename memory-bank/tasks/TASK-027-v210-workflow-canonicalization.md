# [TASK-027] - v2.10.0 workflow canonicalization and kickoff

**Status:** Completed  
**Added:** 2026-02-26  
**Updated:** 2026-02-26

## Original Request

Continue working on Fedora Tweaks and start implementation by closing v2.9.0, activating v2.10.0, and standardizing workflow artifacts to canonical `vX.Y.Z` naming.

## Thought Process

v2.9.0 implementation/release work is complete, but roadmap/race-lock/workflow artifacts had contradictory active state and mixed report naming (`vX.Y` vs `vX.Y.Z`). The safest continuation path is metadata reconciliation plus canonical tag normalization before beginning new migration code. This keeps workflow gates deterministic and prevents repeated release-doc mismatches.

## Implementation Plan

- Standardize workflow scripts to canonical `vX.Y.Z` tags only
- Align workflow-related tests with canonical tag behavior
- Close v2.9.0 metadata and activate v2.10.0
- Create v2.10.0 task/architecture contracts
- Run focused verification for updated scripts/tests

## Progress Tracking

**Overall Status:** Completed - 100%

### Subtasks

- **1.1** Canonicalize workflow scripts — **Complete** (2026-02-26)
  - Updated `check_release_docs.py`, `workflow_runner.py`, and `generate_workflow_reports.py`.
- **1.2** Align workflow script tests — **Complete** (2026-02-26)
  - Updated release-doc and workflow-runner lock tests.
- **1.3** Close v2.9.0 + activate v2.10.0 metadata — **Complete** (2026-02-26)
  - Roadmap/race-lock/memory updated and validated.
- **1.4** Create v2.10.0 tasks/arch specs — **Complete** (2026-02-26)
  - Added `tasks-v2.10.0.md` and `arch-v2.10.0.md`.
- **1.5** Run verification and finalize task state — **Complete** (2026-02-26)
  - Targeted tests and workflow checks passed.

## Progress Log

### 2026-02-26

- Standardized workflow script logic toward canonical `vX.Y.Z` tags.
- Updated workflow-related tests to reject short-tag-only artifacts.
- Updated roadmap/race-lock and memory-bank to mark v2.10.0 active and v2.9.0 done.
- Added v2.10.0 workflow contracts for next implementation slice.
- Seeded `.workflow/reports/run-manifest-v2.10.0.json` with completed plan/design phases.
- Verified focused suite passed (`34 passed`) and release-doc check returned `OK`.
- Added method-level bounded residual migration target inventory to `arch-v2.10.0.md` (network/firewall/system).
- Marked `TASK003` complete and advanced v2.10 run-manifest through `P3 BUILD`.
- Completed focused P4 regression run (`34 passed`) and generated `test-results-v2.10.0.json`.
- Advanced v2.10 run-manifest through `P4 TEST`.
- Completed P5 documentation sync (`CHANGELOG.md`, `README.md`, `RELEASE-NOTES-v2.10.0.md`).
- Advanced v2.10 run-manifest through `P5 DOC`.
