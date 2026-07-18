# v16.0.0 "Clarity" Phase 8 Release Readiness

Date: 2026-07-18
Release: `v16.0.0 "Clarity"`
Status: released and publicly verified

## Outcome

Phase 8 completed the regression, performance, compatibility, packaging,
security, documentation, screenshot, and installed-package gates for Clarity.
The exact release tree is published on GitHub and COPR, and every public
readback gate passed.

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
- The historical `v16.0.0 "Horizon"` annotated tag object is preserved as
  `legacy-v16.0.0-horizon`; the canonical tag now identifies Clarity.

## Public release evidence

- Pull request `#34` merged as release commit
  `56007bf7e5c046f189d2e2284740320ca3e1ebad`.
- The annotated `v16.0.0` tag peels to that exact commit. The GitHub release is
  public, non-draft, non-prerelease, and titled `Loofi Fedora Tweaks v16.0.0 —
  Clarity`.
- Auto Release Pipeline run `29641341177`: all 17 jobs passed, including full
  tests, security, Flatpak, sdist, RPM, Fedora Review, RPM smoke, exact tag,
  release, and COPR publication.
- All eight public assets were downloaded. SHA-256 verification passed, and the
  CycloneDX SBOM plus in-toto/SLSA provenance match the artifact set, release
  commit, tag, repository, and workflow run.
- COPR build `10740581`, chroot `fedora-44-x86_64`: succeeded with package
  `1:16.0.0-1`. The workflow installed it from the public repository and
  verified application version `16.0.0`.
- Publish Wiki run `29641877579`: succeeded. Public wiki commit
  `e569292bbd1d083932b55d9c6f9eb0b1c750dca3` identifies Clarity as current,
  links the v16 release, and matches all 12 canonical screenshot files
  byte-for-byte.

Public asset SHA-256 digests:

| Artifact | SHA-256 |
| --- | --- |
| Base RPM | `3de0eb532d6e95706af938f991b7dfb4de670d3135677505525dac06a55b1703` |
| API RPM | `d2c0df45c6fc728923971e7b888ca97bb0f226f2319f81f28dd7f7f692aa558e` |
| Daemon RPM | `fba8ffad27fdc12b3a06d99456e73ed9ba45c486ba11bb583214b31943a35590` |
| Flatpak | `d1ec749cfe7b5eb3b36e64b5105f9b26a29ad6eff23a07c3286e0b78e69b1d28` |
| CycloneDX SBOM | `a87a3c4a6b760ef3ff49fcf4a6967f76de1e172977d5ce7bf9227048232a0af8` |
| in-toto provenance | `32c531f67374367b2651268d629536ad01f7340aa672d787c74d5a08d2ed21a2` |
| Source distribution | `b490cd3a32bc4b5566fbdbd9783bc45329f45e9f17e03d7a5ee61962cab6d0d8` |

No release blocker remains. GitHub, COPR, the Fedora 44 package path, and the
wiki are live and publicly verified.
