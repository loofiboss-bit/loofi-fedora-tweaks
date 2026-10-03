# Product definition

**Loofi Fedora Tweaks is the fastest way to make Fedora feel like your computer.**
Search, change, and undo desktop and system settings for GNOME, KDE, and DNF
from one place. Apps, updates, and health checks exist to support that job;
tweaks are the point.

## Who it is for

- **Everyday Fedora users** who want a setting changed without opening a
  terminal. This is the default experience.
- **Power users** who want more controls in one place. Advanced tools are
  available behind an explicit switch, never in the way by default.

## The four jobs

| Job | What the user does |
|---|---|
| **Tweaks** (start page) | Search and change a setting, see it verified, undo it |
| **Apps** | Find and install trusted applications |
| **Updates** | Update system packages, Flatpaks, and firmware |
| **Health** | Start from a symptom, inspect evidence, apply one reviewed fix |

A history panel (**History & Undo**) is reachable from anywhere.

## Advanced mode

Enabled in Settings (*Show advanced tools*). Adds **System**, **Storage**,
**Network**, **Security**, and **Logs**. Nothing outside this list is added
without changing this document first.

## Principles

1. **Tweaks first.** Every new feature must strengthen tweaks or justify why it
   belongs to one of the four jobs.
2. **One navigation model.** Routes are defined once in
   `core/navigation/routes.py`. No parallel catalogs.
3. **Plain language.** Everyday mode avoids jargon; technical detail is behind
   "Show details".
4. **Reversible and verified.** Every change is checked after it is applied and
   can be undone or reset to its default.
5. **Safety boundary stays strict.** Commands are allow-listed; privileged work
   goes through the desktop authorization agent only when needed.
6. **Delete over hide.** Code without a user-facing entry point is removed, not
   kept dormant.

## Non-goals

System monitoring as a headline feature, mesh/network sharing, AI features,
a plugin marketplace, and release-evidence screens in the user interface.
