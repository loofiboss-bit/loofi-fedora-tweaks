# Tasks — v23.0.1 "Compass"

## Contract

- [x] ID: T1 | Files: `loofi-fedora-tweaks/config/loofi-fedora-tweaks.service`,
  `tests/test_fedora44_readiness.py` | Dep: none | Agent: Release Engineer |
  Description: Permit the daemon to write only its existing config and state
  directories under the hardened user-service sandbox.
  Acceptance: `ProtectHome=read-only` remains active, both application-owned
  paths are explicit, and a regression test covers the unit contract.
  Docs: `docs/releases/RELEASE-NOTES-v23.0.1.md`
  Tests: `test_daemon_unit_allows_only_its_required_user_state_paths`
- [x] ID: T2 | Files: version, spec, pyproject, changelog, release notes |
  Dep: T1 | Agent: Release Engineer | Description: Bind the hotfix to a new
  immutable v23.0.1 release line.
  Acceptance: Version metadata is synchronized and v23.0.0 remains untouched.
  Docs: `CHANGELOG.md`, `docs/releases/RELEASE-NOTES-v23.0.1.md`
  Tests: `scripts/bump_version.py --check`
- [x] [post-publish] Publish and verify exact v23.0.1 GitHub assets,
  attestations, COPR packages, signatures, clean installation, host upgrade,
  CI, CodeQL, and wiki readback.
  - Public v23.0.1 evidence passed. Real-host qualification then exposed the
    remaining runtime/state sandbox boundary completed by v23.0.2.
