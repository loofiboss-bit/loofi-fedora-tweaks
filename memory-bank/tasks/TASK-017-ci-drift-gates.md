# TASK-017 - CI Drift Gates Hardening

**Status:** Completed
**Added:** 2026-02-22
**Updated:** 2026-02-22

## Original Request

Ensure stats/adapter drift checks are blocking and actionable in CI.

## Thought Process

Non-blocking drift checks silently allow repository state divergence. CI should fail with clear diagnostics when generated artifacts are stale.

## Implementation Plan

- Review CI workflow drift checks and blocking behavior
- Remove non-blocking tolerances for required drift gates
- Add/update workflow contract tests to protect behavior

## Progress Tracking

**Overall Status:** Completed - 100%

### Subtasks

| ID | Description | Status | Updated | Notes |
| --- | --- | --- | --- | --- |
| 17.1 | Audit existing drift checks | Complete | 2026-02-22 | Confirmed adapter and stats checks are required CI jobs |
| 17.2 | Enforce blocking policy | Complete | 2026-02-22 | Removed `continue-on-error: true` from `package_flatpak` |
| 17.3 | Update workflow tests | Complete | 2026-02-22 | Added CI contract assertions for drift/flatpak gate behavior |

## Progress Log

### 2026-02-22

- Task created for CI hardening follow-up.
- Updated CI workflow to keep drift gates blocking and package job strict.
- Added workflow contract tests and verified focused test suite pass.
