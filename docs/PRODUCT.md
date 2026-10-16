# Product definition

**Loofi Fedora Tweaks is a control center for understanding and personalizing Fedora.**
Overview leads with CPU, memory, GPU, and storage, then shows network, disk
activity, available hardware readings, compact maintenance status, and relevant
next steps. Introductory content and guides follow the system overview. Search,
change, and verify desktop and system settings for GNOME,
KDE, and DNF alongside applications, updates, health, and verified history.

Voluntary Overview guides help users understand four everyday jobs: personalizing
the desktop, choosing and managing apps, maintaining the system, and solving a
problem. They route into existing pages and reviews. Guide progress is local
presentation state; reviewing or completing a guide never establishes that the
computer is healthy.

## Who it is for

- **Everyday Fedora users** who want a setting changed without opening a
  terminal. This is the default experience.
- **Power users** who want more controls in one place. Advanced tools are
  available behind an explicit switch, never in the way by default.

## The main destinations

| Job | What the user does |
|---|---|
| **Overview** (start page) | Read current resources and up to three relevant next steps, open the appropriate tool, or choose an optional everyday guide |
| **Tweaks** | Use Settings for direct per-user or reviewed computer-wide settings; use Profiles to edit and save a copy, compare profiles, or review a saved profile |
| **Apps** | Use Catalog to select and install trusted applications, Installed to inspect or remove an exact installation, and Sources to inspect configured package sources |
| **Updates** | Update system packages, Flatpaks, and firmware; resume pending verification |
| **Health** | Start from a symptom, inspect evidence, apply one reviewed fix |

**Activity** is a primary destination for recorded changes, independent
verification, previous values, and action-specific recovery guidance.

Global search includes the currently supported GNOME or KDE settings from the
canonical tweak catalog. Selecting a setting opens Tweaks > Settings, reveals
its row, and focuses the control or its availability explanation; search never
changes a value. A profile-library result opens Tweaks > Profiles. Apps keeps
catalog and installed-inventory searches within their respective subviews.
Installed results retain separate user, system, and named Flatpak installations
even when their application names match. The selected-app view ignores catalog
filters until the user returns to the previous search and category.

On first opening Activity, Loofi asynchronously reads up to 25 recent local
Loofi runs. Other recorded sources refresh only when the user asks. A link to a
specific operation looks up that exact run, including runs outside the recent
page; when the record is missing, Activity says so instead of selecting a
different run. Health places its read-only check beside the chosen symptom and
offers a deliberate recheck after the user returns from desktop settings.

Health and global search share closed symptom entries for application launch,
network, battery and power, displays and docking, input devices, printers, and
the existing maintenance checks. Navigation only selects a symptom. The user
starts each bounded read-only collection explicitly. Failed, cancelled, missing,
and partial observations retain their own state; none is interpreted as a
healthy result.

Guide steps can be reviewed, skipped, or linked to one exact saved successful
operation or completed diagnostic session where the step allows it. Missing
evidence stays missing. Returning to a guide does not run checks, apply changes,
install packages, or bypass the owning page's current review.

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

The v34.0.1 Accord candidate adds installation-bound Flatpak updates. Apps can
explicitly check one selected installed Flatpak; Updates supports individual or
multiple selection within an installation. Shared review explains selected
apps, origin, versions, scope, and resolved runtime/extension operations.
Approval binds the complete operation set and commits. Changes require fresh
review; execution never silently adds remotes, rebases, or removes applications.

Independent readback reports each reviewed ref in the same installation,
including partial completion and unavailable observations. Real run IDs link to
Activity. A separate navigation link opens existing unused-runtime maintenance
for the affected installation without checking or cleaning automatically.
Missing optional libflatpak support is unavailable. New RPM maintenance,
background update checks, and automatic cleanup are outside this release.

Profiles use [a separate portable format](TWEAK_PROFILES.md) and include supported
user settings only. Import approval binds the reviewed values and action definitions;
changes run sequentially through Action Center and stop on drift or verification failure.
Built-in Reduced motion and File navigation presets use the same immutable review,
explicit selection, and per-setting verification. A focused setting check updates
only that row and preserves the rest of the visible snapshot.
The KDE-only Folder workspace preset uses the same review to set Dolphin to
reopen folders and tabs, open external folders in a new tab, and confirm before
closing multiple tabs. Health's input guidance links separately to verified KDE
mouse and touchpad modules and can focus the existing tap-to-click tweak.
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

Application-start troubleshooting binds one exact RPM package or Flatpak ref to
its selected installation. It reports installation inventory separately from
recent journal counts. The log query runs only after the user confirms a launch
attempt, returns bounded counts rather than raw messages, and never starts an
application. Network troubleshooting reports active link, IPv4/IPv6 default
routes, resolver configuration, and NetworkManager's own connectivity status
separately. It sends no external probe traffic.

Battery and power, display/docking, input, and printer checks report only fields
available from bounded local sources. KScreen's unknown values remain unknown.
Input guidance reads detected device metadata and the observed KDE touchpad
setting without recording input events. Printer guidance reports CUPS service,
queue state, and the current user's pending-job count; it stores no document
names or printer addresses, and never sends a test print or changes a queue.
Native settings handoffs check the requested KDE module before opening it.

## Companion personal workflows

Companion prioritizes KDE on traditional Fedora with DNF5. GNOME provides
corresponding controls where supported; physical GNOME qualification is tracked
separately. Atomic retains explicitly limited observations and manual guidance.

Tweaks includes a local library of built-in and personal profiles. Focus,
Privacy basics, and Touchpad comfort use existing supported controls. Personal
profiles preserve the portable `loofi.tweak-profile/v1` format and can be
imported, exported, and removed locally. Built-in entries are read-only.
Review compares supported values on the same desktop before the user selects
changes; existing Action Center authority, drift checks, and verification apply.

Apps separates declared Flatpak metadata from global and application overrides
for the selected installation and current user. Overrides identify an app ID,
not one branch. Explanations do not claim effective runtime access: portals and
launch arguments are additional factors. Environment values and private paths
are masked. Permission changes are handed to installed native tools, with
manual guidance when unavailable.

Health can compare compatible saved symptom sessions without collecting again.
Unavailable follow-up sources remain not comparable, never resolved. Screen
sharing diagnostics inspect the session, user services, and advertised portal
support without capturing the screen or restarting services. Advertised support
is not proof that sharing works in a particular application.

Preparing a support question uses one explicitly selected saved session,
problem description, and reproduction steps. A redacted, editable preview can
be exported locally as Markdown or a ZIP. Export does not collect new evidence
or post to a website; edited text is masked again before saving.

Updates offers local preparation for a manual Fedora version upgrade. Release
policy, package database observations, source configuration, free space, and
available DNF restart hints retain their own availability and timestamps.
Backup checklist selections are user confirmations, not verified backups.
Local observations do not certify the future release's transaction, source
availability, or sufficient disk space. Missing or malformed restart advice
remains unknown. Loofi does not download, perform, or reboot for a major upgrade.
The target, observation date and state, detected third-party source IDs, and
dated backup confirmations persist locally. Observations become stale when the
target changes, the saved timestamp is in the future, or more than seven days
have passed; backup confirmations remain user attestations across rechecks.

## Personal everyday workflows

Apps includes visible RPM-owned desktop applications outside the curated
catalog. Several launchers and installed architectures of one RPM package
share one row. RPM is an installation format, not a promise about package
origin or trust; recommended catalog entries retain their explicit curation.
Removal stays in the native software manager. Partial reads remain visible.

Profile library entries can be edited as copies: change the name, inclusion,
and supported target values, then choose **Save copy** or **Save and review…**.
Saving selects the persisted copy and does not change computer settings.
Review inspects that exact saved profile with fresh current values; save errors
or cancelled inspections never start review or application. Drafts survive
Settings/Profiles navigation, and leaving the editor for another profile offers
Save, Discard, or Cancel. Original unknown or unavailable values remain until
deliberately removed.

Setting rows distinguish **Applies immediately · This user** from
**Review required · This computer** before interaction. Requested values,
verified readback, and any session activation result are shown on that setting.
Profile results use understandable setting names and provide a separate
Activity link only for each actual recorded run.

Apps keeps Catalog selection while search and category filters change. **Show
selected** reveals the complete selection regardless of those filters;
individual items can be removed or the selection cleared. The shared final
review names each application, source, package identifier, and installation
scope. Partial failures retain the selection and report each application's
result independently.

The Package sources view in Apps searches configured DNF5 source IDs, names,
and enabled/disabled state with an observation time. Updates links to that
view. It does not refresh metadata, assess remote availability, or change
repository configuration. Unsupported backends and failed reads stay unknown.

Three additional KDE controls manage placement of new windows and snap
distances to screen borders and other windows. Saved-value readback and KWin
session activation retain separate results. Default applications in Apps and
autostart/icon settings in Tweaks use checked native KDE handoffs.

## Routine application and maintenance workflows

Apps can compare captured installations of the same Flatpak ID and explicit RPM
counterparts for six catalog applications. Each installation, architecture and
branch stays separate. Similar names never establish equivalence, and comparison
does not recommend uninstalling an application or predict recovered disk space.

Health's storage guide shows root, home and var measurements, grouped where they
share a device, together with available DNF cache and journal sizes. Failed or
partial reads are unknown. Mount observations also include free inodes, read-only
state, and a separate `/boot` measurement where applicable. DNF cleanup requires its existing Action Center review;
Flatpak runtime inspection opens Apps with the chosen user/system installation.
Named installations remain available in Apps. Journal cleanup remains manual
guidance. Check again starts a new explicit storage-symptom session.

Updates offers a manual local DNF5 restart recommendation with timestamp and
reported packages. The observation stays in this application session, becomes
stale after the existing freshness interval, and never restarts the computer.
An unsupported backend, missing tool or inconsistent response remains unknown.
Overview's suggestions select exact saved operations, update sources or the
storage symptom without running checks on navigation.

Troubleshooting sessions are versioned against the source contract that created
them. Older saved app and network sessions remain readable with their original
profile version; comparisons across incompatible source contracts are marked
not comparable. Session export masks data before local support-bundle creation.

The profile library compares two saved profiles for the same desktop, showing
added, removed, changed and unchanged target values. It never reads live computer
settings. Unknown values remain exact. Editing a copy and applying through a
fresh existing review are separate actions; the portable profile format is unchanged.

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

### Companion KDE appearance extension

The shared catalog includes installed pointer themes, requested pointer sizes
and installed Plasma styles. KDE Wayland pointer changes independently verify
both keys, preserving the value that was not selected. Source-bound pointer
notification delivery remains separate from saved verification and visual
effect. Native Cursor Settings is the explicit alternative on KDE X11.
Profiles retain independent setting commands and existing review/restore
authority; failed notification stops the profile without undoing saved changes.
