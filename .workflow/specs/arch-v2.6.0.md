# Architecture Spec — v2.6.0 "API Migration Slice 2 (Packages)"

## Design Rationale

v2.6.0 continues Phase 2 of the refactor plan by extending daemon-first API
migration into package operations while preserving caller contracts and fallback
behavior introduced in prior slices.

This slice is intentionally narrow:

1. Keep package service method signatures stable for UI/CLI/API callers.
2. Prefer API-backed daemon pathways for package operations where possible.
3. Preserve safe fallback behavior in `LOOFI_IPC_MODE=preferred`.

## Scope

1. Package slice: migrate package service pathways in
   `services/package/service.py` toward daemon/API-first behavior.
2. Add or align package daemon handler contracts under
   `daemon/handlers/`.
3. Harden IPC payload compatibility for package-specific response envelopes.
4. Add focused fallback and compatibility tests for touched package + IPC paths.

## Non-Goals

1. Full `systemctl` → D-Bus migration in this version.
2. Broader polkit policy audit completion in this version.
3. Unrelated UI feature expansion in this version.

## Interfaces and Compatibility

- D-Bus daemon contract remains:
  - Bus: `org.loofi.FedoraTweaks.Daemon`
  - Object: `/org/loofi/FedoraTweaks/Daemon`
  - Interface: `org.loofi.FedoraTweaks.Daemon1`
- Envelope remains unchanged:
  - `{"ok": bool, "data": any, "error": {"code": str, "message": str} | null}`
- Existing package service signatures and return shapes remain backward-compatible.

## Security and Reliability Constraints

1. No `shell=True` usage.
2. All subprocess invocations retain explicit `timeout`.
3. Privileged pathways continue using `PrivilegedCommand` and strict validation.
4. Prefer restrictive behavior on unknown or malformed daemon payloads.
