# V27.0.1 "Core" — Public Release Evidence

**Status:** public release complete  
**Publication date:** 2026-09-13  
**Release:** [v27.0.1 Core](https://github.com/loofiboss-bit/loofi-fedora-tweaks/releases/tag/v27.0.1)

This report records the independently read-back evidence for the V27 Core
release. The repository-wide 90% coverage target and physical/manual Fedora
qualification were explicitly deferred for this version; those gates remain
`unverified` and are not inferred from automated, rootless, or offscreen runs.

## Release identity

| Evidence | Result |
| --- | --- |
| Master merge commit | `eac3f3fd9a06513a4fb78a7cfa3dbd03625be6bd` |
| Annotated tag | `v27.0.1` |
| Tag object | `b4e3e6cb760f6ecb610410e1df9c7cfc397ba374` |
| Peeled tag target | `eac3f3fd9a06513a4fb78a7cfa3dbd03625be6bd` |
| Historical collision | `v27.0.0` remains unchanged as the Marketplace Enhancement history |
| GitHub release | Public, non-draft, non-prerelease |

The tag was created by the canonical master-push workflow after all blocking
checks passed. No historical tag was moved.

## Automated qualification

| Gate | Evidence | Result |
| --- | --- | --- |
| Pull-request CI | [run 34784139569](https://github.com/loofiboss-bit/loofi-fedora-tweaks/actions/runs/34784139569) | passed |
| Master CI | [run 34784282361](https://github.com/loofiboss-bit/loofi-fedora-tweaks/actions/runs/34784282361) | passed |
| CodeQL | [run 34784282578](https://github.com/loofiboss-bit/loofi-fedora-tweaks/actions/runs/34784282578) | actions and Python passed |
| Canonical release pipeline | [run 34784282392](https://github.com/loofiboss-bit/loofi-fedora-tweaks/actions/runs/34784282392) | passed |
| Deterministic test suite | 4,780 passed, 73 skipped, 0 failed | passed |
| Maintained-surface coverage | 86.94% measured locally; 85% blocking gate | passed |
| Fedora review | Fedora 44 container | passed |
| RPM smoke | Fedora 44 install, binary, version, CLI help | passed |

The release workflow uses the maintained-surface 85% gate for V27. The planned
repository-wide 90% target is intentionally a subsequent-release task.

## GitHub release assets

The public release contains exactly the RPM, source distribution, checksum
manifest, CycloneDX SBOM, and in-toto provenance generated from the tagged
commit:

| Asset | Public SHA-256 |
| --- | --- |
| `loofi-fedora-tweaks-27.0.1-1.fc44.noarch.rpm` | `1abd2c81a2e106a246bb0f5fa5f1778b2334bac96400d39a1a09b4b3c6868fc1` |
| `loofi-fedora-tweaks.cdx.json` | `e284081f0119c8cc1cf515a5070a907eb587023f6f498a88c3bd0cf39bb32108` |
| `loofi-fedora-tweaks.intoto.jsonl` | `94a3fe7d6b30336afaaf902fabe20a819e3367ae83ccbb2496eb6335de8b21b1` |
| `loofi_fedora_tweaks-27.0.1.tar.gz` | `80ba8ef2a3bd73b516db7e0e248cf667af071dec61cf8c523dc87abd4acdfe26` |
| `SHA256SUMS.txt` | `e23fca18fa40187ac2623283dd30bc872afeb4b1580b3ad8673374cec2a7bd2e` |

The downloaded public assets pass `sha256sum -c SHA256SUMS.txt`. GitHub
artifact-attestation verification returned one valid SLSA provenance
attestation for both the RPM and the source distribution.

## COPR publication

| Evidence | Result |
| --- | --- |
| Project | [`loofitheboss/loofi-fedora-tweaks`](https://copr.fedorainfracloud.org/coprs/loofitheboss/loofi-fedora-tweaks/) |
| Build | [`10982459`](https://copr.fedorainfracloud.org/coprs/build/10982459) |
| Chroot | `fedora-44-x86_64` |
| Build state | `succeeded` |
| Package EVR | `1:27.0.1-1.fc44` (`noarch`) |
| Public result repository | [COPR results](https://download.copr.fedorainfracloud.org/results/loofitheboss/loofi-fedora-tweaks/fedora-44-x86_64/) |
| Public RPM | [`loofi-fedora-tweaks-27.0.1-1.fc44.noarch.rpm`](https://download.copr.fedorainfracloud.org/results/loofitheboss/loofi-fedora-tweaks/fedora-44-x86_64/Packages/l/loofi-fedora-tweaks-27.0.1-1.fc44.noarch.rpm) |
| Public RPM SHA-256 | `1ad5c3600f0cd3b64bcbdd2eea2a37db4acf26f6d10f68982b9fad74f4f39fd0` |
| RPM signature | OpenPGP V4 RSA/SHA256, fingerprint `4079C862B1977B9BF49768354FE905DF539BA887` |
| Workflow installation check | `dnf` installed version `27.0.1` successfully |

The COPR repository metadata independently exposes the exact `27.0.1-1.fc44`
noarch package and the published key verifies both RPM header and payload
signatures.

## Documentation and wiki

- The README title, release badge/banner, installation guidance, scope, and
  qualification statement identify v27.0.1 Core.
- The active guides, architecture, AppStream metadata, changelog, release
  notes, roadmap, workflow specifications, and AI-adapter guidance are synced
  to the Core scope.
- [Wiki publish workflow 34784282371](https://github.com/loofiboss-bit/loofi-fedora-tweaks/actions/runs/34784282371)
  published wiki commit `f6747ffeef90033e6e38b5ceaed2218de1380821`; a fresh
  public wiki checkout contains the current Core pages and images.
- The repository description is now: “Desktop-neutral Fedora maintenance core
  with capability-aware inspection, reviewed changes, and verified outcomes.”

## Remaining explicit limits

The following are not release claims and remain `unverified` for v27.0.1:

- repository-wide 90% coverage;
- physical Fedora KDE/GNOME/Atomic installation and navigation;
- Polkit-agent behavior on a physical desktop;
- reboot completion after a real update;
- manual keyboard/focus journeys and audible Orca qualification.

These limits are documented so users can distinguish automated release proof
from the deferred physical qualification work.
