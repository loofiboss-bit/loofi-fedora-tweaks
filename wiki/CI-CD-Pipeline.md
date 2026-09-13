# CI/CD Pipeline — v27.0.1 "Core"

The repository uses GitHub Actions for automated validation and the canonical
tag-triggered release. Public release claims must be read back from GitHub,
the package service, and the wiki after the workflow completes.

## Pipelines

| Workflow | Trigger | Scope |
| --- | --- | --- |
| `.github/workflows/ci.yml` | push and pull request | lint, typecheck, tests, security, docs, RPM/sdist packaging |
| `.github/workflows/auto-release.yml` | master push, `v*` tag, or dispatch | validation, gates, RPM/sdist build, exact tag, GitHub release, COPR handoff |
| GitHub CodeQL default setup | pull request and weekly schedule | Python and GitHub Actions security analysis |
| `.github/workflows/publish-wiki.yml` | wiki changes | wiki publication |

## Blocking quality contract

The maintained V27 surface uses an 85% coverage threshold. v27.0.1 measured
86.94% locally with 4,780 tests passed and 73 skipped. The full suite still
runs compatibility modules; the repository-wide 90% target is deferred to the
next release.

The release docs gate checks version synchronization, changelog, release
notes, workflow specs, race lock, active links, CLI examples, README banner,
AppStream metadata, and wiki mirrors. Packaging checks build the single RPM
and source distribution; the removed Flatpak application bundle is not a CI
artifact.

## Release flow

```text
master push
  → validate and docs/spec gates
  → lint, type, test, security, packaging
  → build RPM and sdist
  → auto_tag creates vX.Y.Z on the exact master commit
  → release publishes assets, checksums, SBOM, provenance, and attestations
  → COPR build and public documentation are read back independently
```

The auto-tag job fails closed if a version tag already points at a different
commit. Historical tags are never moved; v27.0.1 is used because v27.0.0 is a
preserved Marketplace Enhancement tag.

CodeQL is configured on the repository security surface for the languages that
exist in V27 (`python` and `actions`). JavaScript/TypeScript scanning is not
enabled because the product contains no JavaScript/TypeScript source.

## Evidence boundary

CI/offscreen evidence does not prove physical desktop accessibility, a real
Polkit agent, reboot completion, fresh Atomic installation, or manual
keyboard/Orca journeys. Those gates are intentionally unverified for
v27.0.1 under the authorized release decision.
