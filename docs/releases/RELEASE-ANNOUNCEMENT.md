# Loofi Fedora Tweaks v14.0.0 "Helm" Release Announcement

## TL;DR

Loofi Fedora Tweaks v14.0.0 "Helm" is now available with expiring Action Center plans, explicit confirmation, bounded first-party maintenance actions, separate outcome verification, and exact release-lineage assurance. Fedora KDE 44 remains the stable supported target, while Fedora 45 remains preview-only and advisory.

**Install:**

```bash
pkexec dnf copr enable loofitheboss/loofi-fedora-tweaks
pkexec dnf install loofi-fedora-tweaks
```

**GitHub Release:** https://github.com/loofiboss-bit/loofi-fedora-tweaks/releases/tag/v14.0.0

---

## What's New

- Review preflight, command, privilege, risk, rollback readiness, execution, and verification in one Action Center flow.
- Execute only audited DNF cache, selected failed-service, and supported SSD trim actions.
- Preserve expiring plans and interrupted runs without automatic retry, rollback, or fix-all behavior.
- Inspect redacted plan/run evidence through Support Bundle v10 and authenticated read-only API routes.
- Verify source, tag, GitHub assets, and Fedora 44/COPR packages against the same commit.

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

**Run the app or CLI:**

```bash
loofi-fedora-tweaks
loofi-fedora-tweaks --cli info
```

---

## Links

- **GitHub Release**: https://github.com/loofiboss-bit/loofi-fedora-tweaks/releases/tag/v14.0.0
- **Full Changelog**: https://github.com/loofiboss-bit/loofi-fedora-tweaks/blob/master/CHANGELOG.md
- **Architecture Guide**: https://github.com/loofiboss-bit/loofi-fedora-tweaks/blob/master/ARCHITECTURE.md
- **Report Issues**: https://github.com/loofiboss-bit/loofi-fedora-tweaks/issues
