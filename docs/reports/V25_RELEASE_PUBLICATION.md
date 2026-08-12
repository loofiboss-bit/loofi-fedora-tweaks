# v25.0.4 “Proof” Public Release Evidence

Status: release evidence record for the canonical v25.0.4 workflow.

The historical `v25.0.0`–`v25.0.3` tags remain unchanged. Proof uses the first
unused v25 patch identity, `v25.0.4`, so the release tag can be bound to the
exact release commit without rewriting historical lineage.

## Release identity

| Field | Evidence |
| --- | --- |
| Repository | `loofiboss-bit/loofi-fedora-tweaks` |
| Release tag | `v25.0.4` |
| Release commit | recorded after the release commit is created |
| Tag peel | recorded after the tag-triggered workflow starts |
| GitHub release | recorded after public release readback |
| Canonical workflow run | recorded after completion |

## Public surfaces

| Surface | Status | Evidence |
| --- | --- | --- |
| GitHub Actions and CodeQL | pending | tag-triggered workflow readback |
| GitHub release and assets | pending | release API and asset checksum readback |
| SBOM, provenance, attestations | pending | published release assets and attestation readback |
| COPR Fedora 44 build | pending | terminal build, repodata, signature, and package readback |
| Wiki | pending | public wiki commit/page readback |

## Physical and manual boundaries

Fedora KDE Wayland, fresh Atomic/Kinoite, Polkit prompts, reboot completion,
keyboard/screen-reader journeys, and manual recovery are not proved by the
release workflow. They remain explicitly `unverified` unless separately
qualified by an authorized human.
