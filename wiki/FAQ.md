# Frequently Asked Questions (FAQ) — v28.0.2 "Ease"

---

### What is Loofi Fedora Tweaks?
Loofi Fedora Tweaks is a focused maintenance control center for Fedora Linux. It brings together system health diagnostics, multi-stream updates (DNF5, Flatpak, firmware), storage optimization, laptop battery health, and verified system changes into a single, desktop-neutral application.

---

### How is Loofi different from GNOME Software or KDE Discover?
GNOME Software and KDE Discover are application stores focused on searching, installing, and updating desktop apps. Loofi focuses on **system maintenance**:
- Probing system packages, Flatpaks, and firmware independently.
- Diagnosing system issues (failed systemd units, network drops, storage pressure).
- Cleaning stale package caches and vacuuming oversized systemd journals.
- Monitoring laptop battery charge thresholds and ZRAM compression.
- Providing a formal change review and verification lifecycle.
When you want to discover or install new GUI applications, Loofi hands off the request directly to GNOME Software or KDE Discover via standard AppStream links.

---

### Do I need to run Loofi with `sudo` or as `root`?
**No.** Running GUI applications as root is dangerous and forbidden. Loofi runs entirely as your normal unprivileged user. When a reviewed change (such as updating packages or vacuuming system journals) requires administrator privileges, Loofi requests authentication through `pkexec` and your desktop's Polkit prompt.

---

### Does Loofi run any background services or daemons?
**No.** Loofi contains zero background daemons, zero scheduled cron jobs, and zero telemetry services. When you close the application, it consumes zero CPU and zero memory.

---

### Does Loofi work on Fedora Silverblue, Kinoite, or Atomic desktops?
**Yes.** Loofi automatically detects `rpm-ostree` and `bootc` deployment backends via `PlatformProfile`. On Atomic systems, it manages staged deployment updates and guides you through reboot verification without attempting unsupported DNF operations.

---

### What makes Loofi safer than running shell scripts found online?
- **Closed Action Schemas**: Commands are not arbitrary shell strings; they are structured Python data models with validated parameters.
- **No Shell Interpolation**: Subprocesses are executed using explicit argument lists (`shell=False`), preventing shell injection.
- **Mutation Lease**: Only one change can execute at a time.
- **Independent Verification**: A command exit code of 0 is not treated as proof of success; Loofi independently checks the target system state afterwards.
- **Trusted Change Journal**: Every modification is logged with its timestamp, authorization, and outcome in `~/.local/share/loofi-fedora-tweaks/`.

---

### Can I automate Loofi from terminal scripts?
**Yes.** The CLI provides 8 commands (`info`, `check`, `updates`, `troubleshoot`, `changes`, `activity`, `doctor`, `support-bundle`). Passing the `--json` flag selects command-specific JSON output suitable for parsing with `jq`; inspect each command's schema before automating it.

---

### How do I troubleshoot or file an issue?
1. Run `loofi-fedora-tweaks --cli doctor` to check the environment and `pkexec` availability.
2. Run `loofi-fedora-tweaks --cli support-bundle` to create a sanitized diagnostic ZIP.
3. Open an issue on [GitHub Issues](https://github.com/loofiboss-bit/loofi-fedora-tweaks/issues) with the bundle and reproduction steps.
