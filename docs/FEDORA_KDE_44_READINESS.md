# Release Readiness

Loofi Fedora Tweaks v6.0.0 "Compass" includes a read-only release readiness center. Fedora KDE 44 is the supported target, and Fedora 45 is available as a preview-only planning profile.

## Run It

GUI:

- Open **Atlas Home**.
- Choose **Release Readiness**.
- Use **Advanced** only when you need raw command/status details.

CLI:

```bash
loofi-fedora-tweaks --cli readiness --target 44
loofi-fedora-tweaks --cli readiness --target 45-preview
loofi-fedora-tweaks --cli readiness --target 44 --advanced
loofi-fedora-tweaks --cli --json readiness --target 44
```

Compatibility alias:

```bash
loofi-fedora-tweaks --cli fedora44-readiness
```

## What It Checks

- Fedora release, with Fedora KDE 44 as the supported target and Fedora 45 as preview-only.
- KDE Plasma and Qt versions.
- Wayland vs X11 session.
- Display manager and Plasma login manager status, including SDDM/GDM detection.
- DNF5, PackageKit, DNF/RPM locks, repository query health, COPR/RPM Fusion risk signals.
- Atomic/rpm-ostree status, pending deployment, and layered packages.
- NVIDIA hardware, kernel module status, akmods, Secure Boot, and MOK state.
- Flatpak KDE runtimes.
- TLS certificate compatibility, including Fedora's CA trust bundle layout.

## Safety Model

Readiness checks never execute repair commands. Any command shown in the UI or JSON output is a preview of the read-only probe used to inspect the system.

Recommendation metadata remains manual by default and may include:

- risk level
- command preview
- reversibility
- rollback or revert guidance
- docs link
- manual-only flag

Repair actions remain part of the Atlas action model and must use existing `pkexec` and rollback conventions before anything mutates the system.

## Support Bundle v4

Support bundles now include privacy-masked generic `release_readiness` data:

- Fedora/KDE/Qt versions
- session type and display manager
- DNF5/PackageKit status
- rpm-ostree status
- NVIDIA/akmods/Secure Boot status
- failed services
- recent journal warnings/errors
- Flatpak runtimes
- masked repository list

The legacy `fedora_kde_44_readiness` field is preserved as an alias for older support tooling.

Home paths, token-like values, and private file contents are not intentionally included.
