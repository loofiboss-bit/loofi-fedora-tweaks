# V23 Compass Public Release Evidence

**Status:** COMPLETE WITH AUTHORIZED PHYSICAL SKIPS

**Final public release:** v23.0.2 "Compass"

**Release date:** 2026-07-29

**Release commit:** `8d0a94eec17586ff2b0101ad460083fbf26ef9b7`

## Release lineage

- The annotated `v23.0.2` tag object
  `be47607faebdbfe6b2e9b0ae7dacb749f214855c` peels to the exact release
  commit.
- Auto Release Pipeline
  [30461966230](https://github.com/loofiboss-bit/loofi-fedora-tweaks/actions/runs/30461966230)
  completed successfully, including tests, Fedora Review, RPM and Flatpak
  smoke tests, exact tag creation, attestations, GitHub publication, COPR,
  and the workflow's public-package install readback.
- CI
  [30461966951](https://github.com/loofiboss-bit/loofi-fedora-tweaks/actions/runs/30461966951)
  and CodeQL
  [30461966045](https://github.com/loofiboss-bit/loofi-fedora-tweaks/actions/runs/30461966045)
  completed successfully for the release commit.
- The Fedora 44 local qualification passed 7,007 tests, 61 expected skips,
  1,184 subtests, and 86.26 percent coverage.
- The original pre-normalization `v23.0.0` tag object remains preserved as
  `legacy-v23.0.0-architecture-hardening`. Canonical v23.0.0 and the v23.0.1
  startup-sandbox hotfix remain immutable earlier Compass releases.

## GitHub Release

[Loofi Fedora Tweaks v23.0.2 — Compass](https://github.com/loofiboss-bit/loofi-fedora-tweaks/releases/tag/v23.0.2)
is public, non-draft, and non-prerelease. A fresh independent download
verified exactly eight assets:

1. `loofi-fedora-tweaks-23.0.2-1.fc44.noarch.rpm`
2. `loofi-fedora-tweaks-api-23.0.2-1.fc44.noarch.rpm`
3. `loofi-fedora-tweaks-daemon-23.0.2-1.fc44.noarch.rpm`
4. `loofi-fedora-tweaks-v23.0.2.flatpak`
5. `loofi_fedora_tweaks-23.0.2.tar.gz`
6. `SHA256SUMS.txt`
7. `loofi-fedora-tweaks.cdx.json`
8. `loofi-fedora-tweaks.intoto.jsonl`

`sha256sum -c SHA256SUMS.txt` passed for every product and evidence asset.
GitHub attestation verification passed for the three RPMs, Flatpak, source
distribution, SBOM, and in-toto evidence. The evidence verifier matched all
five product subjects, tag `v23.0.2`, workflow run `30461966230`, and exact
Git commit.

## COPR and clean Fedora installation

- COPR build
  [10788467](https://copr.fedorainfracloud.org/coprs/loofitheboss/loofi-fedora-tweaks/build/10788467/)
  reached terminal API state `succeeded` for source package
  `1:23.0.2-1` and chroot `fedora-44-x86_64`.
- Public repository metadata exposed the exact base, API, and daemon packages
  as `1:23.0.2-1.fc44 noarch`.
- Direct downloads of all three public RPMs passed header and payload SHA-256
  checks plus OpenPGP RSA/SHA256 verification with fingerprint
  `4079c862b1977b9bf49768354fe905df539ba887`.
- A fresh `fedora:44` container enabled only Fedora repositories plus the
  public project COPR and installed all three packages without local
  artifacts. `rpm -V` returned no differences.
- Installed CLI readback returned `23.0.2`, the authenticated API server
  constructed on loopback, and the installed unit retained its strict
  sandbox plus the private runtime/state directory contract.

## Real Fedora 44 host upgrade

The authorized Fedora 44 KDE host upgraded all three packages together from
`1:23.0.1-1.fc44` to `1:23.0.2-1.fc44`. Package verification returned no
differences. The daemon remained enabled, the API remained disabled, and no
service or desktop enablement was changed by the package transaction.

After `daemon-reload` and restart:

- the daemon was `active/running` with `NRestarts=0`;
- D-Bus `Ping` returned `pong`;
- the full Fedora 44 health snapshot returned `ok: true` with zero collection
  errors;
- the application runtime and XDG state directories were owned by the user
  with mode `0700`;
- the collector lease and rotating application log were created in those
  bounded directories;
- the journal contained no read-only filesystem, permission, traceback, or
  failure messages; and
- the deterministic user configuration content hash was identical before and
  after the upgrade.

The first immediate D-Bus call occurred before the process registered its
well-known bus name. Systemd still reported the service active with zero
restarts; the name appeared during the bounded readiness check and all
subsequent calls passed. This was an observed startup-readiness race in the
test command, not a daemon failure.

## Authorized physical skips

Fresh Atomic/Kinoite installation and reboot qualification, the manual
keyboard journey, and audible Orca narration remain explicitly unverified
under the user's authorized skip. Offscreen, Traditional Fedora, and prior
release evidence are not presented as substitutes for those physical gates.
