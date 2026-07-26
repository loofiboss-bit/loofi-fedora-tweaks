# V21 Resolve Public Release Evidence

**Status:** COMPLETE

**Release date:** 2026-07-26

**Release commit:** `843760c4fe2725d093a977554badf8d1eb2451be`

## GitHub lineage and automation

- The annotated `v21.0.0` tag peels to the exact release commit.
- Auto Release Pipeline
  [30204640746](https://github.com/loofiboss-bit/loofi-fedora-tweaks/actions/runs/30204640746)
  completed successfully, including tests, Fedora Review, RPM and Flatpak
  installation smoke tests, tag creation, GitHub publication, and COPR.
- CI
  [30204640772](https://github.com/loofiboss-bit/loofi-fedora-tweaks/actions/runs/30204640772)
  and CodeQL
  [30204640677](https://github.com/loofiboss-bit/loofi-fedora-tweaks/actions/runs/30204640677)
  completed successfully for the release commit.
- Historical occupied v21 lineages remain available as
  `legacy-v21.0.0-ux-stabilization` and
  `legacy-v21.0.1-python-jose-packaging`.

## GitHub Release

[Loofi Fedora Tweaks v21.0.0 — Resolve](https://github.com/loofiboss-bit/loofi-fedora-tweaks/releases/tag/v21.0.0)
is public, non-draft, and non-prerelease. Independent download and readback
verified exactly eight assets:

1. Base, API, and daemon Fedora 44 RPMs.
2. The Flatpak bundle.
3. The source distribution.
4. `SHA256SUMS.txt`.
5. The CycloneDX SBOM.
6. The in-toto/SLSA provenance statement.

Every checksum passed. The SBOM subjects matched the five product artifacts,
and provenance resolved the release tag to the exact release commit.

## COPR and clean Fedora installation

- COPR build
  [10774741](https://copr.fedorainfracloud.org/coprs/loofitheboss/loofi-fedora-tweaks/build/10774741/)
  reached terminal API state `succeeded` for source package
  `1:21.0.0-1` and chroot `fedora-44-x86_64`.
- Public repository metadata was refreshed after the successful build.
- A new `fedora:44` container enabled the public
  `loofitheboss/loofi-fedora-tweaks` repository and installed the package
  without local artifacts or preinstalled application packages.
- RPM readback returned
  `loofi-fedora-tweaks 1:21.0.0-1.fc44 noarch`.
- Both `loofi-fedora-tweaks --version` and
  `loofi-fedora-tweaks --cli --version` returned `21.0.0`.

## Atomic and documentation boundary

Resolve does not change rpm-ostree command construction, deployment
verification, reboot authority, or package execution policy. The physical
Fedora Kinoite 44 installation, staged deployment, reboot, exact booted
checksum, replacement, and System Check evidence remains the V19
certification referenced by
[V21 Phase 4](V21_PHASE4_PLATFORM_QUALITY.md). Current v21 requalification
covered 170 Traditional/Atomic policy and deployment-contract tests. No new
physical Kinoite reboot was claimed for v21.

Repository release notes, roadmap, task contract, documentation index, and
source-controlled wiki were updated to the completed public state. The wiki
publication workflow provides the independent public documentation readback.
