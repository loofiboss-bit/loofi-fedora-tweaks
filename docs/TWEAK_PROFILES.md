# Portable tweak profiles

Use **Tweaks → Save current settings…** to read and select supported user settings.
Use **Load profile…** to review current and desired values, select changes, and
explicitly approve their application. Profiles transfer between supported Fedora
GNOME desktops or between supported Fedora KDE Plasma desktops. System-wide
settings, unavailable settings, and custom values outside the current choices
are omitted from export with an explanation.

## File format

Profiles are user-selected UTF-8 JSON files, limited to 64 KiB and 128 settings.
The format is closed: duplicate keys or identifiers, extra fields, malformed
values, and unknown schema versions are rejected. Unknown setting identifiers
remain visible in the import review but cannot be applied.

```json
{
  "schema": "loofi.tweak-profile/v1",
  "name": "My GNOME settings",
  "desktop": "gnome",
  "settings": [
    {"id": "gnome-mouse-left-handed", "value": "true"},
    {"id": "gnome-keyboard-repeat", "value": "false"}
  ]
}
```

Values use the stable setting identifiers and string literals in the
[Tweak catalog](TWEAKS.md). Export includes only current supported choices.
Profiles contain no commands, credentials, or restoration history.

## CLI

```bash
loofi-fedora-tweaks --cli tweaks profile export settings.json --name 'My settings'
loofi-fedora-tweaks --cli tweaks profile export input.json --ids gnome-mouse-left-handed gnome-keyboard-repeat
loofi-fedora-tweaks --cli tweaks profile preview settings.json --json
loofi-fedora-tweaks --cli tweaks profile apply settings.json
loofi-fedora-tweaks --cli tweaks profile apply settings.json --yes
```

Without `--yes`, apply prints a fresh review and does not change settings.
With `--yes`, apply creates and confirms a fresh local review; it does not reuse
a previous CLI preview. Optional `--ids` limits apply to available changed rows.
JSON review and result output use the same domain data as the GUI.

## Verification and recovery

The immutable local review expires after 30 minutes. Only one Action Center
plan is prepared at a time, immediately before its selected change. The
current value, requested value, action metadata, and exact command must still
match the approved review. The existing controller revalidates again at
confirmation. Identical values are skipped.

Each change is independently read back before the next begins. Drift,
cancellation, execution failure, or failed verification stops remaining
changes. Completed changes remain recorded in **Activity**, and **Restore
previous value** uses that local verified history. KDE window settings also
verify application in the active Plasma session; a failure there preserves
the verified saved setting and stops remaining changes with a clear message.
Cancellation waits for the current operation and verification to finish.

## KDE appearance entries

Profiles can include `kde-cursor-theme`, `kde-cursor-size` and
`kde-plasma-style` without changing the portable format. Themes must be
installed on the destination. Pointer controls require KDE Wayland; theme and
size can appear in either order and preserve each other's current saved value.
After each verified pointer write Loofi sends a separately recorded notification.
Notification failure stops remaining profile changes, while the original saved
change remains verified and available for eligible restoration in Activity.
Notification success does not qualify visual effect in the running desktop.
