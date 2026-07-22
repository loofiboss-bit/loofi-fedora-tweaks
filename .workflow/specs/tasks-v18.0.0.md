# Tasks — v18.0.0 "Haven"

## Phase 0 — Authority and baseline

- [x] Lock canonical plan, architecture, tasks, race lock, and legacy Sentinel
  archive without changing product version or remote state.
- [x] Record current tests, coverage, startup contract, route inventory,
  architectural hotspots, and mutation surface.
- [x] Preserve the historical Sentinel tag as
  `legacy-v18.0.0-sentinel`; public readback peels it to
  `f0cb0bf2be8a873de368341a400186158e12498f`.

## Implementation

- [x] P1: product catalog, Fedora release policy, operation classification, and static mutation gate.
- [x] P2: Action Center schema v3 and all supported host mutations converged.
- [x] P3: Marketplace retirement, external-code quarantine, Secret Service, and loopback-only API.
- [x] P4: Haven Action Center/Home/Updates/Security/Upgrade/Advanced UX.
- [x] P5: architecture, support-bundle/state, typing, stats, and docs quality.
- [x] P6 local: full regression, performance, security, packaging builds, and artifact smoke tests.

## Release-only gates

- [x] Prepare the authorized v18 candidate for canonical CodeQL and the
  tag-driven release workflow on `master`.
- [x] Certify Fedora 44 Traditional on the physical KDE Wayland host and the
  XCB/XWayland path; carry forward the signed Kinoite 44.1.7 KVM deployment and
  reboot proof with the current Haven Atomic regression matrix. Exact limits
  and evidence boundaries are recorded in `docs/reports/V18_PLATFORM_CERTIFICATION.md`.
- [x] Bump synchronized product metadata to v18.0.0 "Haven".

## Completion

- [ ] [post-publish] Record canonical CodeQL and Auto Release Pipeline results.
- [ ] [post-publish] Verify the exact GitHub tag, release assets, checksums,
  CycloneDX SBOM, and in-toto provenance.
- [ ] [post-publish] Verify the COPR build and a clean Fedora 44 repository install.
- [ ] [post-publish] Read back the public wiki and close roadmap and race-lock status.
