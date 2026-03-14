# Tasks — v2.6.0 "API Migration Slice 2 (Packages)"

**Date**: 2026-02-25  
**Status**: Complete  
**Arch Spec**: `arch-v2.6.0.md`

## Task List

---

### TASK001 — Activate v2.6.0 workflow cycle

**ID**: TASK001  
**Status**: Complete  
**Files**: `.workflow/specs/.race-lock.json`, `.workflow/specs/tasks-v2.6.0.md`, `.workflow/specs/arch-v2.6.0.md`, `.workflow/reports/run-manifest-v2.6.0.json`  
**Dep**: none  
**Agent**: project-coordinator  
**Description**: Activate the v2.6.0 workflow cycle and define canonical task/architecture contracts for package API migration scope.  
**Acceptance**: v2.6.0 lock and spec artifacts exist and describe package API migration scope.  
**Docs**: workflow specs  
**Tests**: TASK005

---

### TASK002 — Package daemon handler foundation

**ID**: TASK002  
**Status**: Complete  
**Files**: `loofi-fedora-tweaks/daemon/handlers/package_handler.py`, `loofi-fedora-tweaks/daemon/handlers/__init__.py`  
**Dep**: TASK001  
**Agent**: backend-builder  
**Description**: Add daemon handler support for package operations with structured response and strict error mapping.  
**Acceptance**: package handler returns schema-consistent payloads for supported actions and explicit typed errors for unsupported or malformed requests.  
**Docs**: docstrings (if behavior changes)  
**Tests**: TASK005

---

### TASK003 — Package service API migration slice

**ID**: TASK003  
**Status**: Complete  
**Files**: `loofi-fedora-tweaks/services/package/service.py`, `loofi-fedora-tweaks/daemon/handlers/package_handler.py`  
**Dep**: TASK002  
**Agent**: backend-builder  
**Description**: Reduce parsing-heavy package command execution by preferring API-backed daemon/service pathways while preserving current method signatures and fallback semantics.  
**Acceptance**: package service behavior remains compatible for callers, with improved structured data handling and no regressions in preferred mode fallback behavior.  
**Docs**: docstrings (if behavior changes)  
**Tests**: TASK005

---

### TASK004 — IPC behavior and compatibility hardening (packages)

**ID**: TASK004  
**Status**: Complete  
**Files**: `loofi-fedora-tweaks/services/ipc/daemon_client.py`, `loofi-fedora-tweaks/services/ipc/types.py`  
**Dep**: TASK003  
**Agent**: backend-builder  
**Description**: Ensure daemon response handling remains strict and backward-compatible for package migration cases.  
**Acceptance**: malformed or unsupported package daemon payloads fail safely with explicit typed errors; preferred mode fallback remains intact.  
**Docs**: docstrings  
**Tests**: TASK005

---

### TASK005 — Test updates for slice-2 package migration

**ID**: TASK005  
**Status**: Complete  
**Files**: `tests/test_daemon_client.py`, `tests/test_ipc_fallback_modes.py`, `tests/test_package_service.py`  
**Dep**: TASK004  
**Agent**: test-writer  
**Description**: Add or update focused tests for package daemon pathways and fallback behavior.  
**Acceptance**: updated test targets pass and verify both success and failure/fallback modes for touched paths.  
**Docs**: module docstrings  
**Tests**: self

---

### TASK006 — Planning artifact cleanup sync

**ID**: TASK006  
**Status**: Complete  
**Files**: `memory-bank/activeContext.md`, `memory-bank/progress.md`, `memory-bank/tasks/_index.md`  
**Dep**: TASK005  
**Agent**: release-planner  
**Description**: Align planning artifacts with active v2.6.0 scope and completed v2.5.0 slice state.  
**Acceptance**: memory-bank state reflects active v2.6.0 workflow and no active-version contradictions remain.  
**Docs**: memory-bank updates  
**Tests**: TASK005

---

### TASK007 — Validation and progress sync

**ID**: TASK007  
**Status**: Complete  
**Files**: `ROADMAP.md`, `.workflow/reports/run-manifest-v2.6.0.json`  
**Dep**: TASK006  
**Agent**: release-planner  
**Description**: Sync roadmap/workflow progress metadata after slice-2 implementation and verification.  
**Acceptance**: workflow artifacts and roadmap status reflect executed v2.6.0 package slice state.  
**Docs**: ROADMAP/workflow report updates  
**Tests**: TASK005
