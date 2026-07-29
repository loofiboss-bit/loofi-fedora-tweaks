# Release Notes -- v23.0.0 "Compass"

**Release Date:** 2026-07-29

**Theme:** Guided, evidence-bound troubleshooting

## Summary

Compass connects existing read-only diagnostics into one explicit
troubleshooting journey. A user selects one of six symptom profiles, starts a
bounded session, reviews current evidence and changes labelled **Possibly
related**, and receives exactly one safe next step. No new repair authority,
background collection, database, or mutating API is introduced.

Product metadata is synchronized to v23.0.0. The historical Architecture
Hardening tag object is preserved byte-identically as
`legacy-v23.0.0-architecture-hardening`, leaving canonical `v23.0.0` for the
Compass exact-commit release.

## Highlights

- One canonical Troubleshoot surface on the existing `diagnostics` route.
- Six closed Traditional/Atomic symptom profiles with exact source and total
  budgets.
- Explicit source state, freshness, applicability, and evidence-quality
  presentation.
- Conservative **Possibly related** journal matching.
- Compatible follow-up comparison that keeps Action Center `verified`
  separate from troubleshooting `resolved`.
- Versioned CLI collection, authenticated retrieval-only API access, and
  bounded Support Bundle v13 export.

## Changes

### Added

- Immutable PyQt-free session, profile, source-result, finding, next-step, and
  comparison contracts.
- Cooperative cancellation, bounded schema-v1 XDG retention, and read-only
  behavior for unknown future schemas.
- Read-only adapters for System Check, observability, Trusted Change Journal,
  Action Center, package/deployment, network, storage, boot, and application
  inventory evidence.
- Explicit `troubleshoot profiles`, `run`, `latest`, `show`, `compare`, and
  `export` CLI commands.
- Authenticated `GET /api/troubleshooting/latest` and
  `GET /api/troubleshooting/sessions/SESSION_ID` retrieval endpoints.

### Changed

- The existing `diagnostics` route now presents the guided Troubleshoot
  journey while preserving `diagnostics:watchtower`, `diagnostics:boot`, and
  the `logs` compatibility redirect.
- Support Bundle v13 may include one explicitly selected bounded
  troubleshooting case while retaining v2-v12 readers.
- Home adds a navigation-only troubleshooting task; it does not collect.

### Fixed

- Rejected nested command vectors, callbacks, renderers, credentials, tokens,
  raw output, malformed values, oversized evidence, and unsafe file modes at
  the relevant boundaries.
- Exposed the problem-profile selector through a visible AT-SPI label/buddy
  relationship.
- Kept API retrieval wrappers, CLI persistence reasons, and application
  inventory facts aligned with their stable contracts.

## Safety and compatibility

- All 81 routes, aliases, favorites, saved navigation, and six destinations
  remain intact.
- Action Center remains the only host-mutation authority and still requires
  separate planning, confirmation, execution, and verification.
- Traditional and Atomic evidence never mix.
- Home, navigation, search, page construction, service construction, and API
  GET requests never start troubleshooting collection.
- Existing settings, System Check, journal, observability, Action Center
  schema v4, CLI/API/daemon, and Support Bundle reader contracts remain
  compatible.

## Local qualification

- Phase 5 repository, architecture, route, security, package, startup, and
  coverage gates passed.
- 7,006 tests passed, 61 were skipped, and 1,184 subtests passed at 86.13
  percent global coverage in the final local release run.
- Fresh real-CLI collection passed for all six profiles on physical Fedora 44
  Traditional.
- Live Wayland AT-SPI exposure passed for the canonical Troubleshoot route.
- Local RPM, source distribution, Flatpak, checksum, CycloneDX SBOM, and
  in-toto provenance candidates passed without host installation.

See [Phase 5 qualification](../reports/V23_PHASE5_LOCAL_QUALIFICATION.md) and
[Phase 6 local release readiness](../reports/V23_PHASE6_LOCAL_RELEASE_READINESS.md).

## Release qualification boundary

- Fresh Fedora 44 Kinoite/Atomic profile qualification and manual
  keyboard-only plus audible Orca journeys remain explicitly unclaimed under
  the authorized skip.
- The canonical workflow binds `v23.0.0`, release artifacts, checksums, SBOM,
  provenance, and attestations to one exact release commit.
- Public package completion requires terminal COPR success, repository
  metadata, RPM signature verification, and clean Fedora 44 installation.
- Release completion requires independent CI, CodeQL, GitHub asset,
  attestation, COPR, package, wiki, and documentation readback.

The preserved legacy tag still peels to the pre-normalization Architecture
Hardening commit `adc4cef116d147bd5b845f0ec98c3a1970b8b054`; no historical
tag object or commit was overwritten or deleted.

## Upgrade notes

No user-data migration or automatic desktop/system setting change is required.
Support Bundle writes v13 while retaining v2-v12 readers. Troubleshooting
session storage is optional, bounded to 20 terminal sessions, and unknown
future schemas remain read-only.
