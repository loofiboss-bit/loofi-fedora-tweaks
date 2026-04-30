# Release Notes -- v5.0.0 "Aurora"

**Release Date:** 2026-04-30  
**Codename:** Aurora  
**Theme:** Fedora KDE 44 Experience & Compatibility

## Summary

v5.0.0 "Aurora" makes Fedora KDE 44 the supported target for Loofi Fedora Tweaks. It builds on the v4.0.0 "Atlas" assistant architecture with a read-only readiness center, support bundle v3 diagnostics, Fedora 44 release workflow alignment, and a cleaner RPM dependency split.

## Highlights

- Fedora KDE 44 Readiness Center for Fedora, Plasma, Qt, Wayland/X11, display manager, DNF5, PackageKit, repos, Atomic, NVIDIA/akmods/Secure Boot, Flatpak KDE runtimes, and TLS certificate compatibility.
- Dashboard card that opens a focused readiness detail view without adding another permanent sidebar tab.
- CLI command: `loofi-fedora-tweaks --cli fedora44-readiness [--advanced]`.
- Support Bundle v3 with privacy-masked Fedora KDE 44 diagnostics.
- Optional RPM subpackages for Web API and daemon runtime dependencies.

## Changes

### Added

- `core/diagnostics/fedora44_readiness.py`
- `services/desktop/kde44.py`
- `services/package/dnf5_health.py`
- `core/export/support_bundle_v3.py`
- `ui/fedora44_readiness_dialog.py`
- `docs/FEDORA_KDE_44_READINESS.md`

### Changed

- Runtime version, package version, project metadata, workflow metadata, changelog, roadmap, and docs now target `5.0.0 "Aurora"`.
- Active COPR chroot and CI container references now target Fedora 44.
- Base RPM no longer requires FastAPI/Uvicorn/JWT/bcrypt/httpx for normal GUI/CLI use.

### Compatibility

- Fedora KDE 44 is the supported target.
- Fedora 43 is best-effort compatible where existing checks and workflows still apply.
- Readiness checks are read-only and do not execute repairs.

## Upgrade Notes

Install the base package for GUI/CLI use:

```bash
sudo dnf install loofi-fedora-tweaks
```

Install optional runtime packages only when needed:

```bash
sudo dnf install loofi-fedora-tweaks-api
sudo dnf install loofi-fedora-tweaks-daemon
```

Run readiness from the CLI:

```bash
loofi-fedora-tweaks --cli fedora44-readiness
loofi-fedora-tweaks --cli --json fedora44-readiness
```
