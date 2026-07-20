# v17 Phase 6 -- Local Release Readiness

Date: 2026-07-20
Status: local release gates passed; public readback pending

## Green gates

- `just verify`: 7,683 passed, 68 skipped, 851 subtests; 86.23% coverage;
  flake8 and mypy passed.
- Assurance definition matrix: 11 passed across Traditional, Atomic, Flatpak,
  firmware, cleanup, and recovery contracts.
- Mutation inventory, five canonical workflows, v16 UI compatibility,
  stabilization rules, Fedora Review availability, release docs, version
  consistency, adapter drift, and packaging manifest passed.
- CI Bandit profile: zero medium/high findings across 70,345 lines.
- `pip-audit --strict`: no known vulnerabilities.
- AppStream validation passed with the historical non-RDNS component ID
  downgraded to informational; no new v17 AppStream error was introduced.
- Version metadata is aligned at `17.0.0` / `Assurance` across Python,
  `pyproject.toml`, and the RPM spec.
- Local RPM, Flatpak, and sdist builds completed. The RPM identifies itself as
  `1:17.0.0-1.fc44`, and the source archive is rooted at
  `loofi_fedora_tweaks-17.0.0/`.

## Startup and resources

| Measurement | v16 baseline | v17 candidate | Gate | Result |
| --- | ---: | ---: | ---: | --- |
| Meaningful Home median | 181.011 ms | 160.268 ms | 217.213 ms | pass |
| RSS median | 77,970 KiB | 78,092 KiB | 89,665 KiB | pass |
| Runtime Home plugins | 1 | 1 | 1 | pass |
| Subprocess probes | 0 | 0 | 0 | pass |
| Active timers / QThreads | 0 / 0 | 0 / 0 | 0 / 0 | pass |

Raw evidence is in `V17_PHASE6_STARTUP.json`.

## Component decision

The current graph contains 114 core/specialist-shared modules, 50
specialist-exclusive modules, and 26/9/11 specialist-exclusive modules reachable
from CLI/API/daemon. `-extras` remains NO-GO. Raw evidence is in
`V17_COMPONENT_ANALYSIS.json`.

## Physical validation

- The Traditional matrix ran on a physical Fedora Linux 44 KDE host.
- A clean Fedora Kinoite 44.1.7 KVM guest was installed from the official ISO
  after verifying its SHA-256 and Fedora 44 primary-key signature. Layering
  `zsh` produced a staged deployment while the old deployment remained booted.
  A real reboot changed the boot ID and booted the exact planned deployment,
  with `zsh-5.9-20.fc44.x86_64` present. Full evidence is in
  `V17_PHASE6_ATOMIC_VM.md`.
- fwupd 2.1.6 completed the packaged ColorHug2 device-emulation fixture across
  signed firmware versions 2.0.6 and 2.0.7. This validates the automated
  machine-readable firmware path without claiming physical hardware coverage;
  see `V17_PHASE6_FWUPD_EMULATION.md`.

## Remaining publication gates

The release commit is locally ready. Exact GitHub tag lineage, canonical CI,
release assets and checksums, SBOM/provenance verification, COPR Fedora 44
install/readback, and public wiki readback must be completed after publication.
