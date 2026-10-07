# Product definition

**Loofi Fedora Tweaks is a control center for understanding and personalizing Fedora.**
Overview combines live resources, available hardware readings, and recorded
maintenance. Search, change, and verify desktop and system settings for GNOME,
KDE, and DNF alongside applications, updates, health, and verified history.

## Who it is for

- **Everyday Fedora users** who want a setting changed without opening a
  terminal. This is the default experience.
- **Power users** who want more controls in one place. Advanced tools are
  available behind an explicit switch, never in the way by default.

## The main destinations

| Job | What the user does |
|---|---|
| **Overview** (start page) | Read current resources and up to three relevant next steps, then open the appropriate tool |
| **Tweaks** | Search and change a setting, share a same-desktop profile, verify and restore supported values |
| **Apps** | Find and install trusted applications; inspect installed apps and remove an exact Flatpak installation |
| **Updates** | Update system packages, Flatpaks, and firmware; resume pending verification |
| **Health** | Start from a symptom, inspect evidence, apply one reviewed fix |

**Activity** is a primary destination for recorded changes, independent
verification, previous values, and action-specific recovery guidance.

## Advanced mode

The **Tools** disclosure shows **System**, **Storage**,
**Network**, **Security**, and **Logs**. Its expansion is saved using the existing
Show advanced tools preference. Nothing outside this list is added
without changing this document first.

## Principles

1. **Understand, then act.** Overview reports actual resource and maintenance
   observations; the task pages provide deliberate, reviewed actions.
2. **One catalog authority.** Canonical product records define available
   functionality; `core/navigation/routes.py` projects those records into
   control-center destinations and documented compatibility links.
3. **Plain language.** Everyday mode avoids jargon; technical detail is behind
   "Show details".
4. **Verified with clear recovery.** Every change is checked after it is
   applied. Where supported, a previous value can be restored from verified
   history; other actions explain their recovery guidance. Reset uses Loofi's
   curated standard value, which may differ from the desktop's current default.
5. **Safety boundary stays strict.** Commands are allow-listed; privileged work
   goes through the desktop authorization agent only when needed.
6. **Delete over hide.** Code without a user-facing entry point is removed, not
   kept dormant.

## Non-goals

Background monitoring while views are hidden, mesh/network sharing, AI features,
a plugin marketplace, and release-evidence screens in the user interface.

## Presentation system

[Design](../DESIGN.md) defines the Loofi palette, geometry, navigation, component
states, and qualification requirements for every reachable GUI surface.

## Everyday workflows

Profiles use [a separate portable format](TWEAK_PROFILES.md) and include supported
user settings only. Import approval binds the reviewed values and action definitions;
changes run sequentially through Action Center and stop on drift or verification failure.
Installed Flatpaks remain distinct by installation and full ref. Removal preserves
app data and requires successful independent inventory verification. RPM removal
opens the desktop software manager. Sound and Bluetooth checks report observations
without changing services, devices, volume, or connections.
