# Release Notes -- v28.0.3 "Ease"

**Release Date:** 2026-09-14  
**Codename:** Ease  
**Theme:** Direct maintenance execution with clear risk boundaries

## Summary

v28.0.3 makes normal system and Flatpak updates executable from **Updates &
Apps**. Preparation, authorization when needed, execution, verification, and
the final result stay on the originating page while the existing Action Center
remains the only mutation authority.

Firmware, removal, rollback, and other sensitive changes use one concrete
confirmation tied to the prepared scope. Physical and manual qualification is
supplementary evidence; the release records its status without making it a
publication prerequisite.

## Highlights

- One click starts a normal system or Flatpak update after a fresh preflight.
- Firmware and sensitive operations show one focused confirmation with impact
  and restart information before any command runs.
- Changes prioritizes active work and history while retaining advanced review
  details.
- Action Center plan and run state use synchronized schema version 4.

## Changes

### Changed

- Added an independent interaction policy to the existing action catalog so
  technical risk is not confused with the amount of UI friction.
- Kept explicit `review_first` settings effective through local confirmation;
  changing the prepared scope requires a new confirmation.
- Preserved fresh preflight, privilege checks, mutation leases, verification,
  duplicate-click protection, and Traditional/rpm-ostree separation.
- Kept bootc and unknown mutation paths unavailable with actionable guidance.

### Added

- A shared asynchronous GUI flow for prepare, optional confirmation, execute,
  verify, awaiting-reboot, and failure states.
- Schema v4 constants, migration, backup validation, and future-format
  read-only handling for Action Center plans and runs.
- Release policy documentation that treats physical/manual checks as recorded
  supplementary evidence rather than blocking gates.

### Fixed

- Removed the forced Select → Review → Plan → Run → Verify navigation for
  everyday Updates & Apps actions.
- Corrected the plan/run schema mismatch that produced false future-format
  warnings.
- Prevented a direct GUI mode from bypassing an explicitly saved `review_first`
  preference or downgrading high-risk actions to automatic execution.

## Verification

Automated tests, lint, type checking, architecture checks, packaging, security
analysis, and release documentation are the publication gates. The exact
counts and public workflow links are recorded in the
[v28.0.3 release evidence](../reports/V28.0.3_RELEASE_PUBLICATION.md).

Physical Fedora, authorization-agent, reboot, Atomic, keyboard, Orca, and
clean-install checks are reported separately as verified, pending, or
`unverified`; they are never inferred from rootless/offscreen tests and do not
block publication.

## Upgrade Notes

No user-data migration is required. Existing Action Center state is migrated
to schema v4 when supported; unknown future formats remain preserved and
read-only. No automatic reboot, rollback, retry, or host installation is
introduced.
