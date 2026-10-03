# GUI Reference — v32.0.0 "Refocus"

Loofi Fedora Tweaks opens on **Tweaks**. Four everyday jobs live in the sidebar;
selecting a destination or search result only navigates, and any change starts
from a reviewable task on its owning page.

```text
Sidebar: [Search Ctrl+K]
├── Tweaks   (start page)
├── Apps
├── Updates
└── Health
Header: [Activity & Recovery] [Settings]
```

Advanced pages (System, Storage, Network, Security, Logs) appear only after you
turn on **Show advanced tools** in Settings.

## Tweaks

Tweaks lists 61 declarative controls for GNOME and KDE Plasma, grouped by theme
(Appearance, Desktop, Interaction, Privacy, Input, Windows, Sound, Power, System
& Packaging). The full list with defaults is generated in
[docs/TWEAKS.md](https://github.com/loofiboss-bit/loofi-fedora-tweaks/blob/master/docs/TWEAKS.md).

- Each row shows the current value read from the system. Changes are checked
  before and after they run.
- **Reset to default** appears on a row whose value differs from its default.
- **Changed from default** filters the page to those rows.
- **Restore previous value** reverts the latest verified change. A fresh check
  blocks restores when the setting has drifted since.
- Search matches titles and descriptions.

![Tweaks](images/tweaks.png)

## Apps

A curated, searchable catalog with installed state and source labels. Flatpak is
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

## Settings and accessibility

Settings is opened from the header and holds the **Show advanced tools** switch.
Search uses `Ctrl+K` and never executes from the result list.

![Settings](images/settings.png)
