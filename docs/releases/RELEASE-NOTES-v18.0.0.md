# Release Notes: v18.0.0 "Haven"

Release candidate date: 2026-07-22<br>
Supported target: Fedora 44<br>
Preview target: Fedora 45

## Summary

Haven makes Action Center the local trust boundary for host changes. All 80
stable routes and 56 first-party action definitions project from reviewed
catalogs, and every host mutation entry point follows the same plan,
confirmation, execution, and independent verification lifecycle.

The public Marketplace and executable third-party Python plugins are retired.
Built-in page providers remain lazy-loaded, and local profiles remain
non-executable data.

## Trust boundary

- GUI, CLI, daemon, automation, and agent host mutations pass through
  `ActionCenterOrchestrator`.
- Daemon, agent, and scheduler paths may create plans but cannot confirm or
  execute them without a local user.
- Every first-party definition declares its operation class, supported Fedora
  variants, reboot policy, affected resources, parameters, preflight, preview,
  confirmation, verification, and recovery policy.
- Unsupported operations produce explicit `manual_only` plans. A command exit
  code never proves that a host change succeeded.
- Action plans and runs use schema v3. Writable v1 and v2 state migrates
  atomically with a last-known-good backup; unknown future schemas remain
  read-only.

## Extensions and local profiles

- External Python extension discovery, installation, hot reload, dependency
  resolution, reviews, analytics, and public preset distribution are absent
  from active and packaged code.
- Existing third-party directories remain user-owned. Loofi can inventory and
  export them but never imports or deletes their code.
- Legacy Marketplace routes resolve to an explanatory local-profiles view. The
  hidden `plugin-marketplace` CLI spelling returns `feature_retired` for stable
  compatibility handling.
- Local profile imports accept a closed, data-only schema. Accepted profiles
  become reviewable plans before any host setting changes.
- Application-owned providers still ship with the reviewed package and load on
  demand from stable catalog IDs and aliases.

## Secrets and API

- Gist and JWT secrets use Secret Service when persistent storage is available.
  Legacy plaintext is removed only after persistent readback succeeds.
- When Secret Service is unavailable, new secrets stay in memory for the
  current process. There is no plaintext fallback.
- The optional Web API rejects non-loopback binding and remains read-only apart
  from rate-limited token issuance. API keys can be rotated or revoked locally.

## Compatibility

- All existing route IDs and aliases still resolve. Retired Community routes
  open compatibility explanations instead of external content.
- Favorites, saved navigation, themes, lazy loading, CLI JSON envelopes, API
  reads, daemon and IPC reads, and Traditional/Atomic capability policy remain
  available.
- Existing extension files and historical release evidence are not deleted.

## Local verification

| Gate | Result |
| --- | --- |
| Full suite | 6,796 passed, 68 skipped, 16 warnings |
| Coverage | 86.24% |
| Lint and mypy | clean |
| Catalog and mutation gate | 80 routes; zero unclassified presentation mutations |
| Action Center catalog | 56 first-party definitions |
| Bandit | zero medium/high findings |
| Project dependency audit | no known application dependency vulnerabilities |
| RPM, source distribution, Flatpak | fresh local builds inspected successfully |
| Current Fedora 44 KDE host | Wayland 1920x1080 at 1.4x passed; XCB/XWayland smoke passed at requested 1180 width |

The recorded offscreen benchmark used one warmup and ten measured clean-profile
runs. Meaningful Home median was 142.042 ms and median RSS was 75,408 KiB.
Every measured run created one provider and reported zero subprocess probes,
active timers, and running QThreads.

The v18 certification carries forward the signed Fedora Kinoite 44 install and
real rpm-ostree reboot/readback evidence from v17. A fresh v18 Atomic guest
installation was not repeated; that boundary is recorded explicitly in the
platform certification report.

The 16 test warnings are known compatibility or test-environment warnings and
remain visible in the readiness report. The workspace development tool
`pip 26.1` has a reported advisory; it is not an application dependency or
packaged runtime component. `pip 26.1.2` contains the fix.

## Upgrade notes

- External Python plugins no longer execute. Their files remain in place for
  inventory and export.
- Replace public presets with explicit local JSON profile files. Imports reject
  unknown fields, unsafe paths, unsupported schemas, and files larger than
  1 MiB.
- Action Center v1 and v2 state migrates automatically when writable. Back up
  application state before downgrading to a version that does not understand
  schema v3.
- Fedora 44 is the release target. Fedora 45 remains preview-only.

## Publication status

This document describes the locally verified candidate. The following evidence
must still be completed and read back before the release is declared public:

- canonical CodeQL on the release commit;
- exact platform certification readback, including the stated carried-forward
  Atomic boundary;
- canonical `v18.0.0` Haven tag creation; the historical Sentinel tag is already
  preserved as `legacy-v18.0.0-sentinel`;
- GitHub release assets, checksums, SBOM/provenance, and exact-commit readback;
- Fedora 44 COPR build and independent repository install/readback.

See [V18_PHASE6_RELEASE_READINESS.md](../reports/V18_PHASE6_RELEASE_READINESS.md)
for the local evidence and remaining blockers.
