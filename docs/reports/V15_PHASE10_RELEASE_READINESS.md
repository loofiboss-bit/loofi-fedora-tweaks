# v15 Phase 10 Release Readiness

Date: 2026-07-18
Release: `v15.0.0 "Essentials"`
Status: local release gates passed; public publication pending

## Outcome

The v15 implementation is locally publish-ready. Documentation, metadata,
screenshots, package descriptions, and workflow specs describe the shipped
six-destination Standard experience, optional Advanced destination, logical
core/specialist isolation, and preserved v14 trust contracts.

The historical pre-renormalization `v15.0.0 "Nebula"` annotated tag object is
preserved on origin as `legacy-v15.0.0-nebula`. The conflicting canonical tag
was removed deliberately before the Essentials release commit is created.

## Compatibility preserved

- Action Center planning, confirmation, execution, verification, expiry,
  leases, history, interruption, CLI, and authenticated read-only API behavior.
- v14 settings, favorites, route aliases, state schemas, backup/restore,
  observability, and support-bundle contracts.
- Traditional and Atomic Fedora package/update behavior.
- Base, API, and daemon RPM subpackages with exact EVR dependencies.
- Existing CLI, API, daemon, and IPC entry contracts.

## Measurements

| Measure | v14 baseline | v15 median | Change |
| --- | ---: | ---: | ---: |
| Meaningful Home | 4552.202 ms | 151.924 ms | 96.66% faster |
| RSS | 107446 KiB | 76068 KiB | 29.20% lower |
| Imported modules | 527 | 288 | 45.35% lower |
| Imported `ui.*_tab` modules | 30 | 2 | 93.33% lower |
| Startup subprocess probes | 54 | 0 | eliminated |
| Active timers / QThreads | 9 / 2 | 0 / 0 | eliminated |

The Phase 6 workflow validator reported five canonical workflows, zero host
probes, and zero mutations.

## Verification

- `just release-prep`: passed.
- Full coverage suite: 7,622 passed, 40 skipped, 86.12% coverage.
- Workflow report suite: 7,622 passed, 40 skipped.
- Lint and mypy: passed.
- Release-doc, publish-ready task, stats, adapter-drift, requirement-sync, and
  packaging-manifest gates: passed.
- RPM: base, API, daemon, and SRPM built for Fedora 44.
- Flatpak: `loofi-fedora-tweaks-v15.0.0.flatpak` built successfully.
- sdist: `loofi_fedora_tweaks-15.0.0.tar.gz` built successfully.
- Fedora review contract and Phase 6 workflow validator: passed.
- Bandit CI profile: zero medium/high findings.
- Dependency audit: no known vulnerabilities. The local audit split the
  installed `dbus-python` 1.4.0 direct requirement from the fully resolved
  remaining requirements because the isolated resolver lacked local GLib
  development headers.
- Codex Security working-tree diff scan: 26/26 security-relevant files closed,
  zero plausible candidates.
- Installed Fedora package transaction dry-run: host `1:14.0.0-1.fc44` to the
  locally built `1:15.0.0-1.fc44` base/API/daemon set passed without mutation.
- Canonical real-app screenshots: regenerated and visually inspected.
- `git diff --check`: passed.

The RPM release gate uses `appstream-util validate-relax` and passed. The
stricter `appstreamcli validate` additionally reports the existing non-reverse-
DNS component-id warning and informational metadata suggestions. The desktop
validator reports the existing multiple-main-category hint. These do not block
the repository's established Fedora release gate.

## Publication gates

The following are intentionally performed only after the exact release commit
exists:

1. build and verify checksums, CycloneDX SBOM, and in-toto/SLSA provenance
   against that commit;
2. push the exact commit and create the canonical `v15.0.0` tag;
3. wait for terminal GitHub Actions and COPR results;
4. verify Fedora 44 install/upgrade evidence and public release assets;
5. publish and read back the wiki and final release announcement.

No physical extras RPM ships in v15. The evidence-backed Phase 9 NO-GO remains
deferred to v16; logical component isolation is the shipped boundary.
