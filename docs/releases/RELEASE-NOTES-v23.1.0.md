# Release Notes -- v23.1.0 "Compass"

**Release Date:** 2026-08-01

**Codename:** Compass (retained; no new codename)

**Theme:** Review-first system changes and clearer everyday workflows

## Summary

Loofi Fedora Tweaks v23.1.0 makes Action Center the enforceable boundary for
every public host-changing CLI and API operation. It also connects Home,
Updates, Install App, Troubleshoot, Cleanup, and Action Center into a simpler
state-led journey while preserving the six destinations and existing data.

## Highlights

- Every public operation is classified in one machine-readable registry.
- Legacy host-changing commands create a closed review plan or return safe
  manual guidance; they no longer apply changes as a side effect.
- Action Center groups work by lifecycle state and explains outcome,
  privilege, restart, verification, and recovery before execution.
- Home presents one calm unavailable state and one primary recommendation.
- Troubleshoot starts from symptoms, and Settings keeps a readable form width.
- Current documentation and privacy-safe Fedora 44 KDE Wayland screenshots now
  match the shipped product.

## Changes

### Changed

- Split CLI parser registration into domain-owned registrars while preserving
  command names, aliases, JSON envelopes, defaults, and exit behavior.
- Split MainWindow initialization into named responsibilities while preserving
  lazy page creation and startup order.
- Reworked the five core task surfaces around explicit state and next action.
- Kept Traditional and Atomic planning and verification behavior distinct.

### Added

- Added structural and behavioral gates that reject direct public host
  mutation, open-ended command plans, plan-and-apply requests, stale docs,
  broken links, wiki drift, missing screenshots, and retired visible routes.
- Added current Install App, Troubleshoot, Cleanup, and Action Center captures
  to the deterministic user-guide screenshot set.

### Fixed

- Corrected active metadata, help text, examples, release references, and
  generated-comment residue that no longer described the current product.
- Made API route-contract tests compatible with FastAPI's nested included
  routers without weakening the mutation-boundary assertions.
- Redacted host-specific network addresses and identifiers from generated
  documentation screenshots.

## Safety and compatibility

- No new route, provider, daemon, database, privileged API, marketplace, agent,
  AI feature, or arbitrary command runner is introduced.
- Existing routes, aliases, persisted settings, Action Center schema, and user
  data remain compatible.
- Installation and upgrade do not enable services or change desktop or system
  settings.
- The existing `Compass` metadata value is retained; v23.1.0 adds no codename.

## Verification

- **Tests:** 7,048 passed, 61 skipped, 0 failed, plus 1,217 subtests
- **Lint and typecheck:** passed with 0 errors
- **Coverage:** 86.36% (86% required)
- **Platform:** real Fedora 44 KDE Plasma 6.7.3 Wayland screenshots captured at
  140% scale; automated UI contracts cover 100% and 140% scale behavior

## Upgrade Notes

Upgrade all installed subpackages together. Existing plans, settings, and
application state remain in place; no user-data migration is required.
