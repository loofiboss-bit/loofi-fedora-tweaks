# Task Spec — v2.1.0 "Continuity"

## Tasks

### TASK-001: Activate v2.1.0 workflow cycle

- **ID:** TASK-001
- **Files:** `ROADMAP.md`, `.workflow/specs/.race-lock.json`, `.workflow/specs/tasks-v2.1.0.md`, `.workflow/specs/arch-v2.1.0.md`
- **Dep:** none
- **Agent:** code-implementer
- **Description:** Open the new ACTIVE version and initialize mandatory workflow specs
- **Acceptance:** v2.1.0 is ACTIVE in roadmap and race lock; v2.1 task/arch specs exist
- **Docs:** ROADMAP.md
- **Tests:** Workflow contract parsing succeeds for v2.1.0 specs
- **Status:** ✅ DONE

### TASK-002: Reconcile memory-bank continuation state

- **ID:** TASK-002
- **Files:** `memory-bank/activeContext.md`, `memory-bank/progress.md`, `memory-bank/tasks/_index.md`
- **Dep:** TASK-001
- **Agent:** code-implementer
- **Description:** Align memory-bank with active v2.1.0 state and remove stale release-closure notes
- **Acceptance:** Memory bank consistently reflects v2.1.0 active continuation
- **Docs:** memory-bank/*
- **Tests:** N/A (documentation/state artifacts)
- **Status:** ✅ DONE

### TASK-003: Reconcile self-maintaining tracker with canonical workflow

- **ID:** TASK-003
- **Files:** `.self-maintaining-progress.md`
- **Dep:** TASK-002
- **Agent:** code-implementer
- **Description:** Update self-maintaining tracker to match current repository path, active version, and authoritative workflow sources
- **Acceptance:** Tracker no longer conflicts with roadmap/race-lock and has an explicit v2.1 continuation status
- **Docs:** `.self-maintaining-progress.md`
- **Tests:** N/A (documentation/state artifacts)
- **Status:** ✅ DONE

### TASK-004: Implement adapter sync smart re-render

- **ID:** TASK-004
- **Files:** `scripts/sync_ai_adapters.py`
- **Dep:** TASK-003
- **Agent:** backend-builder
- **Description:** Add old→new stat-aware smart value replacement for renderable files using previous/current stats snapshots
- **Acceptance:** Stat drift values in renderable files are auto-updated without template placeholders in committed files
- **Docs:** `AGENTS.md`, `.github/instructions/primary.instructions.md` (if behavior changes)
- **Tests:** Add/extend script tests for stat replacement behavior
- **Status:** ✅ DONE

### TASK-005: Integrate previous-stats snapshot into version bump pipeline

- **ID:** TASK-005
- **Files:** `scripts/bump_version.py`, `scripts/project_stats.py`, `scripts/sync_ai_adapters.py`
- **Dep:** TASK-004
- **Agent:** backend-builder
- **Description:** Persist previous stats before regeneration and run adapter render flow as part of version bump cascade
- **Acceptance:** Version bump updates stats and adapter-rendered files in one deterministic flow
- **Docs:** `README.md` or workflow docs for release automation
- **Tests:** Add/extend tests for bump pipeline integration path
- **Status:** ✅ DONE

### TASK-006: Harden CI gates for adapter/stats drift

- **ID:** TASK-006
- **Files:** `.github/workflows/ci.yml`, related workflow docs/tests
- **Dep:** TASK-005
- **Agent:** test-writer
- **Description:** Ensure adapter/stats drift checks are blocking and package workflow error tolerance is policy-compliant
- **Acceptance:** CI fails on drift and reports actionable diagnostics
- **Docs:** `CHANGELOG.md`, workflow docs if behavior changes
- **Tests:** Workflow contract/regression tests updated
- **Status:** ✅ DONE

