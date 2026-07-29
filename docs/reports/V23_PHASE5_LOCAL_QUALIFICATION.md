# V23 Phase 5 — Local Qualification

Date: 2026-07-29  
Target: v23.0.0 "Compass"  
Product metadata: v22.0.0 "Alignment"  
Base commit: `f176b5b0c61769f06c197ce2e590090e70740de0`  
Candidate source identity: `WORKTREE` (no commit or release action is authorized)

## Result

The Phase 5 implementation and all available local qualification gates pass.
This is not a completed Phase 5 platform claim: fresh Fedora 44 Kinoite/Atomic
qualification and manual physical keyboard/Orca journey evidence remain open.
Product metadata therefore stays at v22.0.0 and the V23 race lock stays active.

## Repository qualification

- `just verify`: passed.
  - 7,000 tests passed.
  - 61 tests skipped.
  - 1,184 subtests passed.
  - Global coverage: 86.13 percent.
  - Lint, mypy, architecture, stabilization, route, compatibility, and
    release-document checks passed.
- `just validate-v23-phase5`: passed.
- `just validate-release`: passed.
- `just check-packaging`: passed.
- `just check-drift`: passed.
- `just stats-check`: passed.
- `just validate-product-contract`: passed.
- `just validate-architecture`: passed.
- `just validate-system-check`: passed.
- `git diff --check`: passed.
- Bandit scanned 89,889 lines with no medium or high findings.
- `pip-audit` checked 33 dependencies with no known vulnerabilities.
- CodeQL CLI 2.25.5 `python-security-extended.qls` resolved 52 queries and
  scanned 809 of 809 Python files plus 4 of 4 GitHub Actions files from the
  current worktree.
  - Two initially reported permissive per-user file modes were fixed to `0600`
    and `0700`.
  - The final scan emitted four raw alerts. CodeQL's own
    `AlertSuppression.ql` matched all four at their exact sink locations: two
    intentional one-time CLI credential responses and two path expressions
    already constrained by basename and common-path validation.
  - Effective high or critical findings: zero.
  - [`V23_PHASE5_CODEQL.json`](V23_PHASE5_CODEQL.json) binds the result to a
    SHA-256 digest of every scanned Python and Actions input. The Phase 5
    validator recomputes that digest from the current worktree.

The qualification adds direct regression coverage for all six closed profile
budgets, Traditional/Atomic variants, malformed and oversized values, nested
command vectors, callbacks, renderers, credentials, tokens, raw output, and
redaction boundaries.

## Startup and resource budget

The machine-readable
[`V23_PHASE5_STARTUP.json`](V23_PHASE5_STARTUP.json) contains 3 warmups and 15
measured offscreen runs. `scripts/validate_v23_phase5.py` verifies the evidence
against the Phase 0 baseline and the Phase 0 × 1.10 ceilings:

| Metric | Phase 0 | Phase 5 | Ceiling | Result |
| --- | ---: | ---: | ---: | --- |
| Meaningful Home median | 172.562 ms | 154.254 ms | 189.818 ms | PASS |
| RSS median | 76,472 KiB | 76,236 KiB | 84,119 KiB | PASS |

Every measured run realized exactly one `atlas_dashboard` Home provider with
zero cold-start subprocess probes, active timers, running QThreads, or eager
System Check imports. This is deterministic local performance evidence, not
physical platform evidence.

## Physical Traditional evidence

The current host is Fedora Linux 44 KDE Plasma Desktop Edition, using a real
Wayland session and the Traditional `dnf5` package model. A live AT-SPI2
inspection of the real `MainWindow` passed for the `diagnostics` route and
found the application, navigation, Troubleshoot page, problem-profile label,
explicit start control, result state, and confirmation dialog. Orca was
available. The summary-only evidence is recorded in
[`V23_PHASE5_ATSPI.json`](V23_PHASE5_ATSPI.json); raw accessibility-tree nodes
are intentionally not retained.

This proves live Wayland/AT-SPI exposure on the current Traditional host. It
does not prove a manual keyboard journey or audible Orca speech output.

All six closed profiles were also collected afresh through the real versioned
CLI on this physical host, using isolated temporary XDG state and no mutating
action. Every run retained `traditional` identity, the exact variant-specific
source projection, its locked total budget, and a truthful `completed` or
`partial` terminal state. Only bounded summary records are retained in
[`V23_PHASE5_TRADITIONAL_PROFILES.json`](V23_PHASE5_TRADITIONAL_PROFILES.json);
raw CLI payloads are not retained.

## Profile budgets

The validator locks the exact profile total budgets for both Fedora variants:

| Profile | Traditional | Atomic |
| --- | ---: | ---: |
| `system_slow` | 62 s | 62 s |
| `updates_failed` | 65 s | 65 s |
| `application_failed` | 35 s | 35 s |
| `network_problem` | 25 s | 25 s |
| `storage_pressure` | 85 s | 85 s |
| `boot_or_deployment` | 75 s | 75 s |

`application_failed` remains reduced because no safe application-journal
collector exists. `network_problem` remains reduced because scanning is
excluded. Tests enforce every source budget, exact total, variant separation,
bounded cancellation, and rejection of command-bearing or unbounded inputs.

## Package and local candidate evidence

Phase 5 deliberately keeps the v22.0.0 product metadata required by the V23
architecture contract. The following worktree artifacts were built and
inspected without installation:

- base, API, and daemon RPMs;
- source distribution;
- Flatpak bundle imported into an empty temporary repository;
- SHA-256 checksums, CycloneDX SBOM, and in-toto provenance.

All three RPMs report `1:22.0.0-1.fc44`, pass payload digest verification, and
contain their expected Compass troubleshooting code or service files. They are
unsigned because signing is outside Phase 5 authority.
The source distribution also built a wheel and installed successfully, without
dependency resolution or network access, in the isolated environment
`/tmp/loofi-v23-phase5-source-env.7wiAhM`; installed distribution metadata
reports `22.0.0`. The Flatpak bundle imported successfully into an empty
temporary OSTree repository.
`scripts/generate_release_evidence.py --verify` passed in the isolated
candidate directory `/tmp/loofi-v23-phase5-candidate.RQqjf3`.

| Artifact | SHA-256 |
| --- | --- |
| GUI RPM | `d6a323385c588f8d283838fd073dc39e6629bd26f77543677d5f92f586f42f0d` |
| API RPM | `e68033f05598f290d5959c6e21273bd69d06516b4edcb1b22ab8a2dd7c2dd878` |
| daemon RPM | `2ef72625e5a8737d4242bcb1d071b0febde5e72f78ccee9c8b7993331949b2bf` |
| Flatpak | `dc071647d72f7d28487a2486eee18a670a8b3a6cfe36483776dab6d5d4b2f811` |
| source distribution | `2265f63b30f051f4247efb7e249daf0bb7bf0b1a3256a3e9cd0ec77d8beab1ac` |
| CycloneDX SBOM | `a8821ed936f31d3bed808d8a94870cc3bc1695ba7abbde08f737519f7635dc3b` |
| in-toto provenance | `80557fa76fdda2f5daee72cd2d3447095e404de701ade2b859278c2b6a82746d` |

These hashes identify local worktree artifacts only. They are not release
assets or exact-commit provenance.

## Qualification fixes

- Added a dedicated Phase 5 validator for startup, resource, provider, probe,
  thread, and six-profile budget contracts.
- Added malicious-input and exact-budget regression coverage.
- Exposed the problem-profile control through a visible label/buddy pair after
  live AT-SPI inspection found that the combo-box name was not exported.
- Made AT-SPI evidence summary-only while still validating the live tree.
- Made the Phase 4 API route contract follow mounted FastAPI router wrappers.
- Prevented the auto-release pipeline gate from running after validation has
  explicitly determined that a normal post-release push is not a release.
- Corrected the real CLI session projection to expose the stable persistence
  reason instead of reading a removed model attribute.
- Renamed an internal application-inventory fact so the deny-by-default
  command-key validator does not reject safe availability evidence.
- Tightened generated per-user file modes for sandbox desktop entries and
  dotfiles installers after exact-worktree CodeQL review.
- Replaced two repository-script `exec()` version readers with strict
  `ast.literal_eval` assignment parsing and regression tests proving that
  expressions are rejected without execution.

## Gates intentionally still open

- Fresh physical Fedora 44 Kinoite/Atomic qualification for all variant-aware
  profiles and Atomic package, boot, deployment, and recovery guidance.
- Manual keyboard-only traversal and audible Orca journey on the physical
  Traditional and Atomic targets.
- Exact committed source lineage.
- RPM signatures, installation/upgrade lifecycle, GitHub, COPR, wiki, and
  public documentation readback.
- Resolution of the occupied historical `v23.0.0` tag under separate Phase 6
  release authority.

No commit, push, tag, host installation, remote workflow modification, COPR
action, or publication was performed.
