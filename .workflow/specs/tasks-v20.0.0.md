# Tasks — v20.0.0 "Continuity"

## Contract

- [x] ID: C1 | Files: `core/change_journal/*`, `utils/history.py` | Dep: none | Agent: Core | Description: Define the inert Trusted Change Journal and migrate legacy command-bearing history
  Acceptance: Source-owned records compose without a new durable database; legacy commands are discarded and never executed; future schemas fail closed
  Tests: `tests/test_change_journal.py`, `tests/test_history.py`
- [x] ID: C2 | Files: `core/actions/assurance.py` | Dep: C1 | Agent: Core | Description: Add exact DNF5 offline recovery and rpm-ostree rollback workflows
  Acceptance: Fresh preflight, explicit confirmation, reboot-aware verification, no automatic reboot, and no recovery for unverifiable transaction shapes
  Tests: `tests/test_action_center_assurance.py`
- [x] ID: C3 | Files: `ui/activity_recovery_tab.py`, `core/product_catalog_continuity.py` | Dep: C1 | Agent: UI | Description: Add Activity & Recovery to System
  Acceptance: No startup collection; keyboard-readable ledger; source readiness; conservative correlation wording; Action Center handoff only
  Tests: `tests/test_activity_recovery_tab.py`, navigation tests
- [x] ID: C4 | Files: `cli/main.py`, `cli/parser.py`, `api/routes/system.py` | Dep: C1 | Agent: Interfaces | Description: Add stable CLI and authenticated read-only API views
  Acceptance: CLI recovery creates a plan but never applies; API has no mutation endpoint; limits and source filters are bounded
  Tests: `tests/test_activity_interfaces.py`, `tests/test_main_cli_dispatch.py`
- [x] ID: C5 | Files: `core/executor/operations.py`, `core/actions/assurance.py`, `scripts/validate_product_contract.py` | Dep: C2 | Agent: Security | Description: Close remaining legacy CLI mutation paths
  Acceptance: Direct helpers never spawn mutations; every retained request maps to a named typed Action Center definition
  Tests: `tests/test_v20_mutation_boundary.py`
- [x] ID: C6 | Files: `ui/settings_tab.py`, `utils/navigation_mode.py` | Dep: C3 | Agent: UI | Description: Replace the global mode switch with always-available Specialist Tools
  Acceptance: No visible Standard/Advanced selector; persisted legacy values cannot hide product areas; safety stays action-specific
  Tests: `tests/test_v20_navigation.py`, `tests/test_settings_tab_ux.py`
- [x] ID: C7 | Files: `core/export/support_bundle_v12.py` | Dep: C1 | Agent: Diagnostics | Description: Add bounded journal evidence to the canonical support bundle
  Acceptance: At most 50 redacted events; source status included; no raw output or recovery command vectors
  Tests: `tests/test_support_bundle_v12.py`
- [x] ID: C8 | Files: version, roadmap, architecture, changelog, release docs | Dep: C1-C7 | Agent: Release | Description: Synchronize the v20 release candidate
  Acceptance: Version/codename/spec/race-lock/docs agree and the candidate is ready for the canonical publication workflow
  Tests: `just validate-release`
- [x] ID: C9 | Files: repository-wide | Dep: C1-C8 | Agent: Verification | Description: Run final local release gates
  Acceptance: Full tests, coverage, lint, mypy, architecture, product contract, release docs, packaging checks, and UI smoke pass with recorded evidence
  Tests: `just verify`, `just validate-release`
- [x] ID: C10 | Files: Git refs | Dep: C9 | Agent: Release | Description: Preserve the historical Synapse lineage
  Acceptance: `legacy-v20.0.0-synapse` publicly peels to the original Synapse commit before the canonical tag is replaced
- [ ] [post-publish] ID: C11 | Files: GitHub release | Dep: C10 | Agent: Release | Description: Verify canonical GitHub publication
  Acceptance: Exact tag lineage, canonical CI, release assets, checksums, SBOM, and provenance are independently read back
- [ ] [post-publish] ID: C12 | Files: COPR | Dep: C11 | Agent: Release | Description: Verify Fedora publication
  Acceptance: COPR reaches terminal succeeded and a clean Fedora 44 environment installs and reads back v20.0.0
- [ ] [post-publish] ID: C13 | Files: wiki, roadmap, race lock | Dep: C12 | Agent: Release | Description: Close public documentation and release state
  Acceptance: Public wiki is read back, roadmap is DONE, race lock is completed, and closure metadata records exact evidence

## Publication authority

The user authorized complete GitHub and COPR publication after C9 established
local readiness. C11-C13 remain open until each public surface is independently
read back.
