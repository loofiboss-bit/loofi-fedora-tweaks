# Tasks — v3.0.0

- [x] ID: TASK-001 | Files: `ROADMAP.md, .workflow/specs/.race-lock.json, .workflow/specs/tasks-v3.0.0.md, .workflow/specs/arch-v3.0.0.md` | Dep: - | Agent: project-coordinator | Description: Activate v3.0.0 as the single active workflow target and reconcile the missing Phase 3 baseline reference with the current codebase and stabilization guide.
      Acceptance: `ROADMAP.md` contains exactly one ACTIVE version (`v3.0.0`), race-lock points to `v3.0.0` with `status=active`, and the v3 task/architecture specs reference only verified file paths.
      Docs: ROADMAP
      Tests: `tests/test_workflow_runner_locks.py`

- [x] ID: TASK-002 | Files: `loofi-fedora-tweaks/main.py, loofi-fedora-tweaks/utils/api_server.py` | Dep: TASK-001 | Agent: backend-builder | Description: Enforce loopback-only API startup by default and require explicit `--unsafe-expose` for non-localhost binds while preserving current `LOOFI_API_HOST` and `LOOFI_API_PORT` overrides.
      Acceptance: `--web` starts normally for `127.0.0.1`/`::1`, rejects non-loopback binds without `--unsafe-expose`, and logs a clear refusal path without expanding network exposure silently.
      Docs: none
      Tests: `tests/test_api_server.py`

- [ ] ID: TASK-003 | Files: `loofi-fedora-tweaks/utils/auth.py, loofi-fedora-tweaks/utils/config_manager.py, loofi-fedora-tweaks/utils/api_server.py` | Dep: TASK-001 | Agent: backend-builder | Description: Harden API bootstrap and auth storage by fixing persisted auth data format, applying strict file permissions, and constraining `/api/key` and `/api/token` to safe bootstrap behavior.
      Acceptance: Auth material is stored deterministically with owner-only permissions, invalid or world-readable auth data is rejected, and bootstrap endpoints no longer widen the trust boundary unexpectedly.
      Docs: none
      Tests: `tests/test_auth.py, tests/test_api_server.py`

- [ ] ID: TASK-004 | Files: `loofi-fedora-tweaks/utils/api_server.py, loofi-fedora-tweaks/api/routes/executor.py, loofi-fedora-tweaks/api/routes/system.py, loofi-fedora-tweaks/api/routes/profiles.py` | Dep: TASK-002, TASK-003 | Agent: backend-builder | Description: Add route-aware API throttling and codify the read-only versus privileged endpoint policy so authentication/bootstrap, read, and mutation paths have distinct safeguards.
      Acceptance: Authentication/bootstrap routes are rate-limited, mutation routes have stricter controls than read-only routes, and 429 responses include retry guidance without changing existing route contracts.
      Docs: none
      Tests: `tests/test_api_server.py, tests/test_api_profiles.py`

- [ ] ID: TASK-005 | Files: `loofi-fedora-tweaks/services/security/safe_mode.py, loofi-fedora-tweaks/services/security/safety.py, loofi-fedora-tweaks/utils/settings.py, loofi-fedora-tweaks/api/routes/executor.py` | Dep: TASK-001 | Agent: backend-builder | Description: Introduce Safe Mode as a persisted, default-on first-run control that permits diagnostics but blocks mutating API execution until the user explicitly opts in.
      Acceptance: Safe Mode defaults to enabled on first launch, exposes a reusable mutation guard, returns a clear refusal message for blocked execute requests, and does not bypass existing audit/risk paths.
      Docs: none
      Tests: `tests/test_safe_mode.py, tests/test_auth.py`

- [ ] ID: TASK-006 | Files: `loofi-fedora-tweaks/ui/settings_tab.py, loofi-fedora-tweaks/ui/confirm_dialog.py, loofi-fedora-tweaks/services/security/safety.py, loofi-fedora-tweaks/services/security/risk.py` | Dep: TASK-005 | Agent: frontend-integration-builder | Description: Wire Safe Mode and risk classification into the existing confirmation flow so the settings UI can toggle Safe Mode and confirmation dialogs surface registry-backed risk/revert guidance.
      Acceptance: Settings exposes Safe Mode state, confirmation dialogs display registry-backed risk badges and revert hints when available, and current maintenance/security call sites can adopt the shared path without direct subprocess changes in UI.
      Docs: none
      Tests: `tests/test_settings.py, tests/test_confirm_dialog.py`

- [ ] ID: TASK-007 | Files: `loofi-fedora-tweaks/utils/settings.py, loofi-fedora-tweaks/utils/daemon.py, loofi-fedora-tweaks/utils/plugin_installer.py` | Dep: TASK-001 | Agent: backend-builder | Description: Formalize plugin update safety by making `plugin_auto_update` a first-class persisted setting, keeping the default off, and ensuring daemon-driven updates preserve verification and rollback expectations.
      Acceptance: `plugin_auto_update` is a known setting with a default-off value, daemon update checks do not auto-install unless explicitly enabled, and the update flow retains integrity verification plus rollback capability.
      Docs: none
      Tests: `tests/test_daemon.py, tests/test_plugin_installer.py, tests/test_settings.py`

- [ ] ID: TASK-008 | Files: `tests/test_api_server.py, tests/test_auth.py, tests/test_api_profiles.py` | Dep: TASK-002, TASK-003, TASK-004 | Agent: test-writer | Description: Expand API security regressions for loopback enforcement, bootstrap/auth hardening, rate limiting, and read/write route policy boundaries.
      Acceptance: New tests cover success and refusal paths with mocked filesystem/network behavior only, and the API security slice remains green without root or external services.
      Docs: none
      Tests: `tests/test_api_server.py, tests/test_auth.py, tests/test_api_profiles.py`

- [ ] ID: TASK-009 | Files: `tests/test_safe_mode.py, tests/test_settings.py, tests/test_confirm_dialog.py, tests/test_daemon.py` | Dep: TASK-005, TASK-006, TASK-007 | Agent: test-writer | Description: Add focused UX and daemon regressions for Safe Mode defaults, settings persistence, risk/revert dialog rendering, and default-off plugin auto-update behavior.
      Acceptance: Tests cover first-run defaults, explicit opt-in behavior, dialog fallback behavior, and daemon plugin update safety with all system calls mocked via `@patch`.
      Docs: none
      Tests: `tests/test_safe_mode.py, tests/test_settings.py, tests/test_confirm_dialog.py, tests/test_daemon.py`

- [ ] ID: TASK-010 | Files: `loofi-fedora-tweaks/version.py, pyproject.toml, loofi-fedora-tweaks.spec` | Dep: TASK-008, TASK-009 | Agent: code-implementer | Description: Eliminate version drift by bumping the canonical version files from `2.11.0` to `3.0.0` with codename `Aegis` after the stabilization slice is verified.
      Acceptance: `version.py`, `pyproject.toml`, and the RPM spec report identical `3.0.0` metadata and no runtime path still exposes stale `2.11.0` values.
      Docs: none
      Tests: `tests/test_api_server.py`

- [ ] ID: TASK-011 | Files: `SECURITY.md, CHANGELOG.md, README.md, docs/releases/RELEASE-NOTES-v3.0.0.md` | Dep: TASK-010 | Agent: release-planner | Description: Document the v3 API threat model, version-consistency cleanup, and new safety defaults in release-facing documentation.
      Acceptance: `SECURITY.md` documents API trust boundaries and disclosure guidance, CHANGELOG/README reflect shipped behavior only, and release notes summarize verified v3 stabilization outcomes.
      Docs: SECURITY, CHANGELOG, README, RELEASE-NOTES
      Tests: none
