# Tasks — v2.9.0 "API Migration Slice 5 (Residual Privileged Path Migration)"

**Date**: 2026-02-26  
**Status**: Complete  
**Arch Spec**: `arch-v2.9.0.md`

## Task List

---

### TASK001 — Activate v2.9.0 workflow contracts

**ID**: TASK001  
**Status**: Complete  
**Files**: `ROADMAP.md`, `.workflow/specs/.race-lock.json`, `.workflow/specs/tasks-v2.9.0.md`, `.workflow/specs/arch-v2.9.0.md`, `memory-bank/activeContext.md`, `memory-bank/progress.md`, `memory-bank/tasks/_index.md`  
**Dep**: none  
**Agent**: project-coordinator  
**Description**: Activate the next active slice after v2.8.0 closure and align canonical roadmap/workflow/memory artifacts to v2.9.0.  
**Acceptance**: v2.9.0 is ACTIVE in roadmap and race-lock, with matching task/architecture/memory context state.  
**Docs**: roadmap + workflow specs + memory-bank updates  
**Tests**: Workflow artifact consistency check

---

### TASK002 — Inventory residual privileged pathways

**ID**: TASK002  
**Status**: Complete  
**Files**: `loofi-fedora-tweaks/services/system/services.py`, `loofi-fedora-tweaks/services/system/system.py`, `loofi-fedora-tweaks/services/network/ports.py`, `loofi-fedora-tweaks/services/security/firewall.py`, `.workflow/specs/arch-v2.9.0.md`  
**Dep**: TASK001  
**Agent**: backend-builder  
**Description**: Build an explicit inventory of remaining privileged/local execution paths and prioritize bounded migration targets for v2.9.0.  
**Acceptance**: prioritized migration list exists with method-level targets and risk notes; no privilege scope expansion.  
**Docs**: architecture notes in `arch-v2.9.0.md`  
**Tests**: N/A

---

### TASK003 — Extend daemon handlers and validator coverage for selected v2.9 targets

**ID**: TASK003  
**Status**: Complete  
**Files**: `loofi-fedora-tweaks/daemon/handlers/service_handler.py`, `loofi-fedora-tweaks/daemon/handlers/firewall_handler.py`, `loofi-fedora-tweaks/daemon/validators.py`, `loofi-fedora-tweaks/services/ipc/types.py`  
**Dep**: TASK002  
**Agent**: backend-builder  
**Description**: Add daemon-side support and strict validation for selected residual privileged methods while preserving envelope compatibility.  
**Acceptance**: selected methods support daemon execution with fail-closed validation and typed payload compatibility behavior.  
**Docs**: module-level behavior notes (if needed)  
**Tests**: TASK005

---

### TASK004 — Migrate prioritized service pathways to daemon-first parity

**ID**: TASK004  
**Status**: Complete  
**Files**: `loofi-fedora-tweaks/services/system/services.py`, `loofi-fedora-tweaks/services/system/system.py`, `loofi-fedora-tweaks/services/network/ports.py`, `loofi-fedora-tweaks/services/security/firewall.py`  
**Dep**: TASK003  
**Agent**: backend-builder  
**Description**: Shift prioritized methods to daemon-first invocation with strict preferred-mode local fallback parity for compatibility-safe rollout.  
**Acceptance**: migrated methods use daemon-first flow; fallback behavior remains stable under `LOOFI_IPC_MODE=preferred`.  
**Docs**: architecture + changelog notes pending finalization  
**Tests**: TASK005

---

### TASK005 — Add focused migration regression coverage

**ID**: TASK005  
**Status**: Complete  
**Files**: `tests/test_daemon_dbus.py`, `tests/test_daemon_client.py`, `tests/test_ipc_fallback_modes.py`, `tests/test_service_system.py`, `tests/test_firewall_manager.py`, `tests/test_ports.py`  
**Dep**: TASK004  
**Agent**: test-writer  
**Description**: Add focused regression tests for newly migrated methods covering success, malformed input, daemon failure, and preferred-mode fallback paths.  
**Acceptance**: focused suite passes and validates compatibility-safe migration behavior for selected v2.9 pathways.  
**Docs**: workflow test notes via run-manifest/report artifacts  
**Tests**: self

---

### TASK006 — Verification and metadata synchronization

**ID**: TASK006  
**Status**: Complete  
**Files**: `.workflow/reports/run-manifest-v2.9.0.json`, `ROADMAP.md`, `memory-bank/activeContext.md`, `memory-bank/progress.md`, `memory-bank/tasks/_index.md`, `memory-bank/tasks/TASK-026-v290-daemon-api-slice5.md`  
**Dep**: TASK005  
**Agent**: release-planner  
**Description**: Synchronize workflow/roadmap/memory status and v2.9 execution notes after implementation and focused verification.  
**Acceptance**: canonical artifacts agree on v2.9 progress with no status contradictions.  
**Docs**: roadmap/workflow/memory updates  
**Tests**: TASK005
