# Architecture — v27.0.0 "Core"

## Core Purpose: Fedora Maintenance Core

Transform Loofi Fedora Tweaks into a desktop-neutral Fedora Maintenance Core with five clean destinations, strict Action Center execution, immutable platform profiling, and native Polkit helpers.

## Five Destinations

1. **Home**: System status, single recommended next action, max 5 common tasks. Shows "No system check has been run yet" without false warnings before first check.
2. **Updates & Apps**: System, Flatpak, firmware with strict order (Check → Select source → Review changes → Run → Verify). Application installation handed off neutrally to system software center via AppStream/XDG (`appstream://`).
3. **System Health**: System Check, symptom-driven troubleshooting, storage inspection and reclaim, hardware status, and support bundle. Logs retained purely as diagnostic source and export.
4. **Protection & Recovery**: Firewall/exposure, backup, exact DNF/rpm-ostree rollback, activity history.
5. **Changes**: Linear review and verification workspace (`Needs attention` and `Recent`, state-driven primary button, 5 explicit parts: change, risk, auth, verify, rollback). Settings accessed via header cog.

## Platform Neutrality & `PlatformProfile`

- Immutable `PlatformProfile` in `core/platform/profile.py` detecting Fedora version, architecture (`x86_64`, `aarch64`), desktop (`gnome`, `kde`, `xfce`, `sway`, etc., or `unknown`), session (`wayland`, `x11`, `unknown`), and deployment backend (`dnf5`, `rpm_ostree`, `bootc`, `unknown`).
- Fail-closed: unknown detection never falls back to Workstation, Traditional, or "no reboot required".
- Desktop-neutral `FedoraReadiness` replaces KDE44-specific readiness.

## Security & Execution Boundary

- All persistent host mutations go strictly through Action Center. UI views never import mutator services or run subprocesses directly.
- Native allowlisted `pkexec` commands for system tools.
- CLI reduced to: `info`, `check`, `updates`, `troubleshoot`, `changes`, `activity`, `doctor`, `support-bundle`.
- Decommissioned: local Web API, D-Bus daemon, Flatpak sandbox distribution, and specialist suites (AI Lab, Agents, Automation, Loofi Link, State Teleport, Gaming, Development, Virtualization, Community, Extensions, Profiles).
