# Configuration & State Storage — v28.0.2 "Ease"

Loofi Fedora Tweaks strictly follows the [XDG Base Directory Specification](https://specifications.freedesktop.org/basedir-spec/basedir-spec-latest.html) to keep configuration, runtime state, and logs organized and separated from system files.

---

## 1. Directory Locations

All user state resides within your standard user directory:

| Path | Purpose | Content |
| --- | --- | --- |
| `~/.config/loofi-fedora-tweaks/` | Configuration | User preferences (theme, UI scale, window geometry) |
| `~/.local/share/loofi-fedora-tweaks/` | Application State | System check history, Trusted Change Journal, active plans |
| `~/.local/share/loofi-fedora-tweaks/logs/` | Runtime Logs | Application execution and diagnostic logs |
| `~/.cache/loofi-fedora-tweaks/` | Transient Cache | Temporary inspection caches |

Loofi never creates unmanaged files in `/etc`, `/var`, or your home root directory.

---

## 2. Preference Storage (`settings.json`)

User preferences are stored in JSON format with an explicit schema version:

```json
{
  "schema_version": 2,
  "appearance": {
    "theme": "system",
    "scale_factor": 1.0,
    "navigation_layout": "expanded"
  },
  "behavior": {
    "confirm_exit_with_active_plans": true,
    "default_timeout_seconds": 300
  }
}
```

### Safety & Migration Rules
- **Forward-Only Migration**: When upgrading Loofi versions, preferences are automatically migrated forward to the newest schema.
- **Future Schema Protection**: If an older version of Loofi opens a configuration created by a newer release, it loads in safe read-only mode to prevent deleting unrecognized settings.
- **Atomic Writes**: Preference files are written to a `.tmp` file and atomically renamed to prevent file corruption during sudden power losses.

---

## 3. Trusted Change Journal & State Persistence

The Trusted Change Journal records the complete lifecycle of reviewed system changes:
- Plan ID and creation timestamp.
- Action identifier and typed parameters.
- Preflight results and Polkit authorization timestamp.
- Subprocess output stream and exit code.
- Post-execution verification findings.

Past records are maintained with automatic rotation to ensure historical records do not grow without bound.

---

## 4. Environment Variables

The following environment variables can be used to control runtime behavior:

| Variable | Values | Purpose |
| --- | --- | --- |
| `QT_QPA_PLATFORM` | `wayland`, `xcb`, `offscreen` | Overrides Qt display server backend |
| `LOOFI_IPC_MODE` | `standard`, `disabled` | Set to `disabled` during headless CI testing |
| `XDG_CONFIG_HOME` | Absolute path | Custom location for user configuration files |
| `XDG_DATA_HOME` | Absolute path | Custom location for persistent application state |

---

## 5. Resetting Application State

To reset user preferences to fresh defaults without affecting system packages:

```bash
rm -rf ~/.config/loofi-fedora-tweaks/settings.json
```

To clean all historical check snapshots and journals:

```bash
rm -rf ~/.local/share/loofi-fedora-tweaks/
```

Resetting local state has **zero impact** on your installed Fedora packages or system configurations.

