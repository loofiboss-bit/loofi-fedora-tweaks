# Architecture — v28.0.2 "Ease"

Loofi Fedora Tweaks is structured as a layered, modular desktop application with clean boundaries between UI presentation, domain logic, system service probing, and execution authority.

The canonical architecture contract is defined in [ARCHITECTURE.md](https://github.com/loofiboss-bit/loofi-fedora-tweaks/blob/master/ARCHITECTURE.md) and [.workflow/specs/arch-v28.0.2.md](https://github.com/loofiboss-bit/loofi-fedora-tweaks/blob/master/.workflow/specs/arch-v28.0.2.md).

---

## 1. Runtime Layering

```text
                     main.py
                        │
         ┌──────────────┴──────────────┐
         ▼                             ▼
    GUI (ui/)                      CLI (cli/)
   (PyQt6 views)              (Argparse commands)
         │                             │
         └──────────────┬──────────────┘
                        ▼
                  core/ (Domain)
     ├── PlatformProfile (Detection authority)
     ├── ProductCatalog (Navigation & capability contracts)
     ├── ActionCenterOrchestrator (Planning & mutation authority)
     └── Storage / State (Atomic persistence & Journal)
                        │
                        ▼
                services/ (Probes)
     ├── DNF5 / rpm-ostree / bootc adapters
     ├── Flatpak / fwupd inspection
     ├── Systemd / Journal / Health checks
     └── Hardware / Battery / ZRAM monitors
```

---

## 2. Layer Boundaries & Responsibilities

- **`ui/` (Presentation)**:
  Owns PyQt6 widgets, accessibility hints, theme styling, and responsive layout. UI code **never** directly invokes shell commands, package managers, or mutating file operations.
- **`cli/` (Command-Line Interface)**:
  Parses bounded CLI arguments and emits formatted human text or structured command-specific `--json` payloads. Completely decoupled from Qt; imports zero UI code.
- **`core/` (Domain Logic & Contracts)**:
  Owns business logic, `PlatformProfile` detection, the immutable `ProductCatalog`, Action Center planning, mutation lease locking, and independent verification.
- **`services/` (Probing & Adapters)**:
  Performs bounded, read-only system inspection across systemd, DNF5, ostree, Flatpak, and hardware sysfs nodes. Free of Qt dependencies.
- **`utils/` (Low-Level Primitives)**:
  File I/O helpers, safe subprocess execution wrappers, and JSON serialization.

---

## 3. PlatformProfile: The Detection Authority

`PlatformProfile` is the shared, immutable authority across both GUI and CLI. It queries and caches:
- Fedora version (`43`, `44`, `45-preview`, or `unknown`).
- Deployment backend (`dnf5`, `rpm_ostree`, `bootc`, or `unknown`).
- Desktop environment (`GNOME`, `KDE`, `XFCE`, `Sway`, `generic`).
- Display server (`wayland` or `x11`).

If an unrecognized backend or distribution is detected, `PlatformProfile` **fails closed**, disabling incompatible mutation workflows rather than assuming traditional Fedora defaults.

---

## 4. Single Mutation Authority

All persistent system modifications must be constructed as typed Action Center plans within `core.action_center`.
- UI buttons and CLI commands only stage plans.
- Mutation leases prevent concurrent write operations.
- Execution requires explicit user authorization via Polkit (`pkexec`).
- Verification is performed post-execution using an independent probe.
