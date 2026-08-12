# v25.0.4 “Proof” Public Release Evidence

Status: complete. The v25.0.4 public release, automated qualification, package
publication, and documentation readback passed. Physical and manual gates are
reported separately and remain explicitly `unverified`.

The historical `v25.0.0`–`v25.0.3` tags remain unchanged. Proof uses the first
unused v25 patch identity, `v25.0.4`, so the public release tag is bound to the
exact release commit without rewriting historical lineage.

## Release identity

| Field | Evidence |
| --- | --- |
| Repository | `loofiboss-bit/loofi-fedora-tweaks` |
| Release tag | [`v25.0.4`](https://github.com/loofiboss-bit/loofi-fedora-tweaks/releases/tag/v25.0.4) |
| Release commit | `d93deaf801edd1fe9f2e240e5eee243890ce09d1` |
| Tag object | `2d65b52f74dadb5258a114b1c66897fc744ec4e0` |
| Peeled tag commit | `d93deaf801edd1fe9f2e240e5eee243890ce09d1` |
| Canonical workflow | [run 31589208342](https://github.com/loofiboss-bit/loofi-fedora-tweaks/actions/runs/31589208342), `success` |
| CodeQL workflow | [run 31589207822](https://github.com/loofiboss-bit/loofi-fedora-tweaks/actions/runs/31589207822), `success` |
| GitHub release | [v25.0.4 “Proof”](https://github.com/loofiboss-bit/loofi-fedora-tweaks/releases/tag/v25.0.4), published, non-draft, non-prerelease |

The tag readback used `git ls-remote --tags` and proved that the annotated tag
peels to the exact release commit. The historical v25 tag objects and peeled
commits are recorded in [V25_VERSION_LINEAGE.md](V25_VERSION_LINEAGE.md).

## Public surfaces

| Surface | Status | Evidence |
| --- | --- | --- |
| GitHub Actions and CodeQL | passed | Canonical run `31589208342` and CodeQL run `31589207822` both completed successfully for the exact release commit. |
| GitHub release and assets | passed | The public release contains eight uploaded assets: three RPMs, Flatpak, source archive, `SHA256SUMS.txt`, CycloneDX SBOM, and in-toto provenance. |
| Checksums | passed | Fresh `gh release download v25.0.4` readback passed `sha256sum -c SHA256SUMS.txt` for all seven listed payload assets; the manifest hash is `sha256:10ff8fc1913d77bdcc1e96eb6d55c68f80464ae515e3302aba1720e6a24ad194`. |
| SBOM, provenance, attestations | passed | The canonical workflow recorded eight verified attestations. The downloaded base RPM also passed direct `gh attestation verify` readback. |
| COPR Fedora 44 build | passed | [Build 10855992](https://copr.fedorainfracloud.org/coprs/loofitheboss/loofi-fedora-tweaks/build/10855992/) reached terminal `succeeded` for `fedora-44-x86_64`; public repodata and all three RPM signatures were read back. |
| Wiki | passed | [Wiki publish run 31589208352](https://github.com/loofiboss-bit/loofi-fedora-tweaks/actions/runs/31589208352) succeeded; public `Home`, `Getting-Started`, and `Screenshots` pages identify v25.0.4 “Proof”. |

### GitHub asset hashes

The public release asset server reported these SHA-256 digests:

| Asset | SHA-256 |
| --- | --- |
| `loofi-fedora-tweaks-25.0.4-1.fc44.noarch.rpm` | `fe756564be019335268edadf9b259dbe2b6bbc58de5deca99d0956b723dc9961` |
| `loofi-fedora-tweaks-api-25.0.4-1.fc44.noarch.rpm` | `a32dbc643e439ef96b0c05b4d7c511f1c4c492b2f1cf0399e3ae92da2a29294c` |
| `loofi-fedora-tweaks-daemon-25.0.4-1.fc44.noarch.rpm` | `0c70d46fd3044e47c99e935661788f0dbb807284f1144aa4874430b17479db2b` |
| `loofi-fedora-tweaks-v25.0.4.flatpak` | `8b22f3f826233fdae1146ba1ac5c23e2f45bcd648dd2290da4ae8821a534cd57` |
| `loofi-fedora-tweaks.cdx.json` | `152ca0a0734f2d440e270a8f40d5ec41a0f3f53b4442d5010e712e0406f4fb28` |
| `loofi-fedora-tweaks.intoto.jsonl` | `36d5fd9c0111e5e5870aeb3a6c1a67350335f8cbb1fba17c6d119b8f3bccabde` |
| `loofi_fedora_tweaks-25.0.4.tar.gz` | `1e61b33e359f47e9994c70f35c8a13a1a9b9f3d799cf9459feb29edeade24715` |

## COPR and package readback

- Build: `10855992`, terminal state `succeeded`.
- Chroot: `fedora-44-x86_64`.
- Source EVR: `1:25.0.4-1`.
- Public repository: [loofi-fedora-tweaks COPR](https://copr.fedorainfracloud.org/coprs/loofitheboss/loofi-fedora-tweaks/).
- Public repodata: [repomd.xml](https://download.copr.fedorainfracloud.org/results/loofitheboss/loofi-fedora-tweaks/fedora-44-x86_64/repodata/repomd.xml), HTTP 200 after the public redirect.
- All three public RPMs reported `Header OpenPGP ...: OK`, `Header SHA256 digest: OK`, `Payload SHA256 digest: OK`, and `Legacy OpenPGP ...: OK`.
- Signing-key fingerprint: `4079C862B1977B9BF49768354FE905DF539BA887`.

The canonical Fedora review and RPM smoke jobs passed in the release workflow,
including package installation and version/help checks in the Fedora 44 CI
environment. This is package-path evidence, not proof of a real host or KDE
Wayland session.

## Physical and manual boundaries

Fedora KDE Wayland on the real desktop, a fresh Atomic/Kinoite host, Polkit
prompts and privileged execution on the host, reboot completion, keyboard and
screen-reader journeys, and manual recovery are not proved by the release
workflow. A clean physical Fedora KDE 44 installation remains `unverified`.
No manual blocker was bypassed or represented as passed; these gates require
separate authorized human qualification.
