# GUI Reference — v32.2.0 "Coherence"

Loofi Fedora Tweaks opens on **Overview**, unless reopening the last page is
enabled. Six primary destinations are always available. Selecting a destination
or search result navigates without applying a change.

```text
Header: [Search Ctrl+K]
Sidebar:
├── Overview   (default start page)
├── Tweaks
├── Apps
├── Updates
├── Health
├── Activity
├── Tools      (collapsed group)
│   ├── System
│   ├── Storage
│   ├── Network
│   ├── Security
│   └── Logs
└── Settings   (footer)
```

Expand **Tools** to inspect advanced pages. Existing advanced-tools preferences
are retained. Settings stays at the bottom of the sidebar.

## Overview

A read-only dashboard shows computer information, CPU, memory, GPU, storage,
network/disk activity, temperatures, battery, and recorded maintenance results.
Each reading identifies its source, time, and state. **Collecting**,
**Unavailable**, **Read failed**, and **Last known value** distinguish pending,
unsupported, failed, and old evidence. Missing readings are not zero values.

Measurements refresh every two seconds, sensors every five seconds, with up to
60 samples per graph. **Pause** retains the last values and **Resume** establishes
a fresh baseline. Collection pauses when neither Overview nor System Monitor
is visible or the window is hidden/minimized. Sleeping GPUs are not queried
automatically; the dashboard installs no tools or drivers.

## Tweaks

Tweaks lists 73 controls across GNOME, KDE Plasma, and shared system settings,
grouped by theme (Appearance, Desktop, Interaction, Privacy, Input, Windows,
Sound, Power, System & Packaging). The full list with Loofi standard values is generated in
[docs/TWEAKS.md](https://github.com/loofiboss-bit/loofi-fedora-tweaks/blob/master/docs/TWEAKS.md).

- Each row shows the current value read from the system. Changes are checked
  before and after they run.
- **Use Loofi standard value** applies the catalog's curated reference value;
  it does not necessarily match the installed desktop's own default.
- **Restore previous value** is offered when verified history can safely
  recover the immediately preceding value.
- **Changed** filters settings that differ from Loofi's curated reference value.
- A fresh check blocks restoration when the setting has drifted since the
  verified change.
- Search matches titles and descriptions.

![Tweaks](images/tweaks.png)

## Apps

A curated, searchable catalog with availability, source, and installation scope.
Selected apps remain in the fixed review summary while the catalog scrolls or
filters change. Flatpak is
preferred for GUI applications; RPM is used for trusted CLI and system tools.

![Apps](images/apps.png)

## Updates

System, Flatpak and Firmware are separate cards with one primary action each:
**Check**, **Update**, **Continue** or **Verify**.

![Updates](images/updates.png)

## Health

Health starts from a symptom and runs read-only diagnostics before offering one
supported operation or instruction. There is no **Fix all**.

![Health](images/health.png)

## Activity

Inspect **Needs you**, **In progress**, or **History**, then select a change for
its recorded before/after evidence, verification, and available recovery.
**Restore previous value** recovers eligible recorded evidence; **Use Loofi
standard value** applies the curated reference. Both use reviewed, verified
operations.

## Settings and accessibility

Settings is opened from the sidebar footer. **Follow system theme** uses Loofi
light or dark colors according to the desktop mode; explicit dark, light, and
high-contrast choices remain available. Search uses `Ctrl+K` and never executes
from the result list.

![Settings](images/settings.png)
