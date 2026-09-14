# Atomic & Immutable Fedora Guide — v28.0.2 "Ease"

Loofi Fedora Tweaks natively understands Fedora's immutable desktop variants, including **Fedora Silverblue** (GNOME), **Fedora Kinoite** (KDE Plasma), **Fedora Sericea** (Sway), **Fedora Onyx** (Budgie), and containerized **bootc** systems.

The core architecture uses `PlatformProfile` to detect deployment capabilities before displaying operations. It clearly distinguishes `rpm_ostree`, `bootc`, and traditional `dnf5` backends; it never treats an unknown host as a standard DNF system.

---

## Architectural Distinctions

| Characteristic | Traditional Fedora (Workstation) | Atomic Fedora (Silverblue / Kinoite) |
| --- | --- | --- |
| **System Root** | Read-write (`/`, `/usr`) | Read-only sysroot (`/usr` is immutable) |
| **Package Backend** | DNF5 | `rpm-ostree` or `bootc` |
| **Update Mechanism** | In-place package replacement | Staged image deployment tree |
| **Application Layer** | RPM packages + Flatpaks | Flatpaks (recommended) + minimal RPM layering |
| **Activation** | Immediate (some services need restart) | Staged (active upon next reboot) |

---

## How Loofi Handles Atomic Systems

### 1. Capability-Aware Probing
When launched on an Atomic system, Loofi:
- Detects the active deployment commit, pinned deployments, and staged updates.
- Disables traditional package manager operations (such as direct DNF cache writes) that do not apply to ostree images.
- Keeps Flatpak inspection independent: user and system Flatpak updates are fully operational without altering the ostree image.

### 2. Staged Deployment Lifecycle
On Atomic hosts, updating the base system creates a new staged deployment tree:
1. **Check**: `loofi updates check` queries the ostree remote for new deployment commits.
2. **Review**: The Action Center creates a plan summarizing commit metadata and changed packages.
3. **Execution**: The plan runs `rpm-ostree upgrade` without rebooting your machine.
4. **Staged Notification**: Loofi indicates that a new deployment is staged and awaiting a system reboot.
5. **Reboot Verification**: After you reboot using your desktop session controls, run `loofi changes verify <RUN_ID>` to confirm the booted deployment matches the target commit.

Loofi **never** runs `systemctl reboot` automatically.

```bash
# Verify the detected package backend
loofi --json info | jq -r '.package_manager'

# Check for staged or pending ostree updates
loofi updates check
```

---

## Best Practices on Atomic Desktops

- **Prefer Flatpaks for Desktop Software**: Installing GUI applications via Flatpak keeps the base ostree clean and avoids slow ostree layering operations.
- **Layer Packages Sparingly**: Keep `rpm-ostree install` restricted to low-level system utilities (e.g. specialized kernel modules, virtualization drivers, or VPN packages).
- **Rollback Safety**: If a newly booted deployment causes issues, use the GRUB boot menu to select the previous deployment, or use `rpm-ostree rollback`. Loofi's **Protection & Recovery** destination detects previous deployment pins.

---

## Bootc Systems

On Fedora systems managed via `bootc` (bootable containers), Loofi identifies the `bootc` backend and presents clear, manual guidance rather than attempting to route commands through `rpm-ostree`.
