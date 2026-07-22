# Loofi Fedora Tweaks v18.0.0 "Haven" Release Announcement

## TL;DR

Haven makes Action Center the single local trust boundary for host changes.
The GUI, CLI, daemon, automation, and agent entry points all produce the same
reviewable plans, and unattended paths cannot confirm or execute them.

The public release is verified end to end. The annotated tag resolves to
`6cfe11babd502d32bb57f333f1f505615a4f8864`; GitHub Actions, release assets,
checksums, SBOM, provenance, COPR build `10764217`, and a clean Fedora 44
repository installation all passed independent readback.

## Highlights

- 80 stable routes project from one reviewed product catalog.
- 56 first-party Action Center definitions declare capability, preview,
  confirmation, verification, and recovery policy.
- Action plan and run state uses schema v3 with atomic migration and
  last-known-good recovery.
- The public Marketplace and executable third-party Python extensions are
  retired; local profiles are data-only.
- Persistent secrets use Secret Service without a plaintext fallback.
- The optional API is loopback-only and read-only apart from local token
  lifecycle operations.

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

- **GitHub release**: <https://github.com/loofiboss-bit/loofi-fedora-tweaks/releases/tag/v18.0.0>
- **Release notes**: <https://github.com/loofiboss-bit/loofi-fedora-tweaks/blob/master/docs/releases/RELEASE-NOTES-v18.0.0.md>
- **COPR packages**: <https://copr.fedorainfracloud.org/coprs/loofitheboss/loofi-fedora-tweaks/>
- **Wiki**: <https://github.com/loofiboss-bit/loofi-fedora-tweaks/wiki>
- **Issue tracker**: <https://github.com/loofiboss-bit/loofi-fedora-tweaks/issues>
