# Loofi Fedora Tweaks v7.0.0 "Aegis" Release Announcement

## TL;DR

Loofi Fedora Tweaks v7.0.0 "Aegis" is now available as the safe guided actions and Fedora 44 reliability release. It adds readiness action planning, explicit confirmation for supported mutating actions, Support Bundle v5 diagnostics, and stricter release gates.

**Install:**

```bash
pkexec dnf copr enable loofitheboss/loofi-fedora-tweaks
pkexec dnf install loofi-fedora-tweaks
```

**GitHub Release:** https://github.com/loofiboss-bit/loofi-fedora-tweaks/releases/tag/v7.0.0

---

## What's New

- Guided Action Bridge for safe readiness action planning and verification.
- Action Inbox in the existing readiness dialog with risk, privilege, rollback, and command preview metadata.
- CLI commands under `loofi-fedora-tweaks --cli readiness` for action listing, preview, confirmed run, and verification.
- Support Bundle v5 with privacy-masked Fedora KDE 44 diagnostics and action summaries.
- Stricter CI/release metadata drift gates.

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
loofi-fedora-tweaks --cli readiness --target 44
loofi-fedora-tweaks --cli readiness actions --target 44
```

---

## Links

- **GitHub Release**: https://github.com/loofiboss-bit/loofi-fedora-tweaks/releases/tag/v7.0.0
- **Full Changelog**: https://github.com/loofiboss-bit/loofi-fedora-tweaks/blob/master/CHANGELOG.md
- **Readiness Guide**: https://github.com/loofiboss-bit/loofi-fedora-tweaks/blob/master/docs/FEDORA_KDE_44_READINESS.md
- **Report Issues**: https://github.com/loofiboss-bit/loofi-fedora-tweaks/issues
