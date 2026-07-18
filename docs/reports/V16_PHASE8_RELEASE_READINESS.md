# v16.0.0 "Clarity" Phase 8 Release Readiness

Date: 2026-07-18
Release: `v16.0.0 "Clarity"`
Status: locally publish-ready; public readback pending

## Outcome

Phase 8 completes the regression, performance, compatibility, packaging,
security, documentation, screenshot, and installed-package gates for Clarity.
The product version is synchronized at 16.0.0 and the release tree is ready for
the exact-commit GitHub/COPR publication workflow.

## Regression and compatibility

- `just verify`: passed with lint and mypy clean.
- Full coverage suite: 7,722 passed, 40 skipped, 851 subtests; 86.48% coverage
  against the enforced 85% gate.
- Versioned workflow report suite: 7,722 passed and 40 skipped.
- Five canonical workflows: passed with zero host probes and zero mutations.
- Complete Action Center, Traditional/Atomic, route/state migration, CLI, API,
  daemon, D-Bus, IPC, and plugin compatibility suites: passed as part of the
  full regression run.
- Phase 7 real-shell contract: 400 automated cells and 24 release-catalog cells
  passed; the signed Wayland, Qt `xcb`, keyboard, contrast, and AT-SPI evidence
  remains valid for the unchanged product code.

## Startup and resources

The release reran `scripts/benchmark_startup.py` on the same Fedora KDE host and
method used for v15. Raw evidence is in `V16_PHASE8_STARTUP.json`.

| Measurement | v15 | v16 | Result |
| --- | ---: | ---: | --- |
| Meaningful Home median | 151.924 ms | 181.011 ms | passed the 182.309 ms relative and 225 ms absolute limits |
| RSS median | 76068 KiB | 77970 KiB | passed; 2.50% increase, below 15% |
| Runtime plugin instances | 1 | 1 | passed |
| Startup subprocess probes | 0 | 0 | passed |
| Active timers / QThreads | 0 / 0 | 0 / 0 | passed |

## Security and dependencies

- Bandit CI profile: zero medium/high findings across 69,999 lines.
- `pip-audit -r requirements.txt`: no known vulnerabilities.
- Stabilization rules and Fedora review contract checks: passed.
- Command, privilege, timeout, archive, Action Center, API, and plugin security
  regression suites: passed in the full test run.

## Packaging and installed runtime

- Packaging manifest and requirement synchronization: passed.
- Base, API, daemon, and source RPMs built for Fedora 44.
- Host upgrade from installed `1:15.0.0-1.fc44` to the local
  `1:16.0.0-1.fc44` base RPM: passed on the real Fedora KDE workstation.
- Installed RPM `--version`, CLI `--version`, and offscreen GUI startup: passed.
- Clean Fedora 44 container installation of base, API, and daemon RPMs plus CLI
  smoke: passed.
- `loofi-fedora-tweaks-v16.0.0.flatpak` built, installed into an isolated user
  root, imported PyQt6, reported 16.0.0, and passed offscreen GUI startup.
- `loofi_fedora_tweaks-16.0.0.tar.gz` built successfully.
- RPM AppStream validation passed. A full Fedora Review run completed with zero
  rpmlint errors; its upstream-source checksum warning is expected until the
  historical `v16.0.0` tag is preserved and replaced by the Clarity tag.
- The existing non-blocking setuptools license deprecation notices remain
  informational for the future 2027 deadline.

## Release surfaces

- README, user guides, architecture, changelog, AppStream, release notes,
  announcement, workflow specs, and version metadata describe Clarity.
- Canonical user-guide screenshots were regenerated from the exact 16.0.0 tree
  and visually inspected after capture.
- The historical `v16.0.0 "Horizon"` tag must be preserved as
  `legacy-v16.0.0-horizon` before the canonical tag is assigned to Clarity.

## Publication closure

The GitHub release, release assets, checksums, CycloneDX SBOM, in-toto/SLSA
provenance, terminal Actions state, COPR build, public Fedora 44 package install,
wiki readback, and roadmap/race-lock closure are recorded here after publication.
