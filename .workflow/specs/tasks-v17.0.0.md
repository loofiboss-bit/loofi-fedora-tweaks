# Tasks — v17.0.0 "Assurance"

## Phase 0

- [x] Lock canonical scope, architecture, tasks, baseline, and mutation inventory.

## Implementation

- [x] P1: Action Center run schema v2, reboot-aware verification, typed action
  validation, v1 migration, and read-only API.
- [x] P2: independent Fedora, Flatpak, and firmware update plans and UI review.
- [x] P3: Fedora/Flatpak application install and remove plans.
- [x] P4: verified journal/autoremove cleanup and read-only diagnosis handoffs.
- [x] P5: verified Timeshift/Snapper recovery-point creation and UI/CLI convergence.
- [x] P6: full regression, startup/resource, security, packaging, release docs,
  version bump, and local release readiness.

## Completion

The user separately authorized full GitHub and COPR publication. Local release
gates, physical Fedora Atomic 44 reboot/readback, and fwupd host emulation are
complete. The following evidence is intentionally collected after publication:

- [ ] [post-publish] Verify exact GitHub tag/release lineage, assets, checksums,
  SBOM, and provenance.
- [ ] [post-publish] Verify the canonical workflow, COPR Fedora 44
  install/readback, and public wiki.
