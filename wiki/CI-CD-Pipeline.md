# CI/CD Automation Pipeline — v36.2.0 "Blueprint"

The Loofi Fedora Tweaks repository uses GitHub Actions for continuous integration, security scanning, packaging validation, and automated release publication.

---

## 1. Automated Workflows

| Workflow | Trigger | Responsibilities |
| --- | --- | --- |
| **`ci.yml`** | Push & Pull Request | Code linting, typechecking (`mypy`), unit tests, coverage verification (85% threshold), docs validation, dependency audit, RPM/sdist build checks |
| **`auto-release.yml`** | Push to `master` / Tag / Manual dispatch | Automated quality validation, version consistency checks, RPM build, Fedora review & installed smoke check, immutable git tag creation, GitHub Release publication with OIDC attestation, and COPR build handoff |
| **CodeQL Analysis** | PR & Weekly Schedule | Semantic static security analysis for Python, C/C++, and GitHub Actions workflows |
| **`publish-wiki.yml`** | Wiki Directory Push | Synchronizes documentation mirrors to the GitHub Wiki |

---

## 2. Release Gate Sequence

The `auto-release.yml` pipeline runs entirely on GitHub-hosted runners (the former self-hosted VM job is retired) and executes a deterministic sequence of gates before creating a release:

```text
Commit to master / v* tag
   │
   ├─► 1. Documentation, Version & Manifest Gate (scripts/check_packaging_manifest.py)
   ├─► 2. Static Typing, Architecture & Linting (mypy, validate_architecture.py, flake8)
   ├─► 3. Test Suite & Coverage Gate (pytest, min 85% coverage)
   ├─► 4. Package Build, Fedora Review & Installed RPM Smoke Test (fedora-review mock, RPM/sdist)
   ├─► 5. Auto-Tagging (verified annotated git tag)
   ├─► 6. GitHub Release Creation (RPM, sdist, CycloneDX SBOM, in-toto provenance, GitHub attestation)
   └─► 7. Fedora COPR build (`fedora-44-x86_64`, `fedora-45-x86_64`) and installed-version verification
```

---

## 3. Public Evidence Readback

Every public release records its verification evidence in `docs/reports/` (see [V36.2.0_RELEASE_PUBLICATION.md](https://github.com/loofiboss-bit/loofi-fedora-tweaks/blob/master/docs/reports/V36.2.0_RELEASE_PUBLICATION.md)), documenting:
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
