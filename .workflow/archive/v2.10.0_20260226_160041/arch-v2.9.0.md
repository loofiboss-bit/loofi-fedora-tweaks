# Architecture Spec — v2.9.0 "API Migration Slice 5 (Residual Privileged Path Migration)"

## Design Rationale

v2.9.0 continues the daemon-first migration sequence after v2.8.0 hardening by
targeting residual privileged pathways that still rely on direct local execution.
The slice remains bounded and compatibility-focused: no privilege model expansion,
no new root capability surface, and no unrelated UI feature scope.

## Scope

1. Inventory remaining privileged/local execution pathways in service modules.
2. Prioritize a bounded subset for v2.9 migration.
3. Extend daemon handler + validator coverage for selected methods.
4. Migrate selected service call paths to daemon-first with preferred-mode fallback parity.
5. Add focused regression tests for daemon/client/fallback compatibility.

## Non-Goals

1. Broad architectural refactors outside selected migration targets.
2. New policy capability/action additions.
3. Privilege escalation model changes or unsafe exposure changes.

## Interfaces and Compatibility

- D-Bus daemon contract remains unchanged:
  - Bus: `org.loofi.FedoraTweaks.Daemon`
  - Object: `/org/loofi/FedoraTweaks/Daemon`
  - Interface: `org.loofi.FedoraTweaks.Daemon1`
- IPC envelope remains unchanged:
  - `{"ok": bool, "data": any, "error": {"code": str, "message": str} | null}`
- Service method signatures remain backward-compatible for callers.
- `LOOFI_IPC_MODE=preferred` remains the default fallback mode.

## Design Decisions

### D1: Inventory-first migration targeting

- **Layer**: services + daemon + validators
- **Modified files**: `services/system/services.py`, `services/system/system.py`, `services/network/ports.py`, `services/security/firewall.py`
- **Pattern**: enumerate residual privileged paths first, then migrate in bounded batches
- **Risk**: accidental scope creep; mitigated with explicit target list and non-goals

### D2: Strict fail-closed validation for newly daemonized pathways

- **Layer**: daemon handlers + validators + IPC types
- **Modified files**: `daemon/handlers/service_handler.py`, `daemon/handlers/firewall_handler.py`, `daemon/validators.py`, `services/ipc/types.py`
- **Pattern**: validate inputs before privileged operations; reject malformed payloads with typed envelope errors
- **Risk**: false rejections for valid legacy inputs; mitigated through focused compatibility tests and preferred-mode fallback validation

### D3: Preferred-mode fallback compatibility is mandatory

- **Layer**: services + ipc client
- **Modified files**: selected service methods in `services/system/`, `services/network/`, `services/security/`
- **Pattern**: daemon-first call, then local fallback on daemon unavailability when mode is preferred
- **Risk**: behavior drift between daemon and local code paths; mitigated with paired success/failure regression tests

## Security and Reliability Constraints

1. No `shell=True` usage.
2. All subprocess calls retain explicit `timeout`.
3. Privileged actions remain constrained to existing capability scope.
4. Unknown/malformed daemon payloads fail closed with typed errors.
5. No hardcoded `dnf`; package manager resolution remains dynamic.

## Test Strategy

1. Extend daemon-side tests for new handler methods and validation failure paths.
2. Extend IPC client tests for typed payload handling and fallback semantics.
3. Extend service tests for daemon-first parity and preferred-mode local fallback.
4. Keep test coverage focused on touched pathways to minimize unrelated churn.

## v2.9 Inventory Snapshot (TASK002)

### Target modules scanned

- `services/system/services.py`
- `services/system/system.py`
- `services/network/ports.py`
- `services/security/firewall.py`

### Residual privileged/migration candidates

- **ServiceManager system mutations** in `services/system/services.py`
- Methods: `start_unit`, `stop_unit`, `restart_unit`, `mask_unit`, `unmask_unit`
- Current local path: direct `pkexec systemctl` execution
- v2.9 action: route daemon-first through `Service*` IPC methods with preferred fallback

- **ServiceManager read path parity** in `services/system/services.py`
- Methods: `list_units`, `get_unit_status`
- Current local path: direct `systemctl` execution
- v2.9 action: daemon-first read-path support for parity and centralized validation

- **Daemon exposure gaps** in `daemon/server.py`
- Existing handlers for package/service existed but were not exported as D-Bus methods
- v2.9 action: expose `Package*`, `System*`, and `Service*` methods on daemon interface

- **Firewall/ports residual local fallbacks** in `services/security/firewall.py` and `services/network/ports.py`
- Methods still include direct local fallback execution (`pkexec firewall-cmd`, `systemctl` checks)
- v2.9 action: keep fallback behavior, validate parity, and harden method-level contracts incrementally

### Priority for implementation sequence

- `daemon/server.py` method exposure for existing package/system/service handlers
- `services/system/services.py` daemon-first migration for service management methods
- Focused regression coverage for daemon response + preferred fallback parity
