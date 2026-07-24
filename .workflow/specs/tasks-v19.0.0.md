# Tasks — v19.0.0 "Steward"

## Phase 0 — Authority, baseline, and scope lock

- [x] Confirm `master`, exact v18 tag lineage, public release evidence, and the
  preserved historical Sentinel tag.
- [x] Correct the current release, Action Center schema, and coverage statements
  in `ARCHITECTURE.md`.
- [x] Inventory health-related routes, aliases, saved-navigation behavior,
  stores, readers/writers, Home/recommendation IDs, and current action
  candidates.
- [x] Record deterministic Home states, current collector timings, startup
  evidence, screenshot evidence, and the Traditional/Atomic certification
  boundary.
- [x] Mark v19 as the sole active roadmap target and set the active race lock.
- [x] Add version-neutral product-contract and architecture validator entry
  points while retaining thin v18 compatibility wrappers.
- [x] Make no runtime product, route, state, or execution change.

## Implementation

- [x] P1: canonical PyQt-free System Check domain, closed collector profile,
  storage adapters, mapping validation, and migration decision.
- [x] P2: explicit cancellable Home check with no cold-start probes or polling.
- [x] P3: one canonical System Check page with route and persisted-data
  compatibility adapters.
- [x] P4: finding-to-Action Center handoff using audited action IDs and closed
  parameters only.
- [x] P5: explicit follow-up comparison, resolution states, support bundle,
  read-only API, and CLI parity.
- [x] P6: accessibility, performance, security, packaging, platform, and release
  readiness.

## Release-only gates

- [x] Certify the latest claimed Fedora Traditional target on a physical KDE
  session and the latest claimed Fedora Atomic target through an exact
  deployment/reboot/readback path.
- [x] Pass local full tests at 86 percent coverage, lint, mypy, architecture,
  stabilization, startup/check-duration, accessibility, security, packaging,
  and release-document gates.
- [x] Rebuild from the authorized exact release commit and pass final checksum,
  CycloneDX SBOM, in-toto provenance, and exact-commit readback gates.
- [x] Bump synchronized product metadata to v19.0.0 "Steward" only after every
  local release gate passes.
- [x] Tag or publish only after separate explicit authorization.

## Completion

- [ ] [post-publish] Verify canonical CI, CodeQL, tag lineage, release assets,
  checksums, SBOM, and provenance.
- [ ] [post-publish] Verify COPR terminal success and clean installation from the
  public repository.
- [ ] [post-publish] Read back public documentation and close the roadmap and
  race lock.
