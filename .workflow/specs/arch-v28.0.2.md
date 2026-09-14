# Architecture — v28.0.2 "Ease"

Status: patch release architecture for the merged battery-service review fixes.

## Goals

- Keep the v28 Core product boundary and Action Center mutation authority
  unchanged.
- Advertise only battery-service backends that are implemented and observable
  through the standard Fedora sysfs contract.
- Make privileged cleanup auditable, bounded, validated, and fail closed.

## Decisions

- `BatteryService.is_supported()` reports support only for the implemented
  standard sysfs backend. Firmware-specific HP BIOS/WMI support is not claimed
  without an implemented backend.
- Battery cleanup uses the existing `PrivilegedCommand` abstraction and its
  validated builders for service disablement, unit removal, daemon reload, and
  failed-state reset. The cleanup path checks each return code and treats
  timeout, OS error, or non-zero completion as failure.
- Removal uses `rm -f -- <validated path>` so the target cannot be interpreted
  as an option. No shell command string or unbounded subprocess path is added.
- The patch changes no routes, product destinations, deployment backends,
  host settings, service enablement behavior, or persisted user-data contract.

## Verification boundaries

Focused and full rootless/offscreen tests qualify the code and command
contracts. Physical Fedora, authorization-agent, reboot, fresh Atomic,
keyboard, Orca, and clean-install qualification remain separate manual gates
and must not be inferred from these checks.
