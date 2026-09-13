# v26.0.3 “Everyday” Public Release Evidence

Status: complete. The v26.0.3 public release, automated qualification, package
publication, and documentation readback passed. Physical and manual gates are
reported separately and remain explicitly `unverified`.

## Release identity

| Field | Evidence |
| --- | --- |
| Repository | `loofiboss-bit/loofi-fedora-tweaks` |
| Release tag | [`v26.0.3`](https://github.com/loofiboss-bit/loofi-fedora-tweaks/releases/tag/v26.0.3) |
| Release commit | `53ad83487fa5bd972c2832178920bb001b8a989f` |
| Tag object | `49b58aa046333aa1a7210b5d63d369c08f9d3b35` |
| Peeled tag commit | `53ad83487fa5bd972c2832178920bb001b8a989f` |
| Canonical workflow | [run 34754130936](https://github.com/loofiboss-bit/loofi-fedora-tweaks/actions/runs/34754130936), `success` |
| CI workflow | [run 34754130958](https://github.com/loofiboss-bit/loofi-fedora-tweaks/actions/runs/34754130958), `success` |
| CodeQL workflow | [run 34754130799](https://github.com/loofiboss-bit/loofi-fedora-tweaks/actions/runs/34754130799), `success` |
| GitHub release | [v26.0.3 “Everyday”](https://github.com/loofiboss-bit/loofi-fedora-tweaks/releases/tag/v26.0.3), published, non-draft, non-prerelease |

The tag readback used `git ls-remote --tags` and proved that the annotated tag
peels to the exact release commit `53ad83487fa5bd972c2832178920bb001b8a989f`.

## Public surfaces

| Surface | Status | Evidence |
| --- | --- | --- |
| GitHub Actions and CodeQL | passed | Canonical run `34754130936`, CI run `34754130958`, and CodeQL run `34754130799` all completed successfully for the exact release commit. |
| GitHub release and assets | passed | The public release contains eight uploaded assets: three RPMs, Flatpak, source archive, `SHA256SUMS.txt`, CycloneDX SBOM, and in-toto provenance. |
| Checksums | passed | Fresh `gh release download v26.0.3` readback passed `sha256sum -c SHA256SUMS.txt` for all seven listed payload assets; the manifest hash is `sha256:d6aa95d3ca320881bff95c5c912e1d7c4a6dbfee801c9a64a3f43321d5536754`. |
| SBOM, provenance, attestations | passed | The canonical workflow recorded eight verified attestations. |
| COPR Fedora 44 build | passed | [Build 10981363](https://copr.fedorainfracloud.org/coprs/loofitheboss/loofi-fedora-tweaks/build/10981363/) reached terminal `succeeded` for `fedora-44-x86_64`; public repodata and RPM signatures were read back. |
| Wiki | passed | [Wiki publish run 34754130937](https://github.com/loofiboss-bit/loofi-fedora-tweaks/actions/runs/34754130937) succeeded; public wiki commit `6ba5d98f69b683201e6c86526dccd44cdd5d1fc5`. |

### GitHub asset hashes

The public release asset server reported these SHA-256 digests:

| Asset | SHA-256 |
| --- | --- |
| `loofi-fedora-tweaks-26.0.3-1.fc44.noarch.rpm` | `c438f4fe1d75c5aa093d427a26ff81f55398864cf953282ec34009177d930905` |
| `loofi-fedora-tweaks-api-26.0.3-1.fc44.noarch.rpm` | `950e8897f55ad22b81370faa822ec66c0719e62d32ac98788fa8212e1c7dbec0` |
| `loofi-fedora-tweaks-daemon-26.0.3-1.fc44.noarch.rpm` | `3ff1a89db7c05a389c0c3f5f59437c1be0e2b5f74c31757af576ca91409e5252` |
| `loofi-fedora-tweaks-v26.0.3.flatpak` | `f9c04954a372c7d5b515013013482c187cc4aaf309b9ed96391988976f7a61b1` |
| `loofi-fedora-tweaks.cdx.json` | `418655f65d7beaecdb45cc1b18688f56fd0ba56006d77433512712e89d0d25a9` |
| `loofi-fedora-tweaks.intoto.jsonl` | `e275a733491fa9dee3ae59e8414c1c7487264ac69f0fb3f833f4bab551c3a480` |
| `loofi_fedora_tweaks-26.0.3.tar.gz` | `140eea24954b37b360320e81fc45983b6ea5e14a99f7f7f0368c69b520c6ffcb` |

## COPR and package readback

- Build: `10981363`, terminal state `succeeded`.
- Target chroot: `fedora-44-x86_64`.
- Version EVR: `1:26.0.3-1.fc44`.
- Source RPM: `loofi-fedora-tweaks-26.0.3-1.fc44.src.rpm`.
- COPR Repository: `https://download.copr.fedorainfracloud.org/results/loofitheboss/loofi-fedora-tweaks`.
