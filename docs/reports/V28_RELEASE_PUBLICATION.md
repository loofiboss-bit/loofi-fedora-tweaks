# V28.0.1 "Ease" — Public Release Evidence

**Status:** public release complete
**Publication date:** 2026-09-14
**Release:** [v28.0.1 Ease](https://github.com/loofiboss-bit/loofi-fedora-tweaks/releases/tag/v28.0.1)

This report records the release identity, automated qualification, public
artifacts, COPR publication, and independent readback for v28.0.1. Physical
and manual Fedora qualification remains separate evidence and is not inferred
from CI, containers, rootless checks, or offscreen tests.

## Release identity

| Evidence | Result |
| --- | --- |
| Pull request | [PR #39](https://github.com/loofiboss-bit/loofi-fedora-tweaks/pull/39), merged 2026-09-14 |
| Master merge commit | `a2e28aaec0fb518b9c2941bcee3060cf50f76257` |
| Annotated tag | `v28.0.1` |
| Tag object | `c371e2c110c24843cbe970a8ec575c13a06d0ff2` |
| Peeled tag target | `a2e28aaec0fb518b9c2941bcee3060cf50f76257` |
| Historical lineage | `v28.0.0` remains unchanged as the workflow-reset record |
| GitHub release | Public, non-draft, non-prerelease |

The tag was created by the canonical master-push workflow after the blocking
checks passed. The tag was independently resolved through GitHub's annotated
tag object and its peeled commit matches the master merge commit exactly.

## Automated qualification

| Gate | Evidence | Result |
| --- | --- | --- |
| Pull-request CI | [CI run 34827911043](https://github.com/loofiboss-bit/loofi-fedora-tweaks/actions/runs/34827911043) | passed |
| Pull-request CodeQL | [CodeQL run 34827907239](https://github.com/loofiboss-bit/loofi-fedora-tweaks/actions/runs/34827907239) | actions and Python passed |
| Canonical release pipeline | [run 34828102923](https://github.com/loofiboss-bit/loofi-fedora-tweaks/actions/runs/34828102923) | passed |
| Deterministic local suite | 4,790 passed, 73 skipped, 830 subtests passed | passed |
| Maintained coverage | 86.66% against the maintained 85% blocking gate | passed |
| Fedora review | [job 103925685456](https://github.com/loofiboss-bit/loofi-fedora-tweaks/actions/runs/34828102923/job/103925685456), Fedora 44 container | passed |
| RPM smoke test | [job 103927040076](https://github.com/loofiboss-bit/loofi-fedora-tweaks/actions/runs/34828102923/job/103927040076), Fedora 44 install and CLI smoke | passed |
| COPR publication and install | [job 103927621091](https://github.com/loofiboss-bit/loofi-fedora-tweaks/actions/runs/34828102923/job/103927621091) | passed; installed version `28.0.1` |

The release pipeline also passed the release-doc, packaging, architecture,
product-contract, adapter-drift, lint, typecheck, security, and stabilization
gates. The planned repository-wide 90% coverage target remains open.

## GitHub release assets

The public release contains the RPM, source distribution, checksum manifest,
CycloneDX SBOM, and in-toto provenance generated from the tagged commit:

| Asset | Public SHA-256 |
| --- | --- |
| `loofi-fedora-tweaks-28.0.1-1.fc44.noarch.rpm` | `ceaac9d49d64692ac5bd108b2a434e59bd1398ac77747e14fe833df839a9ed2a` |
| `loofi-fedora-tweaks.cdx.json` | `afab2198c626d5f71430b92b1834a065886e26ee52fbda4f471c127cd01e338e` |
| `loofi-fedora-tweaks.intoto.jsonl` | `923a0b68dcaeb1d842608995d4115065bc5c75532f6c9d53248ad2f6c7d93354` |
| `loofi_fedora_tweaks-28.0.1.tar.gz` | `f2cd5df0ffdb9ec3ab7cc6f206d3fba6a8e3baa9313abf68ee07d64c4424ed1c` |
| `SHA256SUMS.txt` | `e64ff1d772db62988479a3054dccc6b0d8cf5321b0441e027834e1f828e4c328` |

An independent download of all five public assets passed
`sha256sum -c SHA256SUMS.txt`. GitHub artifact-attestation verification
returned one valid SLSA provenance attestation for both the public RPM and the
source distribution; the attested subject set contains all five exact release
assets.

## COPR publication

| Evidence | Result |
| --- | --- |
| Project | [`loofitheboss/loofi-fedora-tweaks`](https://copr.fedorainfracloud.org/coprs/loofitheboss/loofi-fedora-tweaks/) |
| Build | [10983641](https://copr.fedorainfracloud.org/coprs/loofitheboss/loofi-fedora-tweaks/build/10983641) |
| Chroot | `fedora-44-x86_64` |
| Build state | `succeeded` |
| Package EVR | `1:28.0.1-1.fc44` (`noarch`) |
| Public result repository | [COPR results](https://download.copr.fedorainfracloud.org/results/loofitheboss/loofi-fedora-tweaks/fedora-44-x86_64/) |
| Public RPM | [`loofi-fedora-tweaks-28.0.1-1.fc44.noarch.rpm`](https://download.copr.fedorainfracloud.org/results/loofitheboss/loofi-fedora-tweaks/fedora-44-x86_64/Packages/l/loofi-fedora-tweaks-28.0.1-1.fc44.noarch.rpm) |
| Public RPM SHA-256 | `23dc21ed3dc2c590016993d1213e64d336c128f069b42eec55591789e0b7e058` |
| RPM signature | OpenPGP V4 RSA/SHA256, fingerprint `4079C862B1977B9BF49768354FE905DF539BA887`, header and payload verification passed |
| Workflow installation check | COPR repository installation succeeded with exact version `28.0.1` |

The public COPR RPM was downloaded independently, its NEVRA was read back with
RPM metadata, its SHA-256 was calculated, and its header and payload
signatures were verified.

## Documentation and wiki

The active README, architecture, roadmap, changelog, release notes, workflow
specifications, user guides, AppStream metadata, and repository wiki sources
identify v28.0.1 Ease as the public release. The Getting Started guide remains
byte-identical between `docs/` and the repository wiki source.

The [post-release wiki workflow](https://github.com/loofiboss-bit/loofi-fedora-tweaks/actions/runs/34831752895)
completed successfully and published wiki commit
`0fe5d369dcfdf8889a7bd5a296cc7bc0c48e11fa`. A fresh public wiki checkout
contains the updated Home, Getting Started, and Screenshots pages; the
Getting Started file matches `docs/BEGINNER_QUICK_GUIDE.md` byte-for-byte.

## Remaining explicit limits

The following remain `unverified` for v28.0.1:

- repository-wide 90% coverage;
- physical Fedora 43/44 KDE/GNOME installation and navigation;
- physical rpm-ostree/Atomic qualification;
- Polkit allow, deny, and cancel behavior on a physical desktop;
- real reboot completion after an update;
- manual keyboard/focus, light/dark, 100–200% scale, small-screen, and
  five-user-session journeys;
- audible Orca qualification and benchmark comparison.

These limits are documented so users can distinguish automated release proof
from deferred physical and manual qualification work.
