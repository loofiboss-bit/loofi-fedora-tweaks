# v35.0.0 Everyday — public publication evidence

Published on October 21, 2026, at 10:51:13 UTC (Europe/Stockholm: 12:51:13).

## Lineage and canonical publication

- [GitHub Release](https://github.com/loofiboss-bit/loofi-fedora-tweaks/releases/tag/v35.0.0): public, final, neither draft nor prerelease; the latest-release API returns v35.0.0.
- Annotated tag object: `714aa95a6fca335e80a7dd893e9968403f3f72a1`.
- Tag target and release source: `56b07b1a41c3975bf24ec0acd2d16e2efebea18c`.
- [PR #72](https://github.com/loofiboss-bit/loofi-fedora-tweaks/pull/72) merged after successful CI and CodeQL.
- [Canonical release run 39586282152](https://github.com/loofiboss-bit/loofi-fedora-tweaks/actions/runs/39586282152): completed successfully, including validation, lint, typing, architecture, tests/coverage, security, documentation, RPM/SRPM/sdist, Fedora review, installed RPM smoke, immutable tag, GitHub publication and COPR verification.
- [Main CI 39586282121](https://github.com/loofiboss-bit/loofi-fedora-tweaks/actions/runs/39586282121): completed successfully. Native VM jobs were explicitly skipped under the maintainer's risk-based policy.

## Downloaded public assets

Fresh downloads of all five assets match GitHub API digests; all four entries
in `SHA256SUMS.txt` passed local checksum verification. The RPM reports
`1:35.0.0-1.fc44.noarch`. GitHub cryptographic attestation verification succeeded
with explicit source commit, `refs/heads/master` and the canonical signer
workflow enforced. Published provenance resolves the same source commit and
canonical run. These are public-asset hashes, separate from earlier local builds.

| Asset | SHA256 |
| --- | --- |
| `SHA256SUMS.txt` | `6df083bba469794679b0870251f5f9402b04550cfbfaa4894a664596f45eb492` |
| `loofi-fedora-tweaks-35.0.0-1.fc44.noarch.rpm` | `a89eb0611099ce1b20871396ba59e5cb52fc1ee820cf1ac0059d4fd217135482` |
| `loofi-fedora-tweaks.cdx.json` | `ddd28f211a0c4a9fed4b167fa4e514444da97b13a4d6066e8697da30fd3d8f71` |
| `loofi-fedora-tweaks.intoto.jsonl` | `68307adad883371f2d827f9077bd1d6407a11c27c3f1a2813032466b33aad5aa` |
| `loofi_fedora_tweaks-35.0.0.tar.gz` | `d3509f70ef63fd2cf952ada5644b145228e59f8a829dba2eeac178df398f8b49` |

## COPR

- [Build 11182269](https://copr.fedorainfracloud.org/coprs/loofitheboss/loofi-fedora-tweaks/build/11182269/): public API reports `succeeded`.
- Project `loofitheboss/loofi-fedora-tweaks`, chroot `fedora-44-x86_64`, source `1:35.0.0-1`.
- Fresh repository metadata and binary download independently identify `1:35.0.0-1.fc44.noarch`.
- Downloaded COPR RPM SHA256: `20091137b3bbe1785a7521770b61e3b9b4c16e32678b6cb29af42e6dd5207948`.
- Read-only `rpmkeys --checksig` using the existing trusted keyring reports `digests signatures OK`.
- The canonical job actually installed from the COPR repository in a clean Fedora container and independently queried installed version `35.0.0` at 10:54:20 UTC.
- COPR rebuilds the commit-bound SRPM, so its binary hash differs from the GitHub RPM.

## Wiki

[Wiki publication run 39586282209](https://github.com/loofiboss-bit/loofi-fedora-tweaks/actions/runs/39586282209)
succeeded. Independent public readback of Home, Installation and Changelog
confirmed v35, current installation links, the Fedora 44/x86_64 channel and
disclosed Qt limitations. Initial wiki publication commit:
`294d682813f091362d6bf1e2579e1d4801db4c56`.

## Qualification boundaries

Local source verification passed 5,674 tests with 85.38% maintained coverage;
the hosted Python 3.12 CI passed 5,671 tests with 36 skips. See
[qualification details](../V35_QUALIFICATION.md) for measured performance and layout checks.

The installed Qt accessibility defect remains a known dependency limitation.
An isolated corrected runtime passed its regression but is not shipped in this
RPM. Full final-RPM X11/Wayland/AT-SPI and offline-reboot matrices remain
unqualified. These are disclosed limitations under the maintainer's revised
release policy, rather than mandatory release gates. No host package was
installed or host configuration changed for publication verification.
