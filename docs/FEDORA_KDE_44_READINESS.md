# Release Readiness

Loofi Fedora Tweaks v7.0.0 "Aegis" includes a read-only release readiness center plus safe guided action planning. Fedora KDE 44 is the supported target. Fedora 45 remains preview-only and advisory.

## Run It

GUI:

- Open **Atlas Home**.
- Choose **Release Readiness**.
- Review beginner guidance first.
- Use **Advanced** only when you need raw command/status details.
- Use **Action Inbox** to review candidate actions. There is no fix-all action.

CLI:

```bash
loofi-fedora-tweaks --cli readiness --target 44
loofi-fedora-tweaks --cli readiness --target 44 --advanced
loofi-fedora-tweaks --cli readiness actions --target 44
loofi-fedora-tweaks --cli readiness action-info <action-id> --target 44
loofi-fedora-tweaks --cli readiness action-preview <action-id> --target 44
loofi-fedora-tweaks --cli readiness action-run <action-id> --target 44 --confirm
loofi-fedora-tweaks --cli readiness action-verify <action-id> --target 44
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

Readiness checks are read-only by default. Probe commands shown in beginner, advanced, or JSON output describe inspection steps unless explicitly shown as an Action Inbox candidate.

Guided action candidates include:

- risk level
- command preview
- privilege requirement
- reversibility and rollback hint
- docs link
- manual-only flag
- preflight checks
- verification command or readiness check

Rules:

- No automatic repair.
- No fix-all button.
- `action-preview` never mutates the system.
- `action-run` fails without `--confirm`.
- Manual-only recommendations cannot be executed.
- Privileged actions route through existing `pkexec` and ActionExecutor conventions.

## Support Bundle v5

Support bundles now include privacy-masked generic `release_readiness` data and guided action context:

- Fedora/KDE/Qt versions
- session type and display manager
- DNF5/PackageKit status
- rpm-ostree status
- NVIDIA/akmods/Secure Boot status
- failed services
- recent journal warnings/errors
- Flatpak runtimes
- masked repository list
- action candidates or action plan summary
- recent redacted action history
- privacy manifest

The legacy `fedora_kde_44_readiness` field is preserved as an alias for older support tooling.

Home paths, token/password/secret/key-like values, email addresses, and private file contents are not intentionally included.
