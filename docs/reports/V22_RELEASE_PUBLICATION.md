# V22 Alignment Public Release Evidence

**Status:** COMPLETE

**Release date:** 2026-07-28

**Release commit:** `31dc3ac7af53367f2bd257336ad0282cadea5fe7`

## GitHub lineage and automation

- The annotated `v22.0.0` tag object
  `dc0d8e46442f46669b65451f0aae4b4fecb0e777` peels to the exact release
  commit.
- Auto Release Pipeline
  [30375621830](https://github.com/loofiboss-bit/loofi-fedora-tweaks/actions/runs/30375621830)
  completed successfully, including tests, Fedora Review, RPM and Flatpak
  installation smoke tests, tag creation, GitHub publication, attestation,
  and COPR.
- CI
  [30375622954](https://github.com/loofiboss-bit/loofi-fedora-tweaks/actions/runs/30375622954)
  and CodeQL
  [30375619797](https://github.com/loofiboss-bit/loofi-fedora-tweaks/actions/runs/30375619797)
  completed successfully for the release commit.
- The final release suite passed 6,909 tests, 61 expected skips, 1,079
  subtests, and 86.65 percent coverage.

## GitHub Release

[Loofi Fedora Tweaks v22.0.0 — Alignment](https://github.com/loofiboss-bit/loofi-fedora-tweaks/releases/tag/v22.0.0)
is public, non-draft, and non-prerelease. Independent download and readback
verified exactly eight assets:

1. `loofi-fedora-tweaks-22.0.0-1.fc44.noarch.rpm`
2. `loofi-fedora-tweaks-api-22.0.0-1.fc44.noarch.rpm`
3. `loofi-fedora-tweaks-daemon-22.0.0-1.fc44.noarch.rpm`
4. `loofi-fedora-tweaks-v22.0.0.flatpak`
5. `loofi_fedora_tweaks-22.0.0.tar.gz`
6. `SHA256SUMS.txt`
7. `loofi-fedora-tweaks.cdx.json`
8. `loofi-fedora-tweaks.intoto.jsonl`

`sha256sum -c SHA256SUMS.txt` passed for every product and evidence asset.
`scripts/generate_release_evidence.py --verify` matched the SBOM and in-toto
subjects to the five product artifacts and resolved `v22.0.0` to the exact
release commit. GitHub artifact attestation verification passed for the three
RPMs, Flatpak, and source distribution.

## COPR and clean Fedora installation

- COPR build
  [10783672](https://copr.fedorainfracloud.org/coprs/loofitheboss/loofi-fedora-tweaks/build/10783672/)
  reached terminal API state `succeeded` for source package
  `1:22.0.0-1` and chroot `fedora-44-x86_64`.
- Public repository metadata exposed the exact base, API, and daemon packages.
- Fresh `fedora:44` containers enabled only the public
  `loofitheboss/loofi-fedora-tweaks` COPR in addition to Fedora repositories
  and installed the three packages without local artifacts.
- RPM readback returned `1:22.0.0-1.fc44 noarch` for all three packages and
  `rpm -V` returned no differences.
- Both `loofi-fedora-tweaks --version` and
  `loofi-fedora-tweaks --cli --version` returned `22.0.0`.
- The installed authenticated API surface constructed on loopback and served
  its OpenAPI document from `127.0.0.1`.
- The installed daemon imported the D-Bus GLib integration and remained in its
  GLib main loop until the bounded qualification timeout.
- Direct downloads of the three COPR RPMs passed header and payload digests
  plus OpenPGP RSA/SHA256 signature verification with fingerprint
  `4079c862b1977b9bf49768354fe905df539ba887`.

## Physical Fedora 44 and Atomic boundary

The exact clean release commit was exercised on the current Fedora 44 KDE
Wayland workstation. The real `MainWindow` completed 40 keyboard, visible
focus, dialog, mouse, wheel-equivalent, and resize cases. The live AT-SPI
validator resolved the accessibility bus and verified 379 nodes while Orca
50.2 was available. No offscreen or X11 result is presented as the physical
Wayland result.

Alignment does not change rpm-ostree command construction, staged deployment
verification, reboot authority, or Atomic execution policy. The physical
Fedora Kinoite 44 installation, staged deployment, reboot, exact booted
checksum, replacement, and Atomic System Check evidence remains the V19
certification in
[V19 Phase 6](V19_PHASE6_PLATFORM_CERTIFICATION.md), as carried forward by
[V21 Phase 4](V21_PHASE4_PLATFORM_QUALITY.md). The complete V22 regression and
package qualification revalidated the preserved Traditional/Atomic contracts.
No fresh Kinoite installation or reboot is claimed for V22. Fedora 44 remains
the supported Traditional and Atomic target; Fedora 45 remains preview-only.

## Public documentation

The release notes, roadmap, task contract, documentation index, installation
guide, testing metrics, and source-controlled wiki identify V22 Alignment as
the completed current release. The wiki publication workflow and a separate
public wiki clone provide the final documentation readback.
