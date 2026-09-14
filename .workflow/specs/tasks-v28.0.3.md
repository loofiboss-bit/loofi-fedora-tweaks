# Tasks — v28.0.3 "Ease"

Status: public release and post-publication closure complete for direct
maintenance execution and non-blocking physical/manual evidence.

## Patch scope

- [x] ID: UX-001 | Files: `loofi-fedora-tweaks/ui/maintenance_updates.py`, `loofi-fedora-tweaks/ui/maintenance_direct.py` | Dep: none | Description: Run supported system and Flatpak updates from Updates & Apps through one asynchronous Action Center flow.
  Acceptance: Preparation, optional confirmation, execution, verification, and final result stay on the originating page; normal system and Flatpak updates require no extra app confirmation.
  Docs: `ARCHITECTURE.md`, `docs/USER_GUIDE.md`, `docs/VERIFIED_MAINTENANCE.md`
  Tests: Direct update, confirmation, cancellation, duplicate-click, navigation, and result-state regression coverage.
- [x] ID: UX-002 | Files: `loofi-fedora-tweaks/core/actions/contracts.py`, `loofi-fedora-tweaks/core/actions/eligibility.py`, `loofi-fedora-tweaks/core/actions/assurance.py` | Dep: UX-001 | Description: Separate technical risk from interaction policy and bind confirmations to the prepared scope.
  Acceptance: Automatic policies cannot downgrade high risk; firmware, removal, rollback, and sensitive changes use one concrete confirmation; persisted `review_first` remains respected locally.
  Docs: `ARCHITECTURE.md`, `docs/ADVANCED_ADMIN_GUIDE.md`
  Tests: Eligibility, changed-scope, review-first, confirmation, and unsupported-backend tests.
- [x] ID: STATE-001 | Files: `loofi-fedora-tweaks/core/state/version_constants.py`, `loofi-fedora-tweaks/core/actions/stores.py`, `loofi-fedora-tweaks/core/state/migrations.py`, `loofi-fedora-tweaks/core/state/inventory.py`, `loofi-fedora-tweaks/core/state/backup.py` | Dep: UX-001 | Description: Synchronize Action Center plan and run state on schema v4 with safe migration and future-format preservation.
  Acceptance: v4 reads without false future warnings, supported older formats migrate, and unknown future state remains read-only with actionable diagnostics.
  Docs: `docs/STATE_INTEGRITY.md`, `ARCHITECTURE.md`
  Tests: Current, older, future, malformed JSONL, migration, and backup validation tests.
- [x] ID: DOC-001 | Files: active guides, wiki mirrors, `ROADMAP.md`, `SECURITY.md`, `CONTRIBUTING.md`, `docs/RELEASE_CHECKLIST.md` | Dep: UX-001 | Description: Describe direct execution and make physical/manual qualification supplementary evidence.
  Acceptance: Active documentation no longer requires navigation to Changes for daily updates and explicitly records manual/physical checks as verified, pending, or unverified without blocking publication.
  Docs: All active documentation and release guidance.
  Tests: Release-doc and wiki mirror checks.
- [x] ID: REL-001 | Files: version metadata, AppStream metadata, changelog, release notes, workflow specs | Dep: UX-001, UX-002, STATE-001, DOC-001 | Description: Synchronize v28.0.3 Ease release metadata and automated publication contracts.
  Acceptance: Version, codename, release notes, changelog, roadmap, AppStream metadata, active docs, and race lock agree on v28.0.3.
  Docs: `README.md`, `ROADMAP.md`, `CHANGELOG.md`
  Tests: `just verify`, `just validate-release`, packaging, adapter, and security checks.

## Release gates

- [x] ID: REL-002 | Files: CI and release workflows | Dep: REL-001 | Description: Keep automated tests, static checks, packaging, security, and documentation as the publication gates.
  Acceptance: Canonical tag-driven workflow can publish without a physical/manual test prerequisite.
  Docs: `docs/RELEASE_CHECKLIST.md`, `SECURITY.md`
  Tests: CI workflow and release-doc validation.
- [x] [post-publish] ID: REL-003 | Files: `docs/reports/V28.0.3_RELEASE_PUBLICATION.md`, public GitHub/COPR/wiki surfaces | Dep: REL-002 | Description: Record exact tag lineage, workflow runs, assets, checksums, attestations, COPR metadata, wiki readback, and supplementary physical/manual statuses after publication.
  Acceptance: Every named public surface is independently read back; any unrun physical/manual surface is explicitly recorded as `unverified` and does not block closure.
  Docs: `docs/reports/V28.0.3_RELEASE_PUBLICATION.md`
  Tests: Public readback commands and checksum verification.

## Boundaries

- No host installation, reboot, service enablement, desktop configuration change,
  automatic retry, rollback, or automatic reboot is part of this release task.
- Existing tags and releases remain immutable; the release uses the new v28.0.3
  patch identity.
