# Release Notes -- v29.0.1 "Utility"

**Release Date:** 2026-09-15
**Codename:** Utility
**Theme:** A curated Fedora utility organised around real user jobs

## Summary

v29.0.1 turns Loofi from a maintenance-oriented control center into a broader,
curated Fedora utility. Home now leads to four complete jobs: Install, Tune,
Fix, and Update. Activity & Recovery preserves history, reboot follow-up,
verification, and recovery without exposing the internal execution engine as a
normal destination.

The historical `v29.0.0` tag belongs to the earlier "Usability & Polish"
lineage and remains unchanged. `v29.0.1` is the unambiguous release identity
for Utility.

## Highlights

- Search and select several curated applications, review their source, and see
  a terminal result for each item.
- Start from editable Minimal, Recommended, or Power User Tune profiles that
  contain only implemented and verifiable operations.
- Diagnose a named symptom before choosing one supported repair, instruction,
  or native-settings handoff.
- Check and update System, Flatpak, and Firmware sources independently through
  one state-driven action per card.
- Find work by goal through the shared task catalog and finish ordinary work on
  the page where it started.

## Architecture and safety

- `TaskDescriptor` is the shared product contract for Home, navigation,
  search, owning pages, capability gating, risk, verification, and recovery.
- `ActionCenterOrchestrator` remains the sole host-mutation authority behind a
  shared PyQt-free operation controller and Qt adapter.
- `loofi.action-bundle/v1` records immutable application and Tune selections.
  Application members continue independently; ordered Tune members stop after
  the first unexpected failure.
- Legacy queue execution is disabled. Existing schema-v4 plans and runs remain
  readable, and old `changes` and `maintenance:action-center` routes open the
  matching Activity & Recovery state.
- No operation automatically retries, rolls back, reboots, or runs unattended.
  Unknown and bootc mutation paths remain fail-closed.

## Compatibility

The CLI command `changes` remains a v29 alias for Activity list and detail.
Explicit legacy plan application and run verification verbs remain available
for saved state during the migration. No user-data migration is required.

## Verification

The release gate includes isolated tests and coverage, lint, type checking,
architecture and product contracts, package builds, Fedora RPM smoke testing,
release-document validation, security analysis, checksums, SBOM generation,
and public artifact readback.

Physical KDE/GNOME, Traditional/Atomic, Polkit, reboot, keyboard, scaling, and
Orca checks are recorded separately as verified or `unverified`; offscreen and
CI results are never presented as physical qualification.

## Upgrade notes

Install or upgrade from the Fedora COPR repository:

```bash
pkexec dnf copr enable loofitheboss/loofi-fedora-tweaks
pkexec dnf upgrade loofi-fedora-tweaks
```

Existing application state remains in the standard XDG directories. The
release does not install a background daemon or web API and does not reboot or
change desktop settings during installation.
