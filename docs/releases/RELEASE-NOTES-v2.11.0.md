# Release Notes — v2.11.0 "API Migration Slice 7"

## Overview

v2.11.0 completes a focused hardening slice for residual network, firewall, and system service local execution paths identified in the v2.10.0 planning cycle. This release tightens correctness guarantees, normalizes privileged command construction patterns, and locks explicit daemon/local parity decisions across key service boundaries. All changes maintain strict backward compatibility with daemon-first preferred-mode fallback behavior and introduce no privilege model expansion.

## Highlights

- Hardened network local write paths (`reactivate_connection_local`, `connect_wifi_local`, `disconnect_wifi_local`, `apply_dns_local`, `set_hostname_privacy_local`) to return strict success/failure based on subprocess exit codes instead of unconditional `True`.
- Tightened active-connection detection in `get_active_connection_local()` with deterministic nmcli output parsing to prevent substring misclassification and handle malformed output safely.
- Normalized firewall local mutator command construction (`open_port_local`, `close_port_local`, `add_service_local`, `remove_service_local`, `set_default_zone_local`, `add_rich_rule_local`, `reload_local`) to project-standard `pkexec` patterns with explicit timeout enforcement and elimination of `sudo`/`shell=True` anti-patterns.
- Finalized daemon/local parity classification for `FirewallManager.get_available_services()` and `SystemService` read paths (`has_pending_deployment()`, `get_layered_packages()`) with explicit behavior contracts.
- Added focused regression coverage for network local write-path return semantics, active-connection parsing determinism, firewall privileged command construction, and system service read-path classification.

## Safety Posture

- **No privilege expansion**: All changes strictly harden existing privileged paths without introducing new capabilities.
- **Fail-safe defaults**: Malformed subprocess output and non-zero exit codes return safe null-equivalent or `False` values.
- **Timeout enforcement**: All subprocess calls retain explicit timeout parameters across all touched code paths.
- **Audit compliance**: Firewall privileged operations maintain consistency with the centralized audit logging framework.
- **Daemon compatibility**: Existing daemon-first with local-fallback behavior remains unchanged; no breaking changes to IPC payload contracts.

## Migration Constraints

- This release does not change user-facing privilege model behavior.
- Existing daemon preferred-mode fallback semantics remain fully compatible.
- No UI tab or CLI command surface changes are included in this slice.
- Runtime version alignment and packaging updates occur in the release phase workflow.

## Verification Summary

Focused regression verification targeted the following test suites with all external system calls mocked:

```bash
# Network hardening regression (strict return semantics, active-connection parsing)
PYTHONPATH=loofi-fedora-tweaks python -m pytest \
  tests/test_network_utils.py \
  tests/test_service_network.py \
  tests/test_ipc_fallback_modes.py \
  -v --tb=short

# Firewall and system service hardening regression (privileged command normalization, parity classification)
PYTHONPATH=loofi-fedora-tweaks python -m pytest \
  tests/test_firewall_manager.py \
  tests/test_service_security.py \
  tests/test_system_service.py \
  -v --tb=short
```

All tests passed with zero failures, confirming correctness preservation and hardening effectiveness across the implementation slices.

## Known Issues

None. This release is a stability-focused hardening slice with no known regressions.

## Next Steps

Follow the active roadmap target in `ROADMAP.md` for the next planning and implementation cycle. The v2.11.0 slice closes the network/firewall/system residual inventory from v2.10.0 and prepares for future daemon/API migration opportunities identified during the architectural review process.
