# Fedora KDE 44 Readiness

Loofi Fedora Tweaks v5.0.0 "Aurora" includes a read-only readiness center for Fedora KDE 44. It is designed to explain compatibility signals before an upgrade or after a fresh install without changing system state.

## Run It

GUI:

- Open **Atlas Home**.
- Choose **Fedora KDE 44 Readiness**.
- Use **Advanced** only when you need raw command/status details.

CLI:

```bash
loofi-fedora-tweaks --cli fedora44-readiness
loofi-fedora-tweaks --cli fedora44-readiness --advanced
loofi-fedora-tweaks --cli --json fedora44-readiness
```

## What It Checks

- Fedora release, with Fedora KDE 44 as the supported target and Fedora 43 as best-effort compatible.
- KDE Plasma and Qt versions.
- Wayland vs X11 session.
- Display manager and Plasma login manager status, including SDDM/GDM detection.
- DNF5, PackageKit, DNF/RPM locks, repository query health, COPR/RPM Fusion risk signals.
- Atomic/rpm-ostree status, pending deployment, and layered packages.
- NVIDIA hardware, kernel module status, akmods, Secure Boot, and MOK state.
- Flatpak KDE runtimes.
- `/etc/pki/tls/cert.pem` compatibility.

## Safety Model

Readiness checks never execute repair commands. Any command shown in the UI or JSON output is a preview of the read-only probe used to inspect the system.

Repair actions remain part of the Atlas action model and must include:

- risk level
- command preview
- dry-run/preview behavior where relevant
- rollback or revert guidance

## Support Bundle v3

Support bundles now include privacy-masked Fedora KDE 44 readiness data:

- Fedora/KDE/Qt versions
- session type and display manager
- DNF5/PackageKit status
- rpm-ostree status
- NVIDIA/akmods/Secure Boot status
- failed services
- recent journal warnings/errors
- Flatpak runtimes
- masked repository list

Home paths, token-like values, and private file contents are not intentionally included.
