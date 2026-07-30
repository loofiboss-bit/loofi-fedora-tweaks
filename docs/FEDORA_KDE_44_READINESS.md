# Release Readiness

Loofi Fedora Tweaks v23.0.2 "Compass" keeps the read-only release
readiness center, guided Upgrade Assistant, verified Action Center entry points,
and health history inside the six-destination shell. Fedora KDE 44 is the
supported stable target. Fedora 45 remains preview-only and advisory.

## Run It

GUI:

- Open **Software & Updates → Upgrade Assistant**, or use global search for
  **Release Readiness**.
- Review the summary guidance first.
- Expand advanced report details only when you need raw command/status context;
  this is independent of the application's Standard/Advanced navigation mode.
- Use **Action Inbox** to review candidate actions. There is no fix-all action.

CLI:

```bash
loofi-fedora-tweaks --cli readiness --target 44
loofi-fedora-tweaks --cli readiness plan --target 45-preview
loofi-fedora-tweaks --cli readiness explain <check-id> --target 45-preview
loofi-fedora-tweaks --cli readiness export --target 45-preview
loofi-fedora-tweaks --cli readiness --target 44 --advanced
loofi-fedora-tweaks --cli readiness actions --target 44
loofi-fedora-tweaks --cli readiness action-info <action-id> --target 44
loofi-fedora-tweaks --cli readiness action-preview <action-id> --target 44
loofi-fedora-tweaks --cli readiness action-run <action-id> --target 44
loofi-fedora-tweaks --cli readiness action-verify <action-id> --target 44
loofi-fedora-tweaks --cli action-center list --target 44
loofi-fedora-tweaks --cli action-center preview <action-id> --target 44
loofi-fedora-tweaks --cli action-center history
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
- PyQt6/Qt packaging compatibility for Fedora 45 preview planning.
- Atomic/rpm-ostree status, pending deployment, and layered packages.
- NVIDIA hardware, kernel module status, akmods, Secure Boot, and MOK state.
- Flatpak KDE runtimes.
- KDE Plasma session and Wayland assumptions.
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
- `action-run` is a compatibility handoff that creates an Action Center review
  plan and never applies it. The old `--confirm` flag is accepted but ignored.
- Manual-only recommendations cannot be executed.
- Privileged actions route through existing `pkexec` and ActionExecutor conventions.

## Support Bundle v13

Support bundles include privacy-masked generic `release_readiness` data,
release planning metadata, guided action context, Action Center context, My
Fedora Today observability context, bounded System Check evidence, and
source-owned Trusted Change Journal evidence. An explicitly selected Compass
session may also add one bounded troubleshooting support case:

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
- release plan and target change metadata
- update preview and redacted package/repo health details
- recent redacted action history
- Action Center candidates and bounded history
- Action Center timeline recommendations
- Daily Maintenance dashboard signals
- latest health snapshot and bounded health timeline
- recurring problem fingerprints
- rollback hints used for medium/high-risk actions
- daemon and optional Web API status probes
- daemon snapshot status and read-only collection errors
- support-safe GitHub issue text export
- one selected troubleshooting session, at most 50 findings, 25 related
  changes, 25 linked plan/run status records, and one comparison
- at most two System Check results, one comparison, and linked plan/run records
- at most 50 redacted Trusted Change Journal events with source readiness
- privacy manifest

The legacy `fedora_kde_44_readiness` field is preserved as an alias for older support tooling.

Home paths, token/password/secret/key-like values, email addresses, host identifiers, and private file contents are not intentionally included.
