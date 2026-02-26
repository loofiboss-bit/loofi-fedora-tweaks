# Architecture Spec - v2.11.0 "Residual Migration Slice (Network/Firewall/System)"

## Design Rationale

v2.11.0 converts the residual-service inventory from v2.10.0 into bounded hardening work with no privilege-scope expansion:

1. tighten network local write-path correctness,
2. remove firewall command-construction drift,
3. lock read-path parity decisions for firewall/system helpers,
4. keep daemon-first compatibility behavior stable.

This slice is stabilization-first and intentionally excludes new end-user features.

## Reviewed Inputs

- `.workflow/specs/tasks-v2.11.0.md`
- `AGENTS.md` (critical rules and patterns)
- `ARCHITECTURE.md` (layer rules and critical patterns)

## Scope

- TASK-001: workflow metadata transition to v2.11.0 active target.
- TASK-002: this architecture contract.
- TASK-003/TASK-004: network hardening (local write-path return semantics and active-connection parsing).
- TASK-005/TASK-006: firewall command normalization and parity classification closure.
- TASK-007/TASK-008: focused regression coverage for network/firewall/system behavior guarantees.
- TASK-009/TASK-010: release documentation and roadmap/changelog alignment after verification.

## Non-Goals

1. No new daemon capabilities requiring privilege expansion.
2. No UI tab or CLI feature expansion.
3. No changes to IPC envelope format or default IPC mode behavior.
4. No migration of read-only helpers unless required by compatibility/security constraints.

## Dependency Graph and Sequencing (Acyclic)

```text
TASK-001 -> TASK-002 -> {TASK-003, TASK-004, TASK-005, TASK-006}
TASK-003 + TASK-004 -> TASK-007
TASK-005 + TASK-006 -> TASK-008
TASK-007 + TASK-008 -> TASK-009 -> TASK-010
```

No cycles are present; each edge flows from design to implementation to verification to documentation.

## Critical Rule Alignment Matrix

| Rule (AGENTS.md / ARCHITECTURE.md) | Enforcement in v2.11.0 |
| --- | --- |
| Privileged commands must use `pkexec` (never `sudo`) | Firewall mutators and reload path standardized through `PrivilegedCommand`-built tuples. |
| Always unpack command tuples | All new firewall command calls use `binary, args, desc = ...` before execution. |
| Never hardcode `dnf`; use `SystemManager` PM detection | No package-manager expansion in this slice; existing `SystemManager` pattern remains authoritative. |
| Always branch on Atomic vs Traditional Fedora where relevant | System read-path helpers remain `SystemManager`-owned; no new bypass path added. |
| All subprocess calls require explicit `timeout` | All touched local paths retain explicit timeout values; no new subprocess call without timeout. |
| No `shell=True` | Forbidden; no design introduces shell-based execution. |
| UI must avoid subprocess and use `BaseTab`/`CommandRunner` | No UI file changes in this slice. |
| Audit privileged actions | Firewall privileged mutations/reload routed through audited execution path. |

## Architecture Risk Review and Mitigation

### R1: False-positive success in network local write paths
- **Observed risk**: `reactivate_connection_local`, `connect_wifi_local`, `disconnect_wifi_local`, `apply_dns_local`, and `set_hostname_privacy_local` currently return `True` after `subprocess.run(...)` without checking `returncode`.
- **Mitigation**: enforce `result.returncode == 0` success contract; preserve current exception-to-`False` behavior.

### R2: Active connection misclassification
- **Observed risk**: `get_active_connection_local()` uses substring checks (`"wifi"` / `"ethernet"` in entire line), which can misclassify malformed or unrelated rows.
- **Mitigation**: deterministic parsing by splitting line into `(name, type)` and matching type exactly against supported values.

### R3: Firewall command construction drift
- **Observed risk**: repeated manual construction of `["pkexec", "firewall-cmd", ...]` across mutators and reload creates inconsistency risk and weakens standardized validation/audit flow.
- **Mitigation**: centralize tuple construction in `utils.commands.PrivilegedCommand` and reuse one execution pattern.

### R4: Privileged action audit consistency
- **Observed risk**: privileged firewall local mutators can bypass centralized audit helper.
- **Mitigation**: execute privileged tuples through audited path (`execute_and_log`) or equivalent explicit audit calls with action name + params + exit code.

### R5: Parity ambiguity on read paths
- **Observed risk**: unclear daemon-first vs local-read intent for `get_available_services()`, `has_pending_deployment()`, `get_layered_packages()`.
- **Mitigation**: lock explicit behavior contracts in code comments/tests; avoid implicit mixed behavior.

## Implementation Contracts (Method-Level)

### C1 - Network write-path strict success semantics (TASK-003)

Files: `loofi-fedora-tweaks/services/network/network.py`

Signatures remain unchanged:

```python
@staticmethod
def reactivate_connection_local(connection_name: str) -> bool

@staticmethod
def connect_wifi_local(ssid: str) -> bool

@staticmethod
def disconnect_wifi_local(interface_name: str = "wlan0") -> bool

@staticmethod
def apply_dns_local(connection_name: str, dns_servers: str) -> bool

@staticmethod
def set_hostname_privacy_local(connection_name: str, hide: bool) -> bool
```

Behavior contract:
- keep daemon-first wrappers unchanged (`*_public -> daemon_client.call_json(...) -> *_local fallback`).
- local path must return `True` only when subprocess return code is zero.
- local path must return `False` on non-zero return code and on caught subprocess/OS errors.
- all subprocess calls keep explicit timeout.

### C2 - Active connection parsing hardening (TASK-004)

Files: `loofi-fedora-tweaks/services/network/network.py`, `loofi-fedora-tweaks/daemon/handlers/network_handler.py`

Primary signature unchanged:

```python
@staticmethod
def get_active_connection_local() -> Optional[str]
```

Parsing contract:
- parse each non-empty row from `nmcli -t -f NAME,TYPE connection show --active` into `name` and `conn_type`.
- treat a row as eligible only when normalized `conn_type` is exactly `"wifi"` or `"ethernet"`.
- malformed rows are ignored; function returns `None` when no valid match exists.
- daemon handler return contract stays `str` (`""` for null-equivalent) to preserve IPC payload compatibility.

### C3 - Firewall privileged command normalization (TASK-005)

Files: `loofi-fedora-tweaks/services/security/firewall.py`, `loofi-fedora-tweaks/utils/commands.py`

Add standardized builder(s) in `PrivilegedCommand`:

```python
@staticmethod
def firewall_cmd(arguments: list[str], description: str) -> CommandTuple

@staticmethod
def firewall_reload() -> CommandTuple
```

Use in local mutators/reload:
- `open_port_local`
- `close_port_local`
- `add_service_local`
- `remove_service_local`
- `set_default_zone_local`
- `add_rich_rule_local`
- `remove_rich_rule_local`
- `_reload`

Execution contract:
- always unpack tuple before execution.
- never use `sudo`; never use `shell=True`.
- maintain explicit timeout (`15s` for write/reload paths).
- preserve existing result type (`FirewallResult` for mutators, `bool` for `_reload`).

Audit contract:
- privileged firewall mutations and reload must emit audit entries containing action, params, and exit code.

### C4 - Daemon/local parity classification closure (TASK-006)

Files: `loofi-fedora-tweaks/services/security/firewall.py`, `loofi-fedora-tweaks/daemon/handlers/firewall_handler.py`, `loofi-fedora-tweaks/services/system/system.py`

Contract decisions for v2.11.0:

1. `FirewallManager.get_available_services()` -> **intentional local-read** in this slice.
   - remains unprivileged local `firewall-cmd --get-services` read.
   - behavior and return type stay `List[str]`; failures return `[]`.
   - document decision inline and via regression tests.

2. `SystemManager.has_pending_deployment()` -> **intentional local-read**.
   - remains local `rpm-ostree status --json` parse path with timeout and safe fallback `False`.

3. `SystemManager.get_layered_packages()` -> **intentional local-read**.
   - remains local JSON parse path with timeout and safe fallback `[]`.

Compatibility requirement:
- fallback semantics and public signatures remain unchanged.
- no new privilege scope or root-facing capability introduced.

## Test Strategy and Contracts

### TASK-007 network regressions

Files: `tests/test_network_utils.py`, `tests/test_service_network.py`, `tests/test_ipc_fallback_modes.py`

Required additions:
- non-zero returncode tests for all five hardened local write methods (assert `False`).
- deterministic active-connection parsing tests:
  - valid wifi/ethernet rows,
  - malformed rows,
  - non-target types (vpn/loopback),
  - names containing ambiguous substrings without type match.
- daemon-first compatibility checks confirming unchanged fallback behavior.

### TASK-008 firewall/system regressions

Files: `tests/test_firewall_manager.py`, `tests/test_service_security.py`, `tests/test_system_service.py`

Required additions:
- assert privileged firewall local mutators build commands via standardized tuple path.
- assert explicit timeout remains enforced for each touched subprocess path.
- assert no shell usage and no `sudo` usage in touched command paths.
- assert read-path classification behavior (intentional local-read) remains deterministic.

## Verification Commands (Implementation Exit)

- `PYTHONPATH=loofi-fedora-tweaks python -m pytest tests/test_network_utils.py -v`
- `PYTHONPATH=loofi-fedora-tweaks python -m pytest tests/test_service_network.py -v`
- `PYTHONPATH=loofi-fedora-tweaks python -m pytest tests/test_ipc_fallback_modes.py -v`
- `PYTHONPATH=loofi-fedora-tweaks python -m pytest tests/test_firewall_manager.py -v`
- `PYTHONPATH=loofi-fedora-tweaks python -m pytest tests/test_service_security.py -v`
- `PYTHONPATH=loofi-fedora-tweaks python -m pytest tests/test_system_service.py -v`

## Blocking Concerns

None unresolved at design time. Implementation can proceed with current task ordering.

