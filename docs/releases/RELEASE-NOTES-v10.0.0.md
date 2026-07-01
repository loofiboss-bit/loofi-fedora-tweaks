# Release Notes -- v10.0.0 "Waypoint"

**Release Date:** 2026-07-01
**Codename:** Waypoint
**Theme:** Release Upgrade Assistant and guided readiness UX

## Summary

Loofi Fedora Tweaks v10.0.0 "Waypoint" turns release readiness into a guided upgrade-planning workflow. Fedora KDE 44 remains the stable supported target, while Fedora 45 stays a preview profile with richer read-only checks and clearer explanations.

## Highlights

- Upgrade Assistant entry points from Home and Maintenance.
- Expanded Fedora 45 preview checks for repo layout, Python 3.15/Setuptools, IPv6-mostly NetworkManager, Podman 6, Atomic Flatpak filtering, RPM/OpenSSL compatibility, and PackageKit-DNF5 consistency.
- New CLI commands: `readiness plan`, `readiness explain`, and `readiness export`.
- Support Bundle v6 adds release plan, target changes, action history, update preview, and redacted package/repo health.
- Smart Updates scheduled service generation now validates package names and writes explicit executable commands.
- User guide and wiki screenshots were regenerated from the v10 PyQt UI, including the new Upgrade Assistant view.

## Upgrade Notes

No saved routes, favorites, plugin IDs, or settings are renamed. Fedora 45 remains advisory preview guidance until it becomes a supported target in a later release.
