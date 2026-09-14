# Fedora Tweaks & Verified Maintenance Guide

Loofi Fedora Tweaks provides a curated, verified approach to optimizing and maintaining Fedora Linux. Rather than applying unverified scripts, registry-style tweaks, or disabling core security features, Loofi focuses on high-impact, measurable system maintenance that preserves system stability across Fedora releases.

This guide details the supported maintenance tasks, performance inspections, and storage optimizations available in **v28.0.2 "Ease"**.

---

## 1. System & Package Maintenance

Fedora uses modern package management backends (DNF5 on traditional workstations; `rpm-ostree` and `bootc` on Atomic desktops). Keeping package databases healthy and clean prevents dependency errors, disk bloat, and transaction lockups.

![Updates & Maintenance](images/maintenance-updates.png)

### Package Cache & Metadata Management
- **DNF5 Cache Cleanup**: Safely prunes stale metadata and cached packages from `/var/cache/libdnf5/` without breaking active transactions or repository definitions.
- **Independent Probes**: System packages, Flatpaks, and hardware firmware (via `fwupd`) are queried independently. A slow or unreachable remote does not block other update checks.
- **Transaction History**: Inspect past package transactions and identify package conflicts before applying changes.

```bash
# Check update status from the command line
loofi updates check

# Inspect known repository or dependency conflicts
loofi updates conflicts

# Review recent transaction history
loofi updates history
```

---

## 2. Storage Reclaim & Journal Hygiene

Fedora systems can accumulate gigabytes of cached data and historical journal logs over months of regular use. Loofi provides a transparent preview before any files are pruned.

![Storage Cleanup Preview](images/cleanup-preview.png)

### Systemd Journal Pruning
The `systemd-journald` service records system events continuously. On systems with heavy logging, journals can consume several gigabytes of `/var/log/journal/`.
- **Verified Vacuuming**: Prunes logs older than 7 days or constrains journal size to a healthy maximum (e.g. 200 MB).
- **Integrity Verification**: Verifies that active logs remain readable and `journalctl --verify` passes.

### User Cache Pruning
- **Thumbnail & App Caches**: Reclaims space from `~/.cache/thumbnails/` and obsolete application cache directories.
- **Zero Risk**: Never touches personal user documents, configurations in `~/.config`, or application databases.

---

## 3. Hardware & Power Optimization

![Hardware & System Monitor](images/system-monitor.png)

### Laptop Battery Health (Charge Thresholds)
Charging a modern lithium-ion laptop battery to 100% and leaving it plugged in degrades chemical cell capacity over time. Setting an 80% charge threshold extends long-term battery lifespan.
- **Hardened Kernel Sysfs Support**: Utilizes the Linux kernel sysfs interface (`/sys/class/power_supply/*/charge_control_end_threshold`) supported by ASUS, Lenovo ThinkPad, and other modern laptops.
- **Systemd Battery Service**: Hardened in v28.0.2 to ensure service stability, clean startup, and graceful degradation on unsupported hardware.
- **Safety**: If the host hardware or battery controller does not expose a supported kernel sysfs node, the feature reports itself as unavailable rather than failing or applying invalid configurations.

### ZRAM Compressed Swap Monitoring
Fedora enables ZRAM by default via `systemd-zram-setup@zram0.service`, compressing RAM pages to provide fast swap without wearing SSD storage.
- **Status Inspection**: Verifies ZRAM device status, compression algorithm (Zstandard/LZ4), and active compression ratios.
- **Safety Boundary**: Loofi does not apply aggressive swappiness or vm-dirty hacks that can cause out-of-memory lockups under heavy loads.

---

## 4. Flatpak Runtime & Application Hygiene

Flatpak is Fedora's primary sandbox application runtime. Over time, outdated runtimes from uninstalled applications remain stored on disk.

![Software Center Handoff](images/install-app.png)

- **Orphaned Runtime Detection**: Identifies installed Flatpak runtimes that are no longer referenced by any installed application (`flatpak uninstall --unused`).
- **User vs. System Scope**: Distinguishes between system-wide Flatpaks (`/var/lib/flatpak`) and per-user Flatpaks (`~/.local/share/flatpak`).
- **Desktop Handoff**: Rather than embedding a redundant custom software store, Loofi hands off application installation requests directly to Fedora's native software center (GNOME Software or KDE Discover) using standard AppStream/XDG identifiers.

---

## 5. Security & Network Exposure

![Security & Firewall Overview](images/security-privacy.png)

### Firewall Zone Audit
Fedora includes `firewalld` by default. Loofi inspects active zones and open network ports:
- **Listening Services**: Audits open TCP/UDP ports and active network interfaces.
- **Zone Hygiene**: Verifies that the default zone (typically `FedoraWorkstation` or `public`) does not expose unexpected local development servers or file sharing services to untrusted networks.

### SELinux Status
- **Enforcing Mode**: Verifies that SELinux is active and in `Enforcing` mode.
- **Policy Integrity**: Loofi strictly enforces SELinux best practices and never provides options or scripts to disable SELinux.

---

## 6. Protection, Backups & Rollbacks

![Protection & Recovery](images/restore-preview.png)

- **Btrfs Subvolume Snapshots**: On standard Fedora Btrfs installations, inspects root (`/`) and home (`/home`) subvolume snapshot states.
- **Atomic Deployment Rollbacks**: On Fedora Silverblue and Kinoite, tracks deployment rollbacks via `rpm-ostree` with explicit reboot requirements.
- **Trusted Change Journal**: Every system modification initiated through Loofi is logged with its preflight checks, authorization timestamp, execution log, and verification result in `~/.local/share/loofi-fedora-tweaks/journal/`.

---

## 7. The Loofi Philosophy: Safe vs. Unsafe Tweaks

Many Linux "tweaking" utilities advertise dubious performance scripts that can destabilize your installation. Loofi adheres to strict engineering principles:

| Practice | Loofi Approach | Why It Matters |
| --- | --- | --- |
| **SELinux** | Always Enforcing | Disabling SELinux compromises Fedora's primary security perimeter. |
| **Sysctl Hacks** | Avoided | Arbitrary `sysctl.conf` tweaks often cause memory pressure and kernel panics under load. |
| **Root Execution** | Strictly Forbidden | Loofi runs as a regular user; `pkexec` is invoked only for reviewed, specific operations. |
| **Background Daemons** | None | No idle CPU usage, memory consumption, or background telemetry. |
| **Change Lifecycle** | Plan → Auth → Run → Verify | Every modification is independently verified after execution. |

