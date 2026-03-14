# Tasks — v2.10.0 "API Migration Slice 6 (Canonical Workflow + Next Migration Kickoff)"

**Date**: 2026-02-26  
**Status**: Complete  
**Arch Spec**: `arch-v2.10.0.md`

## Task List

---

### TASK001 — Canonicalize workflow artifact version tags

**ID**: TASK001  
**Status**: Complete  
**Files**: `scripts/workflow_runner.py`, `scripts/check_release_docs.py`, `scripts/generate_workflow_reports.py`, `tests/test_release_doc_check.py`, `tests/test_workflow_runner_locks.py`  
**Dep**: none  
**Agent**: backend-builder  
**Description**: Enforce canonical `vX.Y.Z` artifact naming in workflow/report utilities and align regression tests to the same behavior.  
**Acceptance**: scripts and tests no longer accept or emit short `vX.Y` artifact names for active release lines.  
**Docs**: update roadmap/workflow notes if references mention short tags  
**Tests**: targeted workflow script test suite

---

### TASK002 — Activate and verify v2.10.0 workflow state

**ID**: TASK002  
**Status**: Complete  
**Files**: `.workflow/specs/.race-lock.json`, `ROADMAP.md`, `.workflow/reports/run-manifest-v2.9.0.json`, `memory-bank/activeContext.md`, `memory-bank/progress.md`, `memory-bank/projectbrief.md`  
**Dep**: TASK001  
**Agent**: project-coordinator  
**Description**: Close v2.9.0 metadata state, activate v2.10.0 as canonical active version, and synchronize memory/workflow metadata.  
**Acceptance**: lock/roadmap/memory agree on v2.10.0 active and v2.9.0 done.  
**Docs**: roadmap + memory-bank synchronization  
**Tests**: `scripts/check_release_docs.py --require-logs` and workflow status check


### TASK003 — Define bounded Slice 6 migration targets

**ID**: TASK003  
**Status**: Complete  
**Files**: `.workflow/specs/arch-v2.10.0.md`, `loofi-fedora-tweaks/services/system/system.py`, `loofi-fedora-tweaks/services/network/network.py`, `loofi-fedora-tweaks/services/security/firewall.py`  
**Dep**: TASK002  
**Agent**: architecture-advisor  
**Description**: Produce a bounded inventory of remaining daemon/API-first residual pathways to migrate under v2.10.0 without privilege expansion.  
**Acceptance**: architecture spec documents prioritized method targets and compatibility constraints.  
**Docs**: architecture spec updates only  
**Tests**: N/A


### TASK004 — Add focused validation and regression coverage for v2.10 workflow baseline

**ID**: TASK004  
**Status**: Complete  
**Files**: `tests/test_release_doc_check.py`, `tests/test_workflow_runner_locks.py`, `tests/test_check_fedora_review.py`  
**Dep**: TASK001  
**Agent**: test-writer  
**Description**: Ensure workflow/tag normalization behaviors are validated and CI-facing checks stay deterministic.  
**Acceptance**: targeted tests pass with canonical tag expectations and no flaky short-tag coupling.  
**Docs**: none  
**Tests**: self
