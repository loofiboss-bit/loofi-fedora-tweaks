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
| **Tweaks** | Search and change a setting, review a desktop preset or same-desktop profile, check one current value, and restore supported values |
| **Apps** | Find and install trusted applications; inspect installed apps and their Flatpak metadata permissions; remove an exact installation |
| **Updates** | Update system packages, Flatpaks, and firmware; resume pending verification |
| **Health** | Start from a symptom, inspect evidence, apply one reviewed fix |

**Activity** is a primary destination for recorded changes, independent
verification, previous values, and action-specific recovery guidance.

Global search includes the currently supported GNOME or KDE settings from the
canonical tweak catalog. Selecting a setting opens Tweaks, reveals its row, and
focuses the control or its availability explanation; search never changes a
value. Apps keeps one search field for both the catalog and the already-read
Installed inventory. Installed results retain separate user, system, and named
Flatpak installations even when their application names match.

On first opening Activity, Loofi asynchronously reads up to 25 recent local
Loofi runs. Other recorded sources refresh only when the user asks. A link to a
specific operation looks up that exact run, including runs outside the recent
page; when the record is missing, Activity says so instead of selecting a
different run. Health places its read-only check beside the chosen symptom and
offers a deliberate recheck after the user returns from desktop settings.

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
Built-in Reduced motion and File navigation presets use the same immutable review,
explicit selection, and per-setting verification. A focused setting check updates
only that row and preserves the rest of the visible snapshot.
Installed Flatpaks remain distinct by installation and full ref. Removal preserves
app data and requires successful independent inventory verification. RPM removal
opens the desktop software manager. Sound and Bluetooth checks report observations
without changing services, devices, volume, or connections.
Flatpak permission inspection reports app metadata for one exact installation; it
does not claim to include portal grants or user overrides.

### Care application and maintenance workflows

Installed application filters and sorting use the captured inventory. App details
bind origin, runtime, logical installed size, and locally recorded end-of-life
warnings to the exact ref and installation. No recorded warning is not a support
guarantee. A missing optional libflatpak capability stays unavailable.

Unused-runtime inspection and removal target one explicit Flatpak installation.
The selected set, installed commits, and pinning are rechecked after review;
drift requires a new review. Only approved uninstall operations may run. The
remaining inventory is independently verified and app data is preserved.
System and named installations are shared; Loofi does not inspect other users'
private inventories or promise that runtime removal cannot affect them. Reported
ref sizes do not promise recovered disk space. Recovery is manual reinstallation,
without an automatic rollback.

Failed update sources link to source-specific Health diagnostics and the exact
recorded operation. Opening Health does not start a check. An explicit diagnostic
run collects bounded read-only observations and offers a relevant next step.
GUI and CLI update discovery share source statuses; unavailable evidence cannot
become an up-to-date result.

## Preferences and status

The Loofi release check is off by default and can be enabled in Settings. When
enabled, it runs once after the initial window appears, checks only the Loofi
version with a bounded timeout, and never downloads or installs an update. The
result appears in the app; a desktop notification is sent only when Loofi
notifications are enabled. Offline or cached results are labeled. Start
minimized hides the window only when the system tray is available; otherwise
the window stays visible and explains why. The notification preference gates
all Loofi notifications. Log level changes apply immediately after they are
saved; other preference feedback says when a restart is needed.

Security presents a bounded assessment of the observed listening ports and
firewall state. An incomplete or failed observation is unknown and cannot be
shown as zero ports or as a numeric score. Update review shows up to 100
observed candidates per source, their reported old and new versions, the check
time, and any omitted or retained candidates. A reviewed candidate list is an
observation; the eventual package transaction can differ.
