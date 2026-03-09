# Architecture Spec - v3.0.0 "Aegis"

## Design Rationale

v3.0.0 is the first post-migration major release. The v2.4.0–v2.12.0 line
finished daemon/API parity work, but the stabilization guide still lists open
Phase 3–6 items around API exposure, auth storage, Safe Mode, plugin update
safety, and version consistency. This release stays stabilization-only: no new
major feature families, no privilege-scope expansion, and no UI-layer
subprocess regression.

## Reviewed Inputs

- `.workflow/specs/tasks-v3.0.0.md`
- `AGENTS.md` (critical rules and patterns)
- `ARCHITECTURE.md` (layer boundaries and entry modes)
- `.github/instructions/system_hardening_and_stabilization_guide.md`
- `ROADMAP.md` (active scope)
- Current runtime files: `main.py`, `utils/api_server.py`, `utils/auth.py`, `utils/settings.py`, `utils/daemon.py`, `services/security/risk.py`, `services/security/safety.py`, `ui/confirm_dialog.py`, `ui/settings_tab.py`

## Scope

- TASK-001: activate v3.0.0 metadata and reconcile the missing Phase 3 baseline reference.
- TASK-002: enforce explicit opt-in for non-loopback API exposure.
- TASK-003: harden auth/bootstrap storage and endpoint behavior.
- TASK-004: add route-aware API throttling and read/write boundary controls.
- TASK-005: introduce persisted Safe Mode defaults for mutating execution paths.
- TASK-006: wire Safe Mode and registry-backed risk/revert information into shared UI flows.
- TASK-007: formalize plugin auto-update default-off behavior in persisted settings and daemon flow.
- TASK-008/TASK-009: add focused regression coverage for API and UX safety.
- TASK-010/TASK-011: remove version drift and publish security/release documentation.

## Non-Goals

1. No new privileged capabilities, polkit surface, or arbitrary command execution.
2. No new feature tabs beyond bounded settings/confirmation integrations required for safety work.
3. No replacement of the current FastAPI stack or plugin architecture.
4. No feature-expansion work unrelated to stabilization phases 3–6.

## Dependency Graph and Sequencing (Acyclic)

```text
TASK-001 -> {TASK-002, TASK-003, TASK-005, TASK-007}
TASK-002 + TASK-003 -> TASK-004
TASK-005 -> TASK-006
TASK-002 + TASK-003 + TASK-004 -> TASK-008
TASK-005 + TASK-006 + TASK-007 -> TASK-009
TASK-008 + TASK-009 -> TASK-010 -> TASK-011
```

## Design Decisions

### D1 - Re-establish the Phase 3 Baseline in Canonical Workflow Artifacts

- **Layer**: `.workflow/` + roadmap metadata
- **Files**: `ROADMAP.md`, `.workflow/specs/.race-lock.json`, `.workflow/specs/tasks-v3.0.0.md`, `.workflow/specs/arch-v3.0.0.md`
- **Decision**: treat the stabilization guide as authoritative because the referenced `arch-v2.7.0.md` baseline is absent from the current `.workflow/specs/` directory.
- **Why**: planning must be grounded in the files that actually exist today, not only in historical references.
- **Constraints**: keep exactly one ACTIVE roadmap target and do not reopen completed v2.x slices.

### D2 - Loopback-First API Exposure Control

- **Layer**: entrypoint + API server bootstrap
- **Files**: `loofi-fedora-tweaks/main.py`, `loofi-fedora-tweaks/utils/api_server.py`
- **Decision**: keep `127.0.0.1`/`::1` as the safe default and require an explicit `--unsafe-expose` flag before any non-loopback bind is honored.
- **Why**: `LOOFI_API_HOST` currently allows silent trust-boundary expansion.
- **Constraints**: preserve env-based configuration, emit clear refusal messages, and avoid breaking localhost development.

### D3 - Auth Bootstrap and Storage Hardening Around Existing ConfigManager Paths

- **Layer**: shared utils
- **Files**: `loofi-fedora-tweaks/utils/auth.py`, `loofi-fedora-tweaks/utils/config_manager.py`, `loofi-fedora-tweaks/utils/api_server.py`
- **Decision**: keep auth material under the current config-management path, but persist it with deterministic structure, strict file permissions, and explicit validation on load.
- **Why**: `AuthManager` currently mixes `ConfigManager` state with a marker file write, which is too loose for Phase 3 expectations.
- **Constraints**: maintain JWT and API-key semantics, avoid secret leaks in logs, and keep bootstrap behavior compatible with existing clients where safe.

### D4 - Route-Aware Throttling and Explicit Read/Write Policy Buckets

- **Layer**: API routing
- **Files**: `loofi-fedora-tweaks/utils/api_server.py`, `loofi-fedora-tweaks/api/routes/executor.py`, `loofi-fedora-tweaks/api/routes/system.py`, `loofi-fedora-tweaks/api/routes/profiles.py`
- **Decision**: apply stricter limits and policy checks to bootstrap/authentication and mutating routes than to read-only routes.
- **Why**: the current API already distinguishes health/read/write behavior, but the policy is implicit rather than enforced uniformly.
- **Constraints**: keep `/api/health` minimal and unauthenticated, preserve existing response contracts, and return explicit retry guidance on throttling.

### D5 - Safe Mode as a Shared Service-Level Mutation Guard

- **Layer**: services + persisted settings + API integration
- **Files**: `loofi-fedora-tweaks/services/security/safe_mode.py`, `loofi-fedora-tweaks/services/security/safety.py`, `loofi-fedora-tweaks/utils/settings.py`, `loofi-fedora-tweaks/api/routes/executor.py`
- **Decision**: implement Safe Mode as a reusable guard that defaults on for first-run behavior and is consulted before mutating API execution.
- **Why**: Phase 4 requires explicit opt-in for mutations, and the current code has snapshot safety helpers but no read-only default mode.
- **Constraints**: do not weaken audit logging, do not bypass existing executor validation, and keep the guard independent of PyQt.

### D6 - Reuse ConfirmActionDialog and RiskRegistry Instead of Inventing New UX

- **Layer**: UI + shared safety services
- **Files**: `loofi-fedora-tweaks/ui/settings_tab.py`, `loofi-fedora-tweaks/ui/confirm_dialog.py`, `loofi-fedora-tweaks/services/security/safety.py`, `loofi-fedora-tweaks/services/security/risk.py`
- **Decision**: extend the existing confirmation dialog and safety helper path so registry-backed risk badges and revert instructions appear where confirmation already happens.
- **Why**: the project already has `ConfirmActionDialog` risk badge rendering and `RiskRegistry`; the missing piece is shared wiring and settings exposure.
- **Constraints**: no UI-layer subprocess execution, keep dialogs functional when a risk entry is missing, and use `self.tr(...)` for user-visible strings.

### D7 - Formalize Plugin Auto-Update Safety in the Legacy Daemon Path

- **Layer**: settings + daemon + plugin installer
- **Files**: `loofi-fedora-tweaks/utils/settings.py`, `loofi-fedora-tweaks/utils/daemon.py`, `loofi-fedora-tweaks/utils/plugin_installer.py`
- **Decision**: treat `plugin_auto_update` as a first-class persisted setting and preserve default-off behavior while leaving integrity and rollback enforcement in place.
- **Why**: the daemon already checks `plugin_auto_update`, but the key is not part of canonical settings defaults and therefore lacks explicit UX/control.
- **Constraints**: do not remove checksum/signature verification, and do not enable unattended updates by default.

### D8 - Finish With Version and Documentation Consistency

- **Layer**: version metadata + docs
- **Files**: `loofi-fedora-tweaks/version.py`, `pyproject.toml`, `loofi-fedora-tweaks.spec`, `SECURITY.md`, `CHANGELOG.md`, `README.md`, `docs/releases/RELEASE-NOTES-v3.0.0.md`
- **Decision**: bump directly to `3.0.0` after the stabilization slice passes and document the actual API trust model plus disclosure process.
- **Why**: `version.py` still reports `2.11.0` even though roadmap history continued through `v2.12.0`.
- **Constraints**: use the canonical bump flow, keep docs aligned with verified behavior only, and ensure UI/API/packaging report the same version.

## Risk Review and Mitigation

- **Risk R1**: accidental API lockout during bootstrap hardening.
  - **Mitigation**: keep loopback-safe defaults, preserve clear bootstrap path, and add focused API regression coverage.
- **Risk R2**: Safe Mode guard blocks legitimate flows too broadly.
  - **Mitigation**: scope the guard to mutating execution paths first and surface clear opt-in messaging in settings.
- **Risk R3**: plugin update controls drift between `SettingsManager` and `ConfigManager` consumers.
  - **Mitigation**: define a single persisted key and test daemon/default behavior explicitly.
- **Risk R4**: version cleanup lands before stabilization work is validated.
  - **Mitigation**: gate version bump and release docs after API and UX safety tests pass.

## Verification Commands (Slice Exit)

- `PYTHONPATH=loofi-fedora-tweaks python -m pytest tests/test_api_server.py -v`
- `PYTHONPATH=loofi-fedora-tweaks python -m pytest tests/test_auth.py -v`
- `PYTHONPATH=loofi-fedora-tweaks python -m pytest tests/test_api_profiles.py -v`
- `PYTHONPATH=loofi-fedora-tweaks python -m pytest tests/test_settings.py -v`
- `PYTHONPATH=loofi-fedora-tweaks python -m pytest tests/test_confirm_dialog.py -v`
- `PYTHONPATH=loofi-fedora-tweaks python -m pytest tests/test_daemon.py -v`

## Blocking Concerns

- The stabilization guide references `.workflow/specs/arch-v2.7.0.md` as the Phase 3 inventory baseline, but that artifact is not present in the current repository state. v3.0.0 therefore re-establishes the baseline directly from the guide and current runtime files.
