# v19 Phase 6 Platform Certification

Date: 2026-07-25  
Result: pass for the current Fedora 44 Traditional and Atomic release targets

## Traditional Fedora

The real-shell, accessibility, state, startup, and System Check duration gates
ran on:

```text
Fedora Linux 44 (KDE Plasma Desktop Edition)
KDE Plasma 6.7.3
Wayland
kernel 7.1.4-204.fc44.x86_64
```

The detailed machine-readable evidence is recorded in:

- `docs/reports/V19_PHASE6_ATSPI.json`
- `docs/reports/V19_PHASE6_ATSPI_XCB.json`
- `docs/reports/V19_PHASE6_CHECK_BENCHMARK.json`
- `docs/reports/V19_PHASE6_STARTUP.json`
- `docs/reports/V19_PHASE6_STATE_SCREENSHOTS.json`

## Atomic installation provenance

Guest: Fedora Linux 44.1.7 (Kinoite), kernel
`6.19.10-300.fc44.x86_64`  
Hypervisor: KVM/libvirt  
VM: `loofi-v19-kinoite44-validation`

- Official image: `Fedora-Kinoite-ostree-x86_64-44-1.7.iso`
- Image size: 4,092,461,056 bytes
- SHA-256:
  `4a944312b4e861ab625fd9786957174ef122a8a406bbb54caba7665e0d9f0e92`
- The Fedora checksum file had a good signature from
  `Fedora (44) <fedora-44-primary@fedoraproject.org>` using key
  `36F612DCF27F7D1A48A835E4DBFCF71C6D9F90A6`.
- The unattended installer deployed the media-local ref
  `fedora/44/x86_64/kinoite`.

## Initial Atomic boot

```text
boot ID: 2d0444b7-183f-4736-8e07-036137c188fc
booted checksum: 13e5eb8feb19a2cd200d10ecd06c5d04f77c6e5324e74f8d57940e67b6189b3d
origin: fedora:fedora/44/x86_64/kinoite
requested local packages: []
```

The validation RPM was built from the current worktree before any v19 version
bump. Its `18.0.0-1.fc44` identity is therefore intentional release-gate
metadata, not a claim that v19 had already shipped.

## Staged deployment and first reboot

The first RPM had SHA-256
`beb08a87addd4fdf2ea656d1a3c510c80b733fea809336a207f7f19ca79a6cf0`.
`rpm-ostree install` resolved the PyQt6 and keyring dependencies and staged:

```text
booted: false
staged: true
checksum: d48028228c9f2fae28c85ca6cb6187aff08836ab5918079afc23935cbe8071aa
requested local packages: ["loofi-fedora-tweaks-1:18.0.0-1.fc44.noarch"]
```

After a real reboot:

```text
boot ID: 0a78f356-5f4c-448b-8dbe-1035baa7ef4c
booted checksum: d48028228c9f2fae28c85ca6cb6187aff08836ab5918079afc23935cbe8071aa
staged: false
installed identity: loofi-fedora-tweaks-18.0.0-1.fc44.noarch
```

The installed System Check completed with `atomic: true` and no source errors.
It also exposed a false Traditional-only warning: the DNF health probe was
being interpreted as applicable package-health evidence on Kinoite.

## Atomic correction and exact replacement readback

The package-health card now preserves its stable ID while reporting
rpm-ostree-owned health on Atomic systems. The focused regression suite and the
complete `just verify` gate passed before rebuilding.

Corrected RPM SHA-256:
`68e7067e2a742a6b1ca358dcd51fff621ac524ca900c5c3618b95c30282f2923`

The same-NEVRA local package was atomically replaced in one rpm-ostree
transaction. Before reboot:

```text
booted: false
staged: true
checksum: ab9c5c6695f802563d7a7ba8a7b2b15c732bb4bc69f768fee2e0c70cd2c095d5
requested local packages: ["loofi-fedora-tweaks-1:18.0.0-1.fc44.noarch"]
```

After the second real reboot:

```text
boot ID: 37f8cb26-c1ff-4a66-b83d-f6affcb337ed
booted checksum: ab9c5c6695f802563d7a7ba8a7b2b15c732bb4bc69f768fee2e0c70cd2c095d5
staged: false
requested local packages: ["loofi-fedora-tweaks-1:18.0.0-1.fc44.noarch"]
```

The installed and worktree copies of
`core/diagnostics/daily_maintenance.py` both had SHA-256
`ce82f36826c13589954bf8c634668c8055704a697c3d37657c4aa4f05690b265`.

The corrected guest run reported:

```text
schema: loofi.system-check v1
state: completed
atomic: true
source errors: []
package-health false warning: absent
```

One genuine failed unit from the unattended guest installation,
`systemd-remount-fs.service`, remained visible as a cross-variant finding. This
is host evidence, not a System Check failure or an automatic mutation request.

Fedora 44 remains the stable support target. Fedora 45 remains preview-only
because it was not a stable release at candidate time and was not promoted by
this certification.
