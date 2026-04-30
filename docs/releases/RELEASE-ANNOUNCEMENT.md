# Loofi Fedora Tweaks v5.0.0 "Aurora" Release Announcement

## TL;DR

Loofi Fedora Tweaks v5.0.0 "Aurora" is now available as the Fedora KDE 44 Experience & Compatibility release. It adds a read-only readiness center, Support Bundle v3 diagnostics, Fedora 44 COPR targeting, and optional RPM subpackages for Web API and daemon runtimes.

**Install:**

```bash
pkexec dnf copr enable loofitheboss/loofi-fedora-tweaks
pkexec dnf install loofi-fedora-tweaks
```

**GitHub Release:** https://github.com/loofiboss-bit/loofi-fedora-tweaks/releases/tag/v5.0.0

---

## What's New

- Fedora KDE 44 readiness checks for Fedora version, Plasma, Qt, Wayland/X11, display manager, DNF5, PackageKit, third-party repos, Atomic/rpm-ostree, NVIDIA/akmods/Secure Boot, Flatpak KDE runtimes, and TLS cert compatibility.
- Dashboard card and focused detail view for beginner/advanced readiness output.
- CLI command: `loofi-fedora-tweaks --cli fedora44-readiness`.
- Support Bundle v3 with privacy-masked Fedora KDE 44 diagnostics.
- Optional packages: `loofi-fedora-tweaks-api` and `loofi-fedora-tweaks-daemon`.

---

## Installation & Usage

**Fedora 44 via COPR:**

```bash
pkexec dnf copr enable loofitheboss/loofi-fedora-tweaks
pkexec dnf install loofi-fedora-tweaks
```

**Optional runtimes:**

```bash
pkexec dnf install loofi-fedora-tweaks-api
pkexec dnf install loofi-fedora-tweaks-daemon
```

**Run readiness:**

```bash
loofi-fedora-tweaks --cli fedora44-readiness
loofi-fedora-tweaks --cli --json fedora44-readiness
```

---

## Links

- **GitHub Release**: https://github.com/loofiboss-bit/loofi-fedora-tweaks/releases/tag/v5.0.0
- **Full Changelog**: https://github.com/loofiboss-bit/loofi-fedora-tweaks/blob/master/CHANGELOG.md
- **Readiness Guide**: https://github.com/loofiboss-bit/loofi-fedora-tweaks/blob/master/docs/FEDORA_KDE_44_READINESS.md
- **Report Issues**: https://github.com/loofiboss-bit/loofi-fedora-tweaks/issues
