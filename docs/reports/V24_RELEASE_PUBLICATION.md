# V24 Public Release Evidence

## Result

v24.0.0 "Flow" is publicly released and independently verified. The canonical
tag, GitHub release, CI and CodeQL, eight release assets and attestations,
checksums, SBOM, provenance, COPR Fedora 44 packages, signatures, a clean
disposable Fedora 44 install, and the public wiki all passed readback.

## Exact lineage and workflows

- Release commit: `709faf837649989724b3d744b60dae538b5cec8b`
- Annotated tag object: `d5d8173417b7074a0683a106ab710a61a8b2944b`
- Tag peeled commit: `709faf837649989724b3d744b60dae538b5cec8b`
- Auto Release Pipeline: `31251722128` — success
- CI: `31251722118` — success
- CodeQL: `31251721907` — success
- Wiki publication: `31251722103` — success
- GitHub release: `https://github.com/loofiboss-bit/loofi-fedora-tweaks/releases/tag/v24.0.0`

The earlier lightweight `v24.0.0` target
`dd2a23f8bfb837d3f20e2fc65e63c21a11cb8cd8` ("Power Features") is preserved
under `legacy-v24.0.0-power-features` before the canonical Flow tag was
created.

## GitHub artifacts

The public release exposes eight uploaded assets. A fresh download verified
all seven payload entries in `SHA256SUMS.txt`:

| Asset | SHA-256 |
| --- | --- |
| `loofi-fedora-tweaks-24.0.0-1.fc44.noarch.rpm` | `30cd7eb7f71ab87ebfcac85975eab926097e2526f4eec7a603567a9ceb730a64` |
| `loofi-fedora-tweaks-api-24.0.0-1.fc44.noarch.rpm` | `680f750c80de3fbead05bc45e51ef648c93e6b1d397e3898e7aa380d5215e249` |
| `loofi-fedora-tweaks-daemon-24.0.0-1.fc44.noarch.rpm` | `44009b185106596bfcaad3f487f03a49c016a259769bdb88842f7ee3590d9175` |
| `loofi-fedora-tweaks-v24.0.0.flatpak` | `740f7a177ee1d9549fbbd383490156b1d949b99c7ec82e16f4751676d36a77d7` |
| `loofi-fedora-tweaks.cdx.json` | `2419109a880f3b992a5c7cbe02a53a6082ece8f0708fab89bd92534343c52bd6` |
| `loofi-fedora-tweaks.intoto.jsonl` | `682cfd7921e2eaa241a52c74e7e844af76a0ed05533ef8f56d40c0b1fe82fa7f` |
| `loofi_fedora_tweaks-24.0.0.tar.gz` | `c6b510ecefd5e9bc4647fa968c251e1bfbd67a4d9f2c63eb22e356be47b31d04` |

All eight assets passed `gh attestation verify` with the repository, signer
workflow, and exact source digest enforced. The CycloneDX SBOM identifies
`loofi-fedora-tweaks` v24.0.0. The SLSA v1 provenance binds tag `v24.0.0`, the
release commit, and Auto Release run `31251722128`.

## COPR and clean installation

- COPR build: `10838092` — `succeeded`
- Chroot: `fedora-44-x86_64`
- Public EVR: `1:24.0.0-1.fc44`
- COPR signing-key fingerprint:
  `4079C862B1977B9BF49768354FE905DF539BA887`
- Main, API, daemon, and source RPM readback: digests and signatures OK

The release workflow installed v24.0.0 from the refreshed COPR repository in
its Fedora 44 container. An additional fresh local `fedora:44` disposable
container independently enabled the public repository, installed the package,
read `1:24.0.0-1.fc44.noarch` from RPM metadata, and read
`loofi-fedora-tweaks 24.0.0` from the CLI. The workstation host was not
modified.

## Public documentation

A fresh clone of the GitHub wiki at
`c520a59d27c5b38a9e835a1a640fcfc7da1c10d6` is byte-identical to the
source-controlled `wiki/` tree and identifies v24.0.0 "Flow" as the current
release with working release and release-note links.

## Explicitly unverified physical gates

The authorized blocker skip does not convert unavailable physical evidence
into a pass. These gates remain explicit:

- Fresh Fedora Atomic/Kinoite installation and reboot path: **unverified**
- Physical Fedora KDE Wayland interaction: **unverified**
- Manual keyboard-only journey: **unverified**
- Audible Orca journey: **unverified**

Automated offscreen screenshots and scale contracts do not stand in for these
physical or human-observed results.
