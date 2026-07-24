# Release Notes -- v19.0.0 "Steward"

**Release Date:** Pending publication  
**Codename:** Steward  
**Theme:** Guided System Checks with verified resolution

## Summary

Steward connects the existing Home, diagnostics, saved health evidence, and
Action Center foundations into one explicit System Check journey. Checks remain
read-only, cancellable, timeout-bounded, privacy-safe, and separate from all
host mutation authority.

This document records the locally verified release candidate. No v19 tag,
GitHub release, COPR build, or public documentation update exists until
publication is separately authorized.

## Highlights

- Run one explicit quick check from Home without cold-start probes or polling.
- Review current findings, saved history, source availability, and supporting
  metrics on one canonical System Check page.
- Distinguish resolved, recurring, worsened, and unverifiable follow-up outcomes
  from Action Center execution and verification facts.
- Hand off only fresh, untampered, catalog-backed finding context to the existing
  Action Center review boundary.
- Inspect stable versioned System Check envelopes through the CLI and read-only
  loopback API.

## Safety and compatibility

- Findings contain evidence and identifiers, never commands or callbacks.
- System Check cannot confirm or execute an Action Center plan.
- Action Center still performs fresh preflight, explicit confirmation, audited
  execution, and action-specific verification.
- Schema v4 plan and run stores migrate supported v1-v3 state one version at a
  time with atomic replacement and last-known-good backup. Unknown future state
  remains read-only.
- The `health` route ID, aliases, favorites, saved navigation, CLI compatibility
  commands, snapshots, metrics, plans, and runs remain readable.
- Traditional and Atomic policy branches remain distinct. Fedora 44 stays the
  stable target; Fedora 45 stays preview-only.

## Changes

### Added

- A PyQt-free `core.system_check` domain with immutable result, finding,
  evidence, profile, comparison, presentation, and handoff contracts.
- A closed quick-check profile with per-source timeout, cancellation, partial
  completion, duration, and source-availability evidence.
- One background worker adapter used by Home and the canonical page.
- Stable System Check CLI commands: `health check`, `findings`, `history`, and
  `comparison`.
- Read-only API endpoints and bounded support-bundle fields for saved results
  and comparison evidence.
- Real-shell screenshot, AT-SPI, startup, and System Check duration gates.

### Changed

- Home now offers an explicit check action and refreshes from the persisted
  result only after completion.
- The stable `health` route presents System Check while older health and
  timeline aliases continue to resolve.
- Action Center schema v4 may retain bounded finding origin metadata without
  weakening the v18 trust boundary.
- Health and maintenance documentation now explains the check, evidence,
  Action Center review, and follow-up loop consistently.

### Fixed

- Atomic Fedora no longer treats the absence of DNF as package-health evidence.
  The stable `package-health` card uses rpm-ostree deployment guidance on
  Kinoite and other Atomic variants.
- Stale or tampered findings, invalid parameters, missing mappings, source
  mismatches, and future schemas fail closed without producing a command path.

## Verification

- **Tests:** 6,882 passed, 68 skipped, 1,032 subtests passed, 0 failed
- **Coverage:** 86.26% (86% enforced gate)
- **Lint/type/architecture:** passed
- **System Check median:** 442.335 ms against a 3,500 ms ceiling
- **Meaningful Home median:** 160.661 ms against the v18 172.618 ms ceiling
- **Startup RSS median:** 76,048 KiB against the 86,466 KiB ceiling
- **Startup contract:** one Home provider, zero subprocess probes, zero active
  hidden timers, zero running QThreads, and no System Check imports
- **Accessibility:** Wayland and XCB real-shell/AT-SPI matrices passed
- **Security:** Bandit and dependency audit passed
- **Packaging:** RPM, Flatpak, and source-distribution candidates built and
  passed their local checks
- **Atomic:** a signed Fedora Kinoite 44.1.7 image was freshly installed; the
  exact local RPM was staged and rebooted, the discovered Atomic regression was
  corrected, and a replacement deployment was staged, rebooted, and read back
  with an installed-source checksum matching the worktree

See
`docs/reports/V19_PHASE6_PLATFORM_CERTIFICATION.md`,
`docs/reports/V19_PHASE6_RELEASE_READINESS.md`, and the machine-readable
`docs/reports/V19_PHASE6_*.json` evidence.

## Upgrade notes

No user action is required for persisted state. Supported Action Center state
migrates automatically and atomically when first written; unknown future
schemas are never overwritten. Existing routes and CLI aliases remain valid.

The public installation instructions continue to resolve to the latest
published repository build until v19 publication is separately authorized.

## Deferred publication gates

- Create intentional release commits and verify the exact commit.
- Run canonical CI and CodeQL on that commit.
- Generate and read back final checksums, CycloneDX SBOM, and SLSA/in-toto
  provenance for the exact release artifacts.
- Tag and publish GitHub assets.
- Build and verify COPR packages and a clean repository installation.
- Read back public documentation, then close the roadmap and race lock.
