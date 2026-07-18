# v15 Phase 10 Release Readiness

Date: 2026-07-18
Release: `v15.0.0 "Essentials"`
Status: released and publicly verified

## Outcome

The v15 implementation is published. Documentation, metadata,
screenshots, package descriptions, and workflow specs describe the shipped
six-destination Standard experience, optional Advanced destination, logical
core/specialist isolation, and preserved v14 trust contracts.

The historical pre-renormalization `v15.0.0 "Nebula"` annotated tag object is
preserved on origin as `legacy-v15.0.0-nebula`. The canonical `v15.0.0` tag now
peels to release commit `17aa8aa78cd3ac51d1d63da336ee25d4e5e3b4c1`.

## Compatibility preserved

- Action Center planning, confirmation, execution, verification, expiry,
  leases, history, interruption, CLI, and authenticated read-only API behavior.
- v14 settings, favorites, route aliases, state schemas, backup/restore,
  observability, and support-bundle contracts.
- Traditional and Atomic Fedora package/update behavior.
- Base, API, and daemon RPM subpackages with exact EVR dependencies.
- Existing CLI, API, daemon, and IPC entry contracts.

## Measurements

| Measure | v14 baseline | v15 median | Change |
| --- | ---: | ---: | ---: |
| Meaningful Home | 4552.202 ms | 151.924 ms | 96.66% faster |
| RSS | 107446 KiB | 76068 KiB | 29.20% lower |
| Imported modules | 527 | 288 | 45.35% lower |
| Imported `ui.*_tab` modules | 30 | 2 | 93.33% lower |
| Startup subprocess probes | 54 | 0 | eliminated |
| Active timers / QThreads | 9 / 2 | 0 / 0 | eliminated |

The Phase 6 workflow validator reported five canonical workflows, zero host
probes, and zero mutations.

## Verification

- `just release-prep`: passed.
- Full coverage suite: 7,622 passed, 40 skipped, 86.12% coverage.
- Workflow report suite: 7,622 passed, 40 skipped.
- Lint and mypy: passed.
- Release-doc, publish-ready task, stats, adapter-drift, requirement-sync, and
  packaging-manifest gates: passed.
- RPM: base, API, daemon, and SRPM built for Fedora 44.
- Flatpak: `loofi-fedora-tweaks-v15.0.0.flatpak` built successfully.
- sdist: `loofi_fedora_tweaks-15.0.0.tar.gz` built successfully.
- Fedora review contract and Phase 6 workflow validator: passed.
- Bandit CI profile: zero medium/high findings.
- Dependency audit: no known vulnerabilities. The local audit split the
  installed `dbus-python` 1.4.0 direct requirement from the fully resolved
  remaining requirements because the isolated resolver lacked local GLib
  development headers.
- Codex Security working-tree diff scan: 26/26 security-relevant files closed,
  zero plausible candidates.
- Installed Fedora package transaction dry-run: host `1:14.0.0-1.fc44` to the
  locally built `1:15.0.0-1.fc44` base/API/daemon set passed without mutation.
- Canonical real-app screenshots: regenerated and visually inspected.
- `git diff --check`: passed.

The RPM release gate uses `appstream-util validate-relax` and passed. The
stricter `appstreamcli validate` additionally reports the existing non-reverse-
DNS component-id warning and informational metadata suggestions. The desktop
validator reports the existing multiple-main-category hint. These do not block
the repository's established Fedora release gate.

## Public release evidence

- GitHub release: `v15.0.0`, published 2026-07-18, not a draft or prerelease.
- Release commit: `17aa8aa78cd3ac51d1d63da336ee25d4e5e3b4c1`.
- CI run `29628964016`, CodeQL run `29628963858`, and Auto Release Pipeline
  run `29628964018`: terminal success.
- Public assets: three RPMs, Flatpak, sdist, SHA256SUMS, CycloneDX SBOM, and
  in-toto/SLSA provenance downloaded and verified.
- Provenance: five subjects, source digest bound to the release commit, tag
  `v15.0.0`; SBOM metadata identifies version `15.0.0` with five components.
- Public RPM transaction dry-run from installed `1:14.0.0-1.fc44` to the
  downloaded base/API/daemon `1:15.0.0-1.fc44` set: passed without mutation.
- COPR build `10739754`, chroot `fedora-44-x86_64`: succeeded. The release
  workflow installed the public package and verified version `15.0.0`.
- Wiki commit `d0ecb6228d4fb8a089de99d9d3bd7de134212b93`: public Home text and canonical
  hero screenshot read back byte-for-byte.

Public asset SHA-256 digests:

| Artifact | SHA-256 |
| --- | --- |
| Base RPM | `fe6dc7a6dcb79e76988fd302f97557a2674036b0ab1c0db74faf41ea0a2ecf52` |
| API RPM | `551545348d18b7a546fc0061fefb9de9b1e516f5c8416589e13be9c07f617307` |
| Daemon RPM | `75de590c163900f574d33abc6f9c46c42ad9ec56726528d5ec113e65e7191c30` |
| Flatpak | `0a40c5b10fd8cd747f6439ea085cb9307cd6ec73f587f3021f66906f351a98ac` |
| sdist | `16d2b6206cac55d93470cf8b62d9874bc88bb641601fc86fab3725f6b6696ec4` |

## Remaining and deferred

No physical extras RPM ships in v15. The evidence-backed Phase 9 NO-GO remains
deferred to v16; logical component isolation is the shipped boundary.

The existing AppStream reverse-DNS warning, informational metadata suggestions,
and desktop multiple-main-category hint remain non-blocking under the
repository's established Fedora release gate. No other release issue remains.
