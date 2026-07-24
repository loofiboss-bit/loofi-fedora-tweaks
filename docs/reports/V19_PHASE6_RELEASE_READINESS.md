# v19 Phase 6 Release Readiness

Date: 2026-07-25  
Result: local release candidate ready; exact-commit and publication gates pending

## Verified source state

The v19.0.0 "Steward" worktree passed the complete local verification surface:

- `just release-prep`
- `just build-rpm`
- `just build-flatpak`
- `just build-sdist`
- the CI-equivalent Bandit policy
- `pip-audit --strict --progress-spinner off -r requirements.txt`

The full suite reported 6,882 passed tests, 68 skipped tests, 1,032 passed
subtests, no failures, and 86.26 percent coverage. Release documentation,
packaging manifests, synchronized metadata, agent adapters, the System Check
trust contract, and v19 UI evidence all passed their validators.

Bandit reported zero qualifying findings and zero scan errors. The dependency
audit reported no known vulnerabilities.

## Local artifact identities

The final local builds identify as v19.0.0:

| Artifact | Identity or imported ref | SHA-256 |
| --- | --- | --- |
| `loofi-fedora-tweaks-19.0.0-1.fc44.noarch.rpm` | `loofi-fedora-tweaks 19.0.0-1.fc44 noarch` | `6648518aaf92fd678aa85dd46004387e01128fd6fa7bec9a4dc7212c6e428f8b` |
| `loofi-fedora-tweaks-api-19.0.0-1.fc44.noarch.rpm` | `loofi-fedora-tweaks-api 19.0.0-1.fc44 noarch` | `662a754bdf4c7f4657bbaa510d243e57a83ad81c74b4dcb2d432a01704ff89e0` |
| `loofi-fedora-tweaks-daemon-19.0.0-1.fc44.noarch.rpm` | `loofi-fedora-tweaks-daemon 19.0.0-1.fc44 noarch` | `bd845bb6e4e1dd9dce0e43d01c85d87fd1e1be74bc5daf5543a9156e149a16a4` |
| `loofi-fedora-tweaks-v19.0.0.flatpak` | `app/org.loofi.FedoraTweaks/x86_64/master` | `10c31337aeeb8eca1c38d0a3b70a187f3ce0f126859eeaab99f2ad8ac35b8411` |
| `loofi_fedora_tweaks-19.0.0.tar.gz` | embedded `19.0.0` / `Steward` metadata | `0824d1a9d219d53fa3a0881325e39f35a297979d06de4e19923911dae1ec3527` |

The Flatpak bundle was imported into a new isolated OSTree repository and its
application ref was read back. The source distribution's embedded
`version.py` was read back directly from the archive. RPM identities were read
with `rpm -qp`.

These are local candidate hashes only. They are not public release checksums
and must not be reused after any source or release-artifact change.

## Platform and product evidence

Traditional Fedora shell, accessibility, startup, System Check duration, and
state evidence are recorded in the machine-readable `V19_PHASE6_*.json`
reports. Fresh Fedora Kinoite installation, rpm-ostree deployment, real
reboots, the discovered Atomic correction, replacement deployment, and exact
installed-source readback are recorded in
`V19_PHASE6_PLATFORM_CERTIFICATION.md`.

The release candidate preserves:

- the v18 cold-start ceilings and idle-host contract;
- stable routes, aliases, CLI compatibility, and readable persisted schemas;
- distinct Traditional and Atomic package-health behavior;
- the v18 Action Center preflight, confirmation, execution, and verification
  trust boundary.

## Deliberately pending gates

No release commit, tag, publication, or remote mutation was authorized. The
following gates therefore remain pending:

- create and verify intentional commits for the final code fix and release
  metadata;
- rebuild from and compare against the exact clean release commit;
- generate and verify final checksums, CycloneDX SBOM, and in-toto provenance
  tied to that exact commit and artifact set;
- read back canonical CI and CodeQL;
- tag and publish GitHub assets;
- complete COPR, clean public installation, and public documentation readback;
- close the roadmap and race lock only after public verification.

The local candidate must be rerun through the exact-commit artifact gates if
commit authorization is later granted.
