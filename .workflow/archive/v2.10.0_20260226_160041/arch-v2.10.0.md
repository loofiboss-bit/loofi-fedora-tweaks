# Architecture Spec — v2.10.0 "API Migration Slice 6 (Canonical Workflow + Next Migration Kickoff)"

## Design Rationale

v2.10.0 starts immediately after v2.9.0 closure and focuses on two priorities:

1) canonical workflow/report artifact normalization (`vX.Y.Z` only), and
2) preparing the next bounded daemon/API migration targets for implementation.

The slice is stabilization-first and explicitly avoids privilege model expansion.

## Scope

1. Enforce canonical `vX.Y.Z` naming for workflow artifacts and checks.
2. Align workflow script tests with canonical artifact expectations.
3. Synchronize roadmap/race-lock/memory-bank metadata to v2.10.0 active state.
4. Define prioritized residual daemon/API migration targets for Slice 6.

## Non-Goals

1. Adding new privileged capabilities.
2. Expanding root-level operations or policy scope.
3. UI feature additions unrelated to migration or workflow correctness.

## Interfaces and Compatibility

- D-Bus contract remains unchanged:
  - Bus: `org.loofi.FedoraTweaks.Daemon`
  - Object: `/org/loofi/FedoraTweaks/Daemon`
  - Interface: `org.loofi.FedoraTweaks.Daemon1`
- IPC envelope remains unchanged:
  - `{"ok": bool, "data": any, "error": {"code": str, "message": str} | null}`
- Service method signatures remain backward-compatible.
- `LOOFI_IPC_MODE=preferred` remains the compatibility default.

## Design Decisions

### D1: Canonical workflow artifact naming (`vX.Y.Z` only)

- **Layer**: workflow scripts + report generation + doc gates
- **Files**: `scripts/workflow_runner.py`, `scripts/check_release_docs.py`, `scripts/generate_workflow_reports.py`
- **Decision**: normalize all incoming version tags to `vX.Y.Z`; stop emitting/accepting short `vX.Y` for active lines.
- **Risk**: legacy artifact references can break checks; mitigated by updating tests and active docs in the same slice.

### D2: Keep migration planning bounded and inventory-first

- **Layer**: architecture/task specs + targeted service modules
- **Files**: `.workflow/specs/tasks-v2.10.0.md`, `.workflow/specs/arch-v2.10.0.md`
- **Decision**: define exact residual pathways before implementation; no broad cross-module churn.
- **Risk**: accidental scope creep; mitigated by explicit non-goals and task contracts.

## Security and Reliability Constraints

1. No `shell=True` usage.
2. All subprocess calls retain explicit `timeout`.
3. Privileged paths remain fail-closed on invalid payload/input.
4. Keep `pkexec`-only privilege model (never `sudo`).
5. No hardcoded package-manager command assumptions.

## Test Strategy

1. Update workflow/report tests for canonical `vX.Y.Z` behavior.
2. Validate release-doc checks with canonical artifact paths only.
3. Ensure workflow status/race-lock behavior remains deterministic.
4. Use focused test runs before broader verification.

## Initial Slice 6 Inventory Targets

### Candidate modules for next migration step

- `services/system/system.py`: residual local command pathways to daemon-first parity.
- `services/network/network.py`: remaining local execution branches requiring daemon parity review.
- `services/security/firewall.py`: residual fallback paths requiring strict parity checks.

### Priority order

1. Finalize canonical workflow artifact behavior and tests.
2. Confirm metadata/state consistency for v2.10.0 activation.
3. Begin bounded residual migration implementation from highest-risk service paths.

## TASK003 Bounded Residual Target List (Method-Level)

### A. `services/network/network.py` (highest priority)

#### Write-path methods with permissive local success behavior

- `reactivate_connection_local(connection_name)`
  - Current local fallback always returns `True` after `subprocess.run(...)` without checking `returncode`.
  - Target: enforce strict success criteria (`returncode == 0`) and keep daemon-first parity.

- `connect_wifi_local(ssid)`
  - Current local fallback always returns `True` after command invocation.
  - Target: return failure on non-zero command result and preserve daemon-first flow.

- `disconnect_wifi_local(interface_name)`
  - Current local fallback always returns `True` after command invocation.
  - Target: enforce returncode-based success and parity with daemon response semantics.

- `apply_dns_local(connection_name, dns_servers)`
  - Current local fallback always returns `True` regardless of command outcome.
  - Target: detect and propagate failure when `nmcli con mod` fails.

- `set_hostname_privacy_local(connection_name, hide)`
  - Current local fallback always returns `True` after command invocation.
  - Target: strict success/failure propagation matching daemon contract.

#### Read-path helper target

- `get_active_connection_local()`
  - Current logic infers active transport via substring checks (`"wifi"`, `"ethernet"`) on raw output lines.
  - Target: improve parse robustness to avoid false positives/negatives while keeping non-privileged local fallback.

### B. `services/security/firewall.py` (medium priority)

#### Privileged command consistency targets

- `open_port_local`, `close_port_local`, `add_service_local`, `remove_service_local`,
  `set_default_zone_local`, `add_rich_rule_local`, `remove_rich_rule_local`, `_reload`
  - Current local path directly constructs `pkexec firewall-cmd` command lists.
  - Target: evaluate migration to `PrivilegedCommand` wrappers where available, preserving timeout and deny-by-default behavior.

#### Daemon/local parity guard target

- `get_available_services()`
  - Current implementation is local-only (`firewall-cmd --get-services`) and bypasses daemon-first path.
  - Target: decide whether to expose daemon method for parity or explicitly document this as intentional local-read behavior.

### C. `services/system/system.py` (lower priority, read-path review)

- `has_pending_deployment()` and `get_layered_packages()`
  - These are read-only local `rpm-ostree` queries with timeout and no privilege escalation.
  - Target: classify as intentional local-read utilities unless cross-process centralization is required for consistency.

## Sequencing for Slice 6 implementation

1. Network write-path strict-success fixes (A) + focused regressions.
2. Firewall privileged command consistency and parity decision (B).
3. System read-path classification closure (C).

## Exit Criteria for TASK003

- Method-level target list is explicit, bounded, and prioritized.
- Each target has a concrete rationale and migration direction.
- No privilege scope expansion is introduced by planning decisions.
