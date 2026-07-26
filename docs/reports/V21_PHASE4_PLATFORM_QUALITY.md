# V21 Phase 4 Platform and Quality Gates

Date: 2026-07-26  
Baseline commit: `841218ef4dbfa6368136bd3d8cbc1c394ec81258`  
Qualified checkout: `c5df4ef70d058302c50a0ffd10a458c0e27be144` plus this
uncommitted Phase 4 evidence  
Product version: `20.0.0 "Continuity"`  
Active target: `21.0.0 "Resolve"`

## Outcome

Phase 4 passes the complete local Resolve implementation gate. The current
shell, runtime lifecycle, startup/resource contract, Fedora 44 policy matrix,
package formats, security checks, compatibility validators, and full
repository verification are green.

This is local qualification evidence, not a v21 release candidate or public
release. Product version remains `20.0.0 "Continuity"`. Version
synchronization, exact-commit candidate generation, legacy-tag preservation,
checksums for a final candidate, SBOM, provenance, commit, push, tag,
publication, and public readback remain release-only work.

## Runtime lifecycle and compatibility

- The focused lifecycle, EventBus, AgentScheduler, GUI entry, real
  `MainWindow` geometry, plugin lifecycle, navigation compatibility, and
  Fedora workflow suite passed with `99 passed`.
- All seven real `MainWindow` geometry tests execute under Qt offscreen with
  no lifecycle skip.
- The final full suite passed with `6,861 passed`, `61 skipped`, `1,057` passed
  subtests, and `86.54%` coverage against the `86%` gate.
- Lint, mypy, architecture, product/release documentation, generated project
  statistics, adapter drift, packaging manifest, System Check contract, and
  saved System Check state validation all pass.
- All 81 stable routes, current aliases, lazy loading, Action Center schema v4,
  System Check, journal, CLI/API/daemon, and future-schema read-only contracts
  remain covered by the full compatibility suite.

The full run retains visible non-failing environment and compatibility
warnings, including PyGObject/import deprecations, a mocked clipboard-server
thread warning, legacy SQLite resource warnings, and a duplicate archive-entry
fixture. No warning represents an application-owned EventBus, scheduler,
QThread, timer, or plugin-worker resource left by the current shell.

## Startup and resource evidence

The committed [startup evidence](V21_PHASE4_STARTUP.json) uses a temporary clean
profile, Qt offscreen, two warmups, and seven measured runs:

- meaningful Home median: `155.296 ms`, below the `250.094 ms` ceiling;
- RSS median: `76,076 KiB`, below the `83,582 KiB` ceiling;
- one realized runtime plugin in every run: `atlas_dashboard`;
- zero subprocess probes, active timers, running QThreads, and System Check
  runtime imports in every run.

Compared with the Phase 0 medians, meaningful Home is 31.7 percent faster and
RSS is 0.1 percent higher. Both measurements satisfy the Phase 0 × 1.10
contract.

## Fedora 44 certification boundary

### Traditional

The current host is Fedora Linux 44 KDE Plasma Desktop Edition, kernel
`7.1.4-204.fc44.x86_64`, Plasma `6.7.3`, Qt `6.11.1`, and Wayland. Direct
readback reports:

- `SystemManager.is_atomic() == False`;
- package manager `dnf`;
- the Fedora 44 readiness profile is supported, stable, and `ready`;
- readiness score `82/100`, with zero errors and two host-local warnings for
  display-manager detection and third-party repository review.

The host has the published v19 base/API/daemon RPMs installed. Phase 4 does not
replace that installation with an uncommitted v20 payload. The newly built
local v20 RPM is instead read back from an isolated extracted root.

### Atomic

The last physical Atomic installation evidence remains the Fedora Kinoite
44.1.7 KVM certification in
[V19 Phase 6 Platform Certification](V19_PHASE6_PLATFORM_CERTIFICATION.md).
That evidence includes an official-image signature check, a real
`rpm-ostree install`, staged deployment, reboot, exact booted checksum,
replacement transaction, installed-source readback, and an Atomic System Check
with no source errors.

Resolve changes presentation and application-owned lifecycle coordination; it
does not change package execution policy, rpm-ostree command construction,
deployment verification, or reboot authority. The current Atomic/Traditional
requalification passed `170 tests`, covering variant policy, Action Center
preflight/apply/verify, exact deployment and application operations, navigation
visibility, package services, System Check, Fedora 44 support, and Fedora 45
preview-only behavior. No fresh Kinoite guest install or reboot was performed
for Phase 4, so the result is explicitly carried-forward physical evidence
plus current contract requalification.

Fedora 44 remains the supported Traditional and Atomic target. Fedora 45
remains preview/read-only.

## Local package and security evidence

All builds use the unchanged `20.0.0 "Continuity"` product metadata:

| Artifact | Readback | SHA-256 |
| --- | --- | --- |
| Base RPM | `loofi-fedora-tweaks 1:20.0.0-1.fc44 noarch`; isolated payload reports `20.0.0` | `e99bf12eb112082a1a6f2be834f16f714536295fd3d1518277e8722f8f6852ae` |
| API RPM | `loofi-fedora-tweaks-api 1:20.0.0-1.fc44 noarch` | `7c54df0b0317d49c105c4a3fbb94e5764cd9f6240821567348ae9088072c334c` |
| Daemon RPM | `loofi-fedora-tweaks-daemon 1:20.0.0-1.fc44 noarch` | `4871e42855e8a1f837c2141c370514923c97a87f6750ee936dfae55dd76f8a46` |
| sdist | embedded `20.0.0` / `Continuity` metadata | `5823f077f4096baa3add90d2b171fbcbe13a842f1467acaa40f230845ec3280e` |
| Flatpak | imported as `app/org.loofi.FedoraTweaks/x86_64/master` | `055863deb3631826b3c4a4cd3fa389a9b495419bae25ca2937a2c9f2efe1efda` |

The RPM `%check` import and AppStream validation pass. The base RPM contains no
`__pycache__`, `.pyc`, or `.pyo` payload. The Flatpak bundle imports into an
empty archive-z2 OSTree repository at commit
`de8b8d2504c39b1a9ff37cd1af3c19f74e52e3d146c541ca08496fd46f66306d`
and its application ref reads back successfully.

The CI-equivalent Bandit policy reports zero medium/high findings and zero scan
errors across 70,992 lines of code. `pip-audit --strict` reports no known
vulnerabilities in `requirements.txt`.

These hashes identify local implementation-phase artifacts only. They are not
final release checksums and must not be reused after any source, metadata, or
commit change.

## Gate conclusion

Phase 4 is complete and the implementation is locally qualified to enter the
separately authorized release-readiness phase. The race lock remains active at
`phase-4`; no release-only task has started.
