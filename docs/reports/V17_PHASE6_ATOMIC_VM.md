# v17 Phase 6 -- Fedora Kinoite 44 Atomic VM

Date: 2026-07-20
Guest: Fedora Linux 44.1.7 (Kinoite), kernel 6.19.10-300.fc44.x86_64
Hypervisor: KVM/libvirt
Result: pass

## Installation provenance

- Official image: `Fedora-Kinoite-ostree-x86_64-44-1.7.iso`
- Image size: 4,092,461,056 bytes
- SHA-256:
  `4a944312b4e861ab625fd9786957174ef122a8a406bbb54caba7665e0d9f0e92`
- The Fedora checksum file had a good signature from
  `Fedora (44) <fedora-44-primary@fedoraproject.org>` using key
  `36F612DCF27F7D1A48A835E4DBFCF71C6D9F90A6`.
- The unattended installer deployed the media-local ref
  `fedora/44/x86_64/kinoite`; all 129,580 OSTree objects were copied before
  deployment.

## Initial boot

```text
boot ID: 35db53e3-22e5-42a3-b38b-1352f181c26a
booted checksum: 13e5eb8feb19a2cd200d10ecd06c5d04f77c6e5324e74f8d57940e67b6189b3d
origin: fedora:fedora/44/x86_64/kinoite
requested packages: []
```

`rpm -q zsh` confirmed that the selected validation package was absent.

## Staged deployment

`rpm-ostree install zsh` resolved and installed
`zsh-5.9-20.fc44.x86_64`, then reported that changes were queued for the next
boot. Before reboot, `rpm-ostree status --json` reported:

```text
booted: false
staged: true
checksum: 8020e4f45b49613da469349c7d77bd650d6d7ca4903127664308c5ec25090f0d
base checksum: 13e5eb8feb19a2cd200d10ecd06c5d04f77c6e5324e74f8d57940e67b6189b3d
requested packages: ["zsh"]
```

The original deployment remained `booted: true`, and `rpm -q zsh` still
reported the package as absent. This is the expected Assurance
`awaiting_reboot` boundary.

## Reboot readback

After a real guest reboot:

```text
boot ID: 47c1d09c-ac2e-4bc7-90dd-85d052bb86a3
booted checksum: 8020e4f45b49613da469349c7d77bd650d6d7ca4903127664308c5ec25090f0d
staged: false
base checksum: 13e5eb8feb19a2cd200d10ecd06c5d04f77c6e5324e74f8d57940e67b6189b3d
requested packages: ["zsh"]
installed identity: zsh-5.9-20.fc44.x86_64
```

The new boot ID, exact expected booted checksum, requested-package readback,
and installed RPM identity all matched. No automatic reboot, retry, or rollback
was used.
