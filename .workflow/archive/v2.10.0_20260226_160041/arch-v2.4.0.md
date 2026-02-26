# Architecture Spec — v2.4.0 "Daemon Foundation"

## Design Rationale

v2.4.0 introduces a daemon IPC boundary for high-churn network and firewall operations.
This decouples GUI/CLI callsites from direct command execution while preserving behavior
through strangler fallback in `LOOFI_IPC_MODE=preferred`.

## Scope

1. Add standalone `daemon/` package with D-Bus host and strict input validation.
2. Add `services/ipc/` mode-aware daemon client (`disabled|preferred|required`).
3. Migrate `services/network/network.py`, `services/security/firewall.py`, and `services/network/ports.py`
   to daemon-first execution with local fallback.
4. Keep local command paths intact for rollback and incremental Phase 2 API migration.

## Interfaces

- Bus: `org.loofi.FedoraTweaks.Daemon`
- Object: `/org/loofi/FedoraTweaks/Daemon`
- Interface: `org.loofi.FedoraTweaks.Daemon1`
- Envelope: `{"ok": bool, "data": any, "error": {"code": str, "message": str} | null}`

## Compatibility

- Public service method signatures remain unchanged.
- Preferred mode preserves current behavior on daemon transport failures.
- Required mode fails closed and does not execute local fallback paths.

