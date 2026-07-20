# Release Notes -- v17.0.0 "Assurance"

**Status:** released and independently verified
**Codename:** Assurance
**Supported target:** Fedora KDE 44

## Summary

Assurance converts the five canonical mutation workflows to one preview-first,
explicitly confirmed, auditable, and action-specific verified execution path.
It does not add batch repair, automatic reboot, retry, rollback, remote apply,
or an extras RPM.

## Highlights

- Eleven audited Action Center definitions: the original three plus eight
  independent Assurance actions.
- Exact Fedora NEVRA, Flatpak ref/commit, firmware device/version/checksum,
  application identity, cleanup target, and snapshot readback verification.
- Durable reboot-aware runs for Atomic Fedora, firmware, and Atomic application
  changes.
- Schema-v2 plan/run envelopes with atomic v1 migration and future-schema
  read-only behavior.
- A route-table-enforced read-only HTTP API; token issuance is its only mutating
  method.
- Canonical UI and legacy CLI flows create plans and never auto-apply them.

## Compatibility and scope

Stable routes, aliases, Home, search, the three original actions, CLI, daemon,
IPC, and v1 Action Center history remain readable. Fedora 45 stays read-only.
Raw Btrfs snapshots, RPM database repair, external RPM URLs, repository
bootstrap, restore/delete, and Advanced mutations remain manual or out of
Assurance scope.

Component analysis still reports 114 core/specialist-shared modules, 50
specialist-exclusive modules, and specialist reachability from CLI, API, and
daemon. No physical `-extras` package is created.

## Candidate measurements

- `just verify`: 7,683 passed, 68 skipped, 851 subtests, 86.23% coverage.
- Meaningful Home median: 160.268 ms; RSS median: 78,092 KiB.
- Startup: one Home plugin, zero subprocess probes, timers, or QThreads.
- CI Bandit profile: zero medium/high findings; dependency audit: zero known
  vulnerabilities.

## Physical validation

- Fedora Kinoite 44.1.7 was installed in a clean KVM guest from a
  signature-verified official image. An `rpm-ostree` package layer was staged,
  remained absent before reboot, and appeared in the exact planned deployment
  after a real reboot with a new boot ID.
- fwupd 2.1.6 completed its packaged ColorHug2 host-emulation fixture across two
  signed firmware versions. Physical firmware hardware remains a documented
  manual matrix and is not implied by this result.
- Local RPM, Flatpak, and sdist builds identify version 17.0.0. Version metadata
  is aligned across the Python package, RPM spec, and `pyproject.toml`.

## Publication

The annotated `v17.0.0` tag, canonical workflow, GitHub assets and checksums,
CycloneDX SBOM, in-toto provenance, COPR Fedora 44 build and clean installation,
and public wiki were independently read back successfully. The release commit is
`758e7528558daa200989b2d16a333039c020a4dd`, the workflow is `29716217083`,
and the COPR build is `10748977`.
