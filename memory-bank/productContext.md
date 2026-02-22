# Product Context — Loofi Fedora Tweaks

## Why This Project Exists

Fedora Linux ships with powerful but fragmented system tools — `dnf`, `systemctl`, `firewall-cmd`, `nmcli`, `journalctl`, and dozens more. Each requires memorizing different syntax and flags. Loofi Fedora Tweaks unifies these into a single desktop application with a consistent interface.

## Problems It Solves

- **Tool fragmentation**: Users switch between 20+ CLI tools for routine system tasks
- **Complexity barrier**: Many Fedora features (SELinux, Firewalld, VFIO, Btrfs snapshots) require expert knowledge
- **No unified dashboard**: No single app provides system health, diagnostics, and management
- **Atomic Fedora gap**: rpm-ostree workflows differ from traditional dnf — the app handles both transparently
- **Automation gap**: Recurring maintenance tasks require custom scripts or cron jobs

## How It Works

- **GUI** (default): PyQt6 desktop app with 28 lazy-loaded tabs organized in a sidebar with 7 categories
- **CLI** (`--cli`): Subcommands with `--json` output for scripting and automation
- **Daemon** (`--daemon`): Background scheduler for automated maintenance tasks
- **API** (`--api`): FastAPI REST server for remote management and integration

All four modes consume the same `services/` and `utils/` business logic layer — UI and CLI are consumers only.

## User Experience Goals

- **Lazy loading**: Tabs load on-demand for fast startup (< 2s target)
- **Experience levels**: Beginner/Intermediate/Expert modes to control feature visibility
- **Guided tour**: Interactive onboarding for new users
- **Themes**: Abyss (dark) and Light themes with QSS styling
- **Safety**: Dangerous operations require confirmation dialogs + optional safety snapshots
- **Health dashboard**: System health score with timeline and detailed diagnostics
- **Plugin ecosystem**: Marketplace with ratings, reviews, hot-reload, and sandboxed execution

## Target Users

- Fedora desktop users who want a graphical system management tool
- System administrators who need CLI/API access to common operations
- Power users who want automation, profiles, and export capabilities
- Developers working in Fedora environments who need quick system diagnostics
