# Tasks — v2.4.0 "Daemon Foundation"

**Date**: 2026-02-25  
**Status**: In Progress  
**Arch Spec**: `arch-v2.4.0.md`

## Task List

---

### TASK001 — Daemon IPC scaffolding

**ID**: TASK001  
**Status**: Complete  
**Files**: `loofi-fedora-tweaks/daemon/__init__.py`, `loofi-fedora-tweaks/daemon/runtime.py`, `loofi-fedora-tweaks/daemon/server.py`, `loofi-fedora-tweaks/daemon/interfaces.py`, `loofi-fedora-tweaks/daemon/contracts.py`, `loofi-fedora-tweaks/daemon/validators.py`, `loofi-fedora-tweaks/daemon/handlers/network_handler.py`, `loofi-fedora-tweaks/daemon/handlers/firewall_handler.py`  
**Dep**: none  
**Agent**: backend-builder  
**Description**: Add a standalone daemon package with D-Bus host, strict validators, and network/firewall handlers.  
**Acceptance**: `Ping` and `GetCapabilities` methods return valid JSON envelopes; invalid parameters return validation errors.  
**Docs**: module docstrings  
**Tests**: TASK005

---

### TASK002 — IPC client and mode controls

**ID**: TASK002  
**Status**: Complete  
**Files**: `loofi-fedora-tweaks/services/ipc/__init__.py`, `loofi-fedora-tweaks/services/ipc/daemon_client.py`, `loofi-fedora-tweaks/services/ipc/errors.py`, `loofi-fedora-tweaks/services/ipc/types.py`  
**Dep**: TASK001  
**Agent**: backend-builder  
**Description**: Implement daemon client with `disabled|preferred|required` behavior controlled by `LOOFI_IPC_MODE`.  
**Acceptance**: Preferred mode falls back on transport failures; required mode fails closed with explicit exception.  
**Docs**: docstrings  
**Tests**: TASK005

---

### TASK003 — Service migration (network/firewall/ports)

**ID**: TASK003  
**Status**: Complete  
**Files**: `loofi-fedora-tweaks/services/network/network.py`, `loofi-fedora-tweaks/services/security/firewall.py`, `loofi-fedora-tweaks/services/network/ports.py`, `loofi-fedora-tweaks/services/security/__init__.py`  
**Dep**: TASK002  
**Agent**: backend-builder  
**Description**: Refactor services to daemon-first execution with local fallback while preserving signatures and return shapes.  
**Acceptance**: Existing callers continue to work unchanged; local fallback remains available in preferred mode.  
**Docs**: docstrings  
**Tests**: TASK005

---

### TASK004 — Runtime and UI wiring

**ID**: TASK004  
**Status**: Complete  
**Files**: `loofi-fedora-tweaks/main.py`, `loofi-fedora-tweaks/ui/security_tab.py`  
**Dep**: TASK003  
**Agent**: frontend-integration-builder  
**Description**: Wire daemon runtime entrypoint and remove direct firewall command execution from security UI.  
**Acceptance**: `--daemon` starts new runtime; firewall controls in UI use service layer.  
**Docs**: none  
**Tests**: TASK005

---

### TASK005 — Tests and verification

**ID**: TASK005  
**Status**: In Progress  
**Files**: `tests/test_daemon_client.py`, `tests/test_ipc_fallback_modes.py`, `tests/test_daemon_dbus.py`, updates to existing network/firewall tests  
**Dep**: TASK004  
**Agent**: test-writer  
**Description**: Add daemon client and fallback mode tests plus targeted regression tests for migrated services.  
**Acceptance**: All new tests pass; no regressions in touched modules.  
**Docs**: module docstrings  
**Tests**: self

---

### TASK006 — Packaging and release docs

**ID**: TASK006  
**Status**: Complete  
**Files**: `pyproject.toml`, `requirements.txt`, `loofi-fedora-tweaks.spec`, `loofi-fedora-tweaks/config/loofi-fedora-tweaks.service`, `CHANGELOG.md`, `ROADMAP.md`, `ARCHITECTURE.md`, `loofi-fedora-tweaks/version.py`  
**Dep**: TASK004  
**Agent**: release-planner  
**Description**: Update dependencies, runtime environment defaults, and documentation for v2.4.0.  
**Acceptance**: Version and codename aligned; roadmap/changelog updated with v2.4.0 scope.  
**Docs**: CHANGELOG/ROADMAP/ARCHITECTURE  
**Tests**: TASK005

