# v27.0.0 "Core" — Fedora Maintenance Core

Pre-release local candidate. Current public release is v26.0.3 "Everyday".

## Highlights

- Five focused destinations: Home, Updates & Apps, System Health, Protection & Recovery, and Changes.
- True Fedora neutrality via immutable `PlatformProfile` supporting Workstation, KDE, Silverblue, Kinoite, and Atomic desktops.
- Application management delegated neutrally to installed desktop software center via AppStream/XDG (`appstream://`).
- Strict Action Center mutation boundary for all system changes; direct subprocess mutation removed from UI views.
- Decommissioned specialist and experimental suites (AI Lab, Agents, Automation, Loofi Link, State Teleport, Gaming, Development, Virtualization, Community Marketplace, and extensions).
- Streamlined CLI: `info`, `check`, `updates`, `troubleshoot`, `changes`, `activity`, `doctor`, and `support-bundle`.
- Native Polkit execution via allowlisted system tools.

## Architecture and Migration

This is an intentional breaking major release. Legacy CLI subcommands, specialist data models,
and retired routes are decommissioned. Safety and history data (system checks, update snapshots,
Action Center plans, execution logs, and backup records) are preserved.
