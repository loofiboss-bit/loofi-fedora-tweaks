# Tasks — v28.0.2 "Ease"

Status: public release published; post-publication closure is being recorded
for the merged battery-service review fixes.

## Patch scope

- [x] ID: BAT-001 | Files: `loofi-fedora-tweaks/services/hardware/battery.py`, `tests/test_battery_service.py` | Dep: none | Description: Advertise only the implemented standard sysfs battery backend and remove the unused HP BIOS path.
  Acceptance: Unsupported firmware-specific hardware is reported as unavailable and standard sysfs support remains explicit.
  Docs: `ARCHITECTURE.md`, `docs/releases/RELEASE-NOTES-v28.0.2.md`
  Tests: Battery support and unsupported-backend regression tests.
- [x] ID: BAT-002 | Files: `loofi-fedora-tweaks/services/hardware/battery.py`, `loofi-fedora-tweaks/utils/commands.py` | Dep: BAT-001 | Description: Route battery-service cleanup through validated privileged command builders with bounded execution.
  Acceptance: Disable, removal, daemon reload, and failed-state reset are ordered, validated, and fail closed on non-zero results, timeouts, or OS errors.
  Docs: `ARCHITECTURE.md`, `docs/releases/RELEASE-NOTES-v28.0.2.md`
  Tests: Cleanup ordering, return-code, exception, timeout, and command-builder tests.
- [x] ID: BAT-003 | Files: `tests/test_battery_service.py`, `tests/test_commands.py` | Dep: BAT-002 | Description: Protect the review fixes with focused regression coverage.
  Acceptance: The focused battery and command test suites pass and cover invalid paths and all cleanup failure branches.
  Docs: `docs/releases/RELEASE-NOTES-v28.0.2.md`
  Tests: 59 focused tests passed.

## Release gates

- [x] ID: REL-001 | Files: version metadata, active documentation, workflow specs | Dep: BAT-003 | Description: Synchronize v28.0.2 Ease metadata and release contracts.
  Acceptance: Version, codename, release notes, changelog, roadmap, AppStream metadata, active docs, and race lock agree on v28.0.2.
  Docs: `README.md`, `ROADMAP.md`, `CHANGELOG.md`
  Tests: `check_release_docs.py --require-publish-ready-tasks` and full local verification.
- [ ] [post-publish] ID: REL-002 | Files: release evidence report | Dep: REL-001 | Description: Record exact tag lineage, workflow runs, GitHub assets, checksums, attestations, COPR metadata, and public readback after canonical publication.
  Acceptance: Every named public release surface is independently read back and linked from the current documentation.
  Docs: `docs/reports/V28.0.2_RELEASE_PUBLICATION.md`
  Tests: Public readback commands and checksums verification.
- [ ] [post-publish] ID: REL-003 | Files: physical/manual qualification record | Dep: REL-002 | Description: Keep physical Fedora, authorization, reboot, Atomic, keyboard, Orca, and clean-install gates explicitly classified after publication.
  Acceptance: No rootless or offscreen result is presented as physical qualification.
  Docs: `docs/reports/V28.0.2_RELEASE_PUBLICATION.md`
  Tests: Manual gates are reported as verified, pending, or unverified with evidence.

## Boundaries

- No host installation, reboot, service enablement, or desktop configuration change is part of this release task.
- The immutable v28.0.1 tag and its public release remain unchanged.
