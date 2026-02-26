# Release Notes Draft - v2.11.0

## Summary

v2.11.0 is a stabilization-focused migration slice that hardens network and firewall service behavior, resolves daemon/local parity ambiguity on selected read paths, and improves command-construction consistency for privileged firewall operations.

## Highlights

- Network local write paths now enforce strict success/failure semantics from subprocess return codes.
- Active connection detection is hardened to deterministic parsing for wifi/ethernet rows.
- Firewall local mutators and reload behavior are normalized to centralized `PrivilegedCommand` tuple construction.
- Privileged firewall actions are aligned with project audit expectations (action, params, exit code).
- Read-path contracts are explicitly classified for `get_available_services()`, `has_pending_deployment()`, and `get_layered_packages()`.

## User-Visible Impact

- No new UI tabs or CLI commands.
- No new privileged capabilities.
- Improved reliability of network/firewall operation results (fewer false-success outcomes).

## Safety and Security Posture

- `pkexec`-only privilege model is preserved (no `sudo`).
- No `shell=True` subprocess usage is introduced.
- Explicit `timeout` remains required on all touched subprocess paths.
- No package-manager hardcoding is introduced (`SystemManager` remains source of truth).

## Compatibility Notes

- D-Bus envelope and IPC fallback semantics remain unchanged.
- Method signatures and return types remain backward compatible.
- Read-path decisions in this slice avoid privilege-scope expansion and keep safe defaults (`[]`/`False`/`None` patterns).

## Validation Commands (Planned)

- `PYTHONPATH=loofi-fedora-tweaks python -m pytest tests/test_network_utils.py -v`
- `PYTHONPATH=loofi-fedora-tweaks python -m pytest tests/test_service_network.py -v`
- `PYTHONPATH=loofi-fedora-tweaks python -m pytest tests/test_ipc_fallback_modes.py -v`
- `PYTHONPATH=loofi-fedora-tweaks python -m pytest tests/test_firewall_manager.py -v`
- `PYTHONPATH=loofi-fedora-tweaks python -m pytest tests/test_service_security.py -v`
- `PYTHONPATH=loofi-fedora-tweaks python -m pytest tests/test_system_service.py -v`

## Files Expected During Implementation

- `loofi-fedora-tweaks/services/network/network.py`
- `loofi-fedora-tweaks/daemon/handlers/network_handler.py`
- `loofi-fedora-tweaks/services/security/firewall.py`
- `loofi-fedora-tweaks/daemon/handlers/firewall_handler.py`
- `loofi-fedora-tweaks/services/system/system.py`
- `loofi-fedora-tweaks/utils/commands.py`
- `tests/test_network_utils.py`
- `tests/test_service_network.py`
- `tests/test_ipc_fallback_modes.py`
- `tests/test_firewall_manager.py`
- `tests/test_service_security.py`
- `tests/test_system_service.py`
- `CHANGELOG.md`
- `ROADMAP.md`
- `README.md`
- `docs/releases/RELEASE-NOTES-v2.11.0.md`

## Non-Goals for v2.11.0

- New major features.
- New daemon capability surfaces beyond this migration slice.
- UI redesign or workflow model changes unrelated to migration hardening.

