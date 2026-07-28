# V22 Phase 5 — Local Qualification

Date: 2026-07-28  
Release: v22.0.0 "Alignment"  
Baseline commit: `3c9ce62a14839f40dd1ac027cc43a83476f27571`  
Candidate source identity: `WORKTREE` (no release commit is authorized)

## Result

The V22 implementation is locally qualified and the version metadata is
synchronized to v22.0.0. This is not publication evidence. The race lock stays
active until the separately authorized physical, install, exact-commit, and
public-readback gates are complete.

## Repository qualification

- `just verify`: passed.
  - 6,909 tests passed.
  - 61 tests skipped.
  - 1,079 subtests passed.
  - Global coverage: 86.65 percent.
  - Lint, mypy, architecture, and stabilization checks passed.
- `just validate-release`: passed.
- `just stats-check`: passed.
- `just check-drift`: passed.
- `just check-packaging`: passed.
- `just validate-system-check`: passed.
- `python3 scripts/bump_version.py --check`: passed.
- `git diff --check`: passed.
- Bandit: no medium or high findings.
- `pip-audit`: no known dependency vulnerabilities.

## Startup and resource budget

The final offscreen Home startup probe measured:

- median startup: 169.528 ms, below the 178.211 ms V22 ceiling;
- RSS: 76,828 KiB, below the 84,009 KiB V22 ceiling;
- one Home provider;
- no cold-start probes, timers, or `QThread` instances.

This is deterministic local evidence, not physical Wayland evidence.

## Candidate artifacts

The following v22.0.0 artifacts were built:

- `loofi-fedora-tweaks-22.0.0-1.fc44.noarch.rpm`
- `loofi-fedora-tweaks-api-22.0.0-1.fc44.noarch.rpm`
- `loofi-fedora-tweaks-daemon-22.0.0-1.fc44.noarch.rpm`
- `loofi_fedora_tweaks-22.0.0.tar.gz`
- `loofi-fedora-tweaks-v22.0.0.flatpak`

An isolated candidate directory was generated at
`/tmp/loofi-v22-candidate.yPlVdT`. It contains only these five artifacts plus
`SHA256SUMS.txt`, a CycloneDX SBOM, and an in-toto provenance statement.
`scripts/generate_release_evidence.py --verify` passed.

Artifact SHA-256:

| Artifact | SHA-256 |
| --- | --- |
| GUI RPM | `e7cf53fc026220c9b77d286426a8ad5f66ad44a8d1b41cbddd7efb8c5d5cd2fc` |
| API RPM | `a13f217aabd264b47aab59520699bfa6d6f6859910dfeeb885ff96dc77b82edf` |
| daemon RPM | `6c732ffe44e65c31484c9aa3ea47b2d31499c7d9e3f9a07cb9034268742c1254` |
| sdist | `228de33cd8d735bdb7bf10c16963439a8ad5f083a01870f854f2889b2a09310a` |
| Flatpak | `218c4ab5860e6f0607749251bf39cb6af0b980e295f92a50814ef11de585473d` |

RPM header and payload digests passed. The API RPM requires
`python3-python-multipart`; the daemon RPM requires `python3-gobject-base`.
The local RPMs are unsigned because signing and publication are not authorized.

The release workflow now creates GitHub artifact attestations for the exact
release asset set. A real attestation cannot exist until an authorized GitHub
workflow run has a committed source identity. The local provenance therefore
uses `WORKTREE` and must not be presented as exact-commit release provenance.

## Gates intentionally still open

- Physical Fedora 44 Traditional keyboard, Wayland, Orca, and AT-SPI journey.
- Physical Fedora 44 Kinoite/Atomic behavior and explicit host-layering journey.
- Clean RPM installation of GUI, API, and daemon on a disposable Fedora 44
  target, including `rpm -V`, CLI launch, loopback API, and daemon GLib loop.
- RPM signature verification.
- Exact committed source lineage and fresh artifact rebuild.
- Live GitHub artifact attestation verification.
- GitHub, COPR API/repository/clean-install, documentation, media, and
  installation-flow external readback.
- Fedora 45 promotion; it remains Preview.

No commit, push, tag, host installation, COPR action, or publication was
performed.
