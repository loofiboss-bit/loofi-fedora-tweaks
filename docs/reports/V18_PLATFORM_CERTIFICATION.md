# v18 Platform Certification

Date: 2026-07-22
Release: `18.0.0 "Haven"`; canonical tag commit
`6cfe11babd502d32bb57f333f1f505615a4f8864`

## Fedora 44 Traditional

The release candidate ran on a physical Fedora Linux 44 KDE Plasma host with
kernel `7.1.4-202.fc44.x86_64`, Plasma `6.7.3`, KWin `6.7.3`, and PyQt `6.11.0`.
The active session used Wayland on a 1920 x 1080 internal panel at 1.4 scale.

- The real Wayland main window rendered and reported the title
  `Loofi Fedora Tweaks v18.0.0`.
- The XCB/XWayland path rendered the same release candidate at 1,180 DIP width.
- CLI readback reported version `18.0.0`, codename `Haven`, system type
  `Traditional`, and package manager `dnf`.
- The full suite passed with 6,796 tests, 68 skips, and 86.24 percent coverage.

The deterministic v16 shell matrix remains the release gate for 860, 1,180,
and 1,400 DIP layouts, 100-200 percent scaling, themes, keyboard navigation,
focus, and accessibility. Haven preserves that shell contract and adds no new
layout system.

## Fedora 44 Atomic

The current Fedora 44 Atomic platform evidence is the v17 Kinoite 44.1.7 KVM
certification in `V17_PHASE6_ATOMIC_VM.md`. That run installed the signed
official image, staged a real rpm-ostree deployment, rebooted the guest, and
verified the exact booted checksum and layered RPM identity.

Haven preserves the Assurance rpm-ostree execution and verification contract.
Its regression matrix reran the Atomic branches, including exact staged
deployment matching, the `awaiting_reboot` boundary, boot-ID change, package
identity readback, and the prohibition on automatic reboot, retry, or rollback.
No fresh v18 guest installation was performed, so the release evidence treats
the Kinoite run as carried-forward platform certification backed by current
Haven contract tests rather than as a new v18 guest-reboot claim.

## Support boundary

Fedora 44 is the supported release target. Fedora 45 remains preview-only.
Firmware behavior is covered by the signed fwupd emulation recorded for v17;
the project does not claim fresh physical firmware-device coverage for Haven.
