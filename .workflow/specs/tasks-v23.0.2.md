# Tasks — v23.0.2 "Compass"

## Contract

- [x] ID: T1 | Files: `loofi-fedora-tweaks/config/loofi-fedora-tweaks.service`,
  `tests/test_fedora44_readiness.py` | Dep: none | Agent: Release Engineer |
  Description: Give the daemon private systemd-managed XDG runtime and state
  directories under the hardened user-service sandbox.
  Acceptance: `ProtectSystem=strict` and `ProtectHome=read-only` remain active,
  both directories use mode `0700`, and a regression test covers the unit.
  Docs: `docs/releases/RELEASE-NOTES-v23.0.2.md`
  Tests: `test_daemon_unit_allows_only_its_required_user_state_paths`
- [x] ID: T2 | Files: version, spec, pyproject, changelog, release notes |
  Dep: T1 | Agent: Release Engineer | Description: Bind the completed sandbox
  contract to a new immutable v23.0.2 release line.
  Acceptance: Version metadata is synchronized and earlier releases remain
  untouched.
  Docs: `CHANGELOG.md`, `docs/releases/RELEASE-NOTES-v23.0.2.md`
  Tests: `scripts/bump_version.py --check`
- [x] [post-publish] Publish and verify exact v23.0.2 GitHub assets,
  attestations, COPR packages, signatures, clean installation, host upgrade,
  daemon health, CI, CodeQL, and wiki readback.
