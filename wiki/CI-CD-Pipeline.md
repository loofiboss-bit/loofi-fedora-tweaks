# CI/CD Automation Pipeline — v33.0.1 "Concord"

The Loofi Fedora Tweaks repository uses GitHub Actions for continuous integration, security scanning, packaging validation, and automated release publication.

---

## 1. Automated Workflows

| Workflow | Trigger | Responsibilities |
| --- | --- | --- |
| **`ci.yml`** | Push & Pull Request | Code linting, typechecking (`mypy`), unit tests, coverage verification (85% threshold), docs validation, RPM/sdist build checks |
| **`auto-release.yml`** | Push to `master` / Tag / Manual dispatch | Automated quality validation, version consistency checks, RPM build, immutable git tag creation, GitHub Release publication, and COPR build handoff |
| **CodeQL Analysis** | PR & Weekly Schedule | Semantic static security analysis for Python and GitHub Actions workflows |
| **`publish-wiki.yml`** | Wiki Directory Push | Synchronizes documentation mirrors to the GitHub Wiki |

---

## 2. Release Gate Sequence

The `auto-release.yml` pipeline executes a deterministic sequence of gates before creating a release:

```text
Commit to master
   │
   ├─► 1. Documentation & Version Sync Gate (scripts/check_packaging_manifest.py)
   ├─► 2. Static Typing & Linting (mypy, flake8)
   ├─► 3. Test Suite & Coverage Gate (pytest, min 85% coverage)
   ├─► 4. Dedicated Fedora KDE VM E2E gate
   ├─► 5. Package Build & Metainfo Validation (RPM spec, AppStream)
   ├─► 6. Auto-Tagging (creates verified annotated git tag)
   ├─► 7. GitHub Release Creation (RPM, sdist, CycloneDX SBOM, in-toto attestation)
   └─► 8. Fedora COPR build, terminal success, and installed-version verification
```

---

## 3. Public Evidence Readback

Every public release records its verification evidence in `docs/reports/` (e.g. [V33.0.1_RELEASE_PUBLICATION.md](https://github.com/loofiboss-bit/loofi-fedora-tweaks/blob/master/docs/reports/V33.0.1_RELEASE_PUBLICATION.md)), documenting:
- Exact commit SHA and annotated tag object.
- Test pass count and coverage percentage.
- SHA-256 digests for all published assets (RPM, tarball, SBOM, and attestations).
- Fedora COPR build job ID and install verification.


## v33.0.1 explicit publication exception

`waive_v33_vm_e2e` defaults to false and applies only to a manual dispatch of
version 33.0.1. It records the maintainer-authorized exception for failed VM
runs 38178492268 and 38178492259. Every other build, review, evidence and
publication gate remains required. Release run 38183736156 completed with
this exception. Later releases use the normal VM gate.
