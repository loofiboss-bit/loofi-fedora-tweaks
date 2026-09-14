# GUI Destinations Reference — v28.0.2 "Ease"

Loofi Fedora Tweaks features a focused, desktop-neutral graphical interface designed around five primary destinations and one unified change management workspace. The interface adheres to strict safety boundaries: navigating between screens is completely read-only, and persistent host modifications are only executed after explicit review in **Changes**.

---

## Navigation Architecture

```text
Header Bar: [Search Ctrl+K] [Doctor Status] [Settings ⚙]
├── 1. Home                     (System status, single recommended action, quick tasks)
├── 2. Updates & Apps           (System, Flatpak & firmware updates; AppStream handoff)
├── 3. System Health            (System check, troubleshooting, storage, hardware, support bundle)
├── 4. Protection & Recovery    (Firewall exposure, snapshots, rollback guidance, journal)
└── 5. Changes                  (Action Center review, confirmation, execution & verification)
```

The sidebar adapts responsively to window width and font scaling, supporting expanded sidebar, icon rail, and compact dropdown layouts.

---

## 1. Home Dashboard

The Home dashboard provides an immediate, transparent snapshot of system state without triggering background operations or host modifications.

![Home Dashboard](images/home-dashboard.png)

### Key Features
- **System Identity & Environment**: Displays Fedora version, kernel release, desktop environment (GNOME, KDE Plasma, XFCE, Sway, etc.), display server (Wayland / X11), and architecture.
- **Prioritized Recommendation**: Highlights exactly one recommended action based on system health. If no check has been run, it prompts: *"No system check has been run yet"*.
- **Quick Actions**: Rapid shortcuts for frequent read-only checks, including checking updates, auditing firewall status, or reviewing storage usage.
- **Read-Only Safety**: Constructing the Home view or refreshing state never applies changes or initiates background daemon tasks.

---

## 2. Updates & Apps

The Updates & Apps destination handles software updates across multiple independent streams and provides clean handoff to native desktop app stores.

![Updates & Maintenance](images/maintenance-updates.png)

### Independent Update Streams
Rather than bundling package managers into one fragile process, Loofi probes three sources separately:
1. **System Packages**:
   - Traditional Fedora: DNF5 package transactions and security errata.
   - Atomic Fedora: `rpm-ostree` deployment trees and staged commits.
2. **Flatpak Applications**: Queries system-wide (`/var/lib/flatpak`) and user (`~/.local/share/flatpak`) remotes (e.g. Flathub, Fedora Flatpaks).
3. **Hardware Firmware**: Interfaces with `fwupd` to detect UEFI, SSD, and peripheral firmware updates.

If one source is slow or offline, other sources continue uninterrupted. An unavailable source is never falsely marked as "up to date".

### Review Updates Workflow
When updates are available, clicking **Review updates** generates an Action Center plan with:
- Detailed package changelogs and download sizes.
- Risk assessment and restart requirements.
- An explicit handoff to **Changes** for confirmation.

### Native App Center Handoff

![Software Center Handoff](images/install-app.png)

Loofi does not attempt to clone an application marketplace. When discovering or installing new software, Loofi hands off the request to the desktop's native center (GNOME Software or KDE Discover) using standard AppStream identifiers.

---

## 3. System Health

System Health provides deep diagnostics, symptom-based troubleshooting, hardware telemetry, and support bundle generation.

![System Health Troubleshooting](images/troubleshoot.png)

### System Check
Performs a read-only audit across critical Fedora subsystems:
- Package manager database consistency.
- Systemd unit health (detecting failed services).
- SELinux enforcement status.
- Filesystem mount options and storage pressure.

### Symptom-Driven Troubleshooting
Select from bounded diagnostic profiles such as `system_slow`, `network_problem`, `storage_pressure`, and `boot_or_deployment`. Each profile runs allowlisted read-only checks, formats findings, and offers at most one safe, actionable remedy.

### Storage & Reclaim Analysis

![Storage Cleanup Preview](images/cleanup-preview.png)

- Inspects disk utilization across Btrfs partitions and mount points.
- Previews supported cleanup targets: old package cache and systemd journal logs. User thumbnail and application caches are not modified by Loofi.
- Displays an exact byte-count preview before anything is queued for cleanup.

### Hardware & Resource Monitor

![Hardware & System Monitor](images/system-monitor.png)

- Real-time CPU, RAM, and ZRAM compressed swap usage.
- Storage disk I/O metrics and partition consumption.
- Laptop battery health and charge threshold status.

### Redacted Support Bundle
Exports a sanitized `.zip` archive containing system diagnostic logs, Fedora version information, and recent change journal records for reporting bugs on GitHub. Personal tokens, credentials, and passwords are automatically excluded.

---

## 4. Protection & Recovery

Protection & Recovery centralizes security hygiene, system rollback capabilities, and durable change history.

![Security & Firewall](images/security-privacy.png)

### Firewall & Network Exposure
- Audits active `firewalld` zones (e.g., `FedoraWorkstation`, `public`, `home`).
- Lists open ports and listening daemons (SSH, Samba, local web development servers).
- Warns of unexpected exposure on untrusted network interfaces.

### Backups & Rollbacks

![Rollback & Restore Preview](images/restore-preview.png)

- **Btrfs Snapshots**: Detects existing subvolume snapshots and guides recovery.
- **Atomic Rollbacks**: On Silverblue / Kinoite hosts, inspects previous deployment pins and provides rollback instructions with verified reboot handling.

### Trusted Change Journal
A tamper-resistant, chronological audit log of every change executed through Loofi. Each record includes the plan ID, execution timestamp, authorization status, and post-execution verification result.

---

## 5. Changes (The Action Center)

Changes is the **exclusive authority** for executing persistent modifications to the host system. No other screen in the application can directly invoke mutating shell commands or alter system files.

![Action Center Changes](images/action-center.png)

### The Five-Stage Change Lifecycle

```text
1. Preflight Check   → Validates prerequisites, disk space, and package manager lock availability.
2. Plan Review       → User reviews affected packages/files, risk tier, and reboot requirements.
3. Authorization     → Polkit requests administrator credentials via desktop pkexec agent.
4. Bounded Execution → Mutation runs via explicit argv list with strict timeout bounds (no shell).
5. Independent Verify→ A separate read probe verifies the system state matches the desired outcome.
```

### Safety Guarantees
- **Mutation Lease**: Only one change plan can execute at any time; concurrent mutations are blocked.
- **No Silent Retries**: If an operation fails or authorization is canceled, the plan stays in its recorded state without silent retries.
- **Verification Separation**: A process returning exit code `0` is not assumed to have succeeded; Loofi independently checks the target subsystem to confirm the actual change.

---

## Header & Settings

### Global Search (`Ctrl+K`)
Pressing `Ctrl+K` opens the quick launcher. Typing matches destinations, settings, and safe action entry points. Pressing `Ctrl+Shift+K` restricts search results to actionable maintenance items. Selecting an action always navigates to its review surface in **Changes**; it never executes immediately.

### Settings & Doctor

![Settings & Appearance](images/settings-appearance.png)

Accessible via the header gear icon:
- **Appearance**: Toggle Light, Dark, or System theme and choose whether to follow the system theme.
- **Navigation**: The shell responds to window width and text scaling; use the sidebar toggle when available. Settings does not persist a navigation-layout selector.
- **Doctor Diagnostics**: Inspects application health, `pkexec` availability, and Python environment status. A running desktop Polkit agent must be checked separately.

![State Doctor](images/state-doctor.png)
