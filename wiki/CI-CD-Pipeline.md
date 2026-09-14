# CI/CD Automation Pipeline — v28.0.2 "Ease"

The Loofi Fedora Tweaks repository uses GitHub Actions for continuous integration, security scanning, packaging validation, and automated release publication.

---

## 1. Automated Workflows

| Workflow | Trigger | Responsibilities |
| --- | --- | --- |
| **`ci.yml`** | Push & Pull Request | Code linting, typechecking (`mypy`), unit tests, coverage verification (85% threshold), docs validation, RPM/sdist build checks |
| **`auto-release.yml`** | Push to `master` / Tag | Automated quality validation, version consistency checks, RPM build, immutable git tag creation, GitHub Release publication, and COPR build handoff |
| **CodeQL Analysis** | PR & Weekly Schedule | Semantic static security analysis for Python and GitHub Actions workflows |
| **`publish-wiki.yml`** | Wiki Directory Push | Synchronizes documentation mirrors to the GitHub Wiki |

---

## 2. Release Gate Sequence

The `auto-release.yml` pipeline executes a deterministic sequence of gates before creating a release:

```text
Commit to master
   │
   ├─► 1. Documentation & Version Sync Gate (scripts/check_release_docs.py)
   ├─► 2. Static Typing & Linting (mypy, flake8)
   ├─► 3. Test Suite & Coverage Gate (pytest, min 85% coverage)
   ├─► 4. Package Build & Metainfo Validation (RPM spec, AppStream)
   ├─► 5. Auto-Tagging (creates verified annotated git tag)
   ├─► 6. GitHub Release Creation (RPM, sdist, CycloneDX SBOM, in-toto attestation)
   └─► 7. Fedora COPR Build Dispatch (automated RPM package build)
```

---

## 3. Public Evidence Readback

Every public release records its verification evidence in `docs/reports/` (e.g. [V28.0.2_RELEASE_PUBLICATION.md](https://github.com/loofiboss-bit/loofi-fedora-tweaks/blob/master/docs/reports/V28.0.2_RELEASE_PUBLICATION.md)), documenting:
- Exact commit SHA and annotated tag object.
- Test pass count and coverage percentage.
- SHA-256 digests for all published assets (RPM, tarball, SBOM, and attestations).
- Fedora COPR build job ID and install verification.

