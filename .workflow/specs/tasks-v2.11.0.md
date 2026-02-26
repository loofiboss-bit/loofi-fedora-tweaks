# Tasks — v2.11.0

- [ ] ID: TASK-001 | Files: `ROADMAP.md, .workflow/specs/.race-lock.json, .workflow/reports/run-manifest-v2.10.0.json, .workflow/reports/run-manifest-v2.11.0.json` | Dep: - | Agent: project-coordinator | Description: Reconcile workflow metadata so v2.11.0 is the single active target and v2.10.0 is closed with canonical `vX.Y.Z` artifact naming.
  Acceptance: `ROADMAP.md` has exactly one ACTIVE version (v2.11.0), v2.10.0 is marked DONE, and both run manifests reflect the transition without short-tag artifacts.
  Docs: none
  Tests: `tests/test_workflow_runner_locks.py, tests/test_generate_workflow_reports.py`

- [ ] ID: TASK-002 | Files: `.workflow/specs/arch-v2.11.0.md` | Dep: TASK-001 | Agent: architecture-advisor | Description: Produce the v2.11.0 architecture contract that converts the v2.10 residual inventory into bounded implementation slices for network, firewall, and system services.
  Acceptance: Architecture spec defines method-level scope, non-goals, security constraints (pkexec-only, no `shell=True`, timeout enforcement), and dependency-safe sequencing for all implementation tasks.
  Docs: none
  Tests: none

- [ ] ID: TASK-003 | Files: `loofi-fedora-tweaks/services/network/network.py` | Dep: TASK-002 | Agent: backend-builder | Description: Harden network local write paths (`reactivate_connection_local`, `connect_wifi_local`, `disconnect_wifi_local`, `apply_dns_local`, `set_hostname_privacy_local`) to return strict success/failure from subprocess results.
  Acceptance: All five local write-path methods return `False` on non-zero command outcomes, preserve daemon-first call flow, and keep explicit subprocess `timeout` usage.
  Docs: none
  Tests: `tests/test_network_utils.py, tests/test_service_network.py`

- [ ] ID: TASK-004 | Files: `loofi-fedora-tweaks/services/network/network.py, loofi-fedora-tweaks/daemon/handlers/network_handler.py` | Dep: TASK-002 | Agent: backend-builder | Description: Tighten active-connection detection to avoid substring misclassification and keep daemon payload behavior stable.
  Acceptance: `get_active_connection_local()` parses nmcli output deterministically for wifi/ethernet cases, malformed output returns safe null-equivalent, and daemon handler compatibility is preserved.
  Docs: none
  Tests: `tests/test_network_utils.py, tests/test_ipc_fallback_modes.py`

- [ ] ID: TASK-005 | Files: `loofi-fedora-tweaks/services/security/firewall.py, loofi-fedora-tweaks/utils/commands.py` | Dep: TASK-002 | Agent: backend-builder | Description: Normalize firewall privileged command construction to project standards for local mutating operations and reload behavior.
  Acceptance: Local firewall mutators use `pkexec` command construction consistent with `PrivilegedCommand` patterns, never use `sudo`/`shell=True`, and all subprocess calls keep explicit timeouts.
  Docs: none
  Tests: `tests/test_firewall_manager.py, tests/test_service_security.py`

- [ ] ID: TASK-006 | Files: `loofi-fedora-tweaks/services/security/firewall.py, loofi-fedora-tweaks/daemon/handlers/firewall_handler.py, loofi-fedora-tweaks/services/system/system.py` | Dep: TASK-002 | Agent: backend-builder | Description: Finalize daemon/local parity decisions for `get_available_services()` and classify `has_pending_deployment()`/`get_layered_packages()` as intentionally local-read or daemonized paths.
  Acceptance: Each targeted read path has explicit behavior contract (daemon-first or intentional local-read), no privilege-scope expansion is introduced, and fallback semantics remain backward compatible.
  Docs: none
  Tests: `tests/test_firewall_manager.py, tests/test_system_service.py`

- [ ] ID: TASK-007 | Files: `tests/test_network_utils.py, tests/test_service_network.py, tests/test_ipc_fallback_modes.py` | Dep: TASK-003, TASK-004 | Agent: test-writer | Description: Add focused regression tests for strict return-code handling and active-connection parsing across local and daemon-fallback network paths.
  Acceptance: Tests cover success/failure branches for all hardened network methods, validate malformed-output handling, and pass without real subprocess/network execution.
  Docs: none
  Tests: `tests/test_network_utils.py, tests/test_service_network.py, tests/test_ipc_fallback_modes.py`

- [ ] ID: TASK-008 | Files: `tests/test_firewall_manager.py, tests/test_service_security.py, tests/test_system_service.py` | Dep: TASK-005, TASK-006 | Agent: test-writer | Description: Extend firewall and system regression suites for privileged command normalization, reload behavior, and local-read classification guarantees.
  Acceptance: Tests assert command construction and timeout behavior for firewall mutators, plus deterministic behavior for system read-path classification, with all external calls mocked via `@patch`.
  Docs: none
  Tests: `tests/test_firewall_manager.py, tests/test_service_security.py, tests/test_system_service.py`

- [ ] ID: TASK-009 | Files: `CHANGELOG.md, ROADMAP.md` | Dep: TASK-007, TASK-008 | Agent: release-planner | Description: Document v2.11.0 migration-slice outcomes and align roadmap status after verification is complete.
  Acceptance: CHANGELOG entry summarizes network/firewall/system hardening outcomes and ROADMAP status reflects completed v2.11.0 deliverables with no conflicting active target.
  Docs: CHANGELOG
  Tests: none

- [ ] ID: TASK-010 | Files: `README.md, docs/releases/RELEASE-NOTES-v2.11.0.md` | Dep: TASK-009 | Agent: release-planner | Description: Publish user-facing release documentation for v2.11.0, including migration constraints, safety posture, and verification commands.
  Acceptance: README version/release references and release notes accurately describe v2.11.0 changes, list executed verification commands, and avoid unsupported capability claims.
  Docs: RELEASE-NOTES
  Tests: none
