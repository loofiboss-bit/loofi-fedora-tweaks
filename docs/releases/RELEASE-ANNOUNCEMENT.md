# Loofi Fedora Tweaks v17.0.0 "Assurance" Release Announcement

## TL;DR

Assurance makes the five canonical system-changing workflows preview-first,
explicitly confirmed, audited, and verified. Fedora, Flatpak, firmware,
application, cleanup, and recovery-point operations now converge on Action
Center without adding automatic retry, reboot, rollback, or remote apply.

The release is live on GitHub and the Fedora 44 COPR repository. Checksums,
CycloneDX SBOM, in-toto/SLSA provenance, RPMs, Flatpak, and source distribution
were read back and verified against the exact release commit.

## Highlights

- Eleven deny-by-default Action Center definitions retain one action and one
  command vector per plan.
- Exact planned RPM identities, Flatpak refs/commits, firmware facts, cleanup
  targets, and recovery-point evidence drive outcome verification.
- Atomic Fedora and firmware operations persist safely across required reboots.
- Schema-v2 history migrates v1 stores atomically and keeps future schemas
  read-only.
- The Web API route table is read-only except for token issuance.
- The v16 shell, routes, state, CLI, daemon, IPC, and original Action Center
  definitions remain compatible.

## Install or upgrade

```bash
pkexec dnf copr enable loofitheboss/loofi-fedora-tweaks
pkexec dnf upgrade loofi-fedora-tweaks
```

Optional runtimes remain separate:

```bash
pkexec dnf install loofi-fedora-tweaks-api
pkexec dnf install loofi-fedora-tweaks-daemon
```

## Links

- **GitHub release**: <https://github.com/loofiboss-bit/loofi-fedora-tweaks/releases/tag/v17.0.0>
- **Release notes**: <https://github.com/loofiboss-bit/loofi-fedora-tweaks/blob/master/docs/releases/RELEASE-NOTES-v17.0.0.md>
- **COPR packages**: <https://copr.fedorainfracloud.org/coprs/loofitheboss/loofi-fedora-tweaks/>
- **Wiki**: <https://github.com/loofiboss-bit/loofi-fedora-tweaks/wiki>
- **Issue tracker**: <https://github.com/loofiboss-bit/loofi-fedora-tweaks/issues>
