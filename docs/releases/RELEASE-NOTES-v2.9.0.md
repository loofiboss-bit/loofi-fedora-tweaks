# Release Notes — v2.9.0 "API Migration Slice 5"

## Overview

v2.9.0 finalizes a bounded residual privileged-path migration slice focused on daemon-first execution parity for selected service, firewall, and ports operations. This cycle extends daemon method coverage, preserves preferred-mode compatibility fallbacks, and hardens fail-closed validation behavior on migrated paths. The implementation emphasizes no privilege expansion while tightening regression confidence for daemon/API migration continuity.

## Highlights

- Extended daemon D-Bus export surface in `daemon/server.py` for selected `Package*`, `System*`, and `Service*` methods.
- Added `ServiceHandler` support for `mask_unit`, `unmask_unit`, and `get_unit_status` wrappers.
- Migrated selected `ServiceManager` pathways to daemon-first invocation with preferred fallback parity.
- Migrated `FirewallManager.is_running()` to daemon-first reads with local-safe recursion-resistant fallback.
- Hardened `PortAuditor` local fallback with normalized port/protocol allowlist validation (`tcp|udp`, valid port range).
- Added focused regression coverage for daemon payload handling, fallback modes, service forwarding, firewall/ports behavior, and invalid-input fail-closed paths.
- Completed focused verification run: `248 passed, 1 warning, 0 failed`.

## Upgrade Notes

- No user-facing privilege model changes in this slice.
- Existing preferred-mode compatibility behavior remains intact.
- Runtime version bump and packaging alignment should be handled at release packaging phase.
