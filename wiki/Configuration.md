# Configuration & State Storage — v28.0.2 "Ease"

Loofi Fedora Tweaks keeps application state under the [XDG Base Directory Specification](https://specifications.freedesktop.org/basedir-spec/basedir-spec-latest.html) paths where the current state services apply them. Some legacy preference helpers still use the default home-relative configuration path; the exact scope is documented below.

---

## 1. Directory Locations

The following are the default locations; XDG overrides apply to the state services described in the environment table:

| Path | Purpose | Content |
| --- | --- | --- |
| `~/.config/loofi-fedora-tweaks/` | Configuration | User preferences, onboarding, and configuration-owned state |
| `~/.local/share/loofi-fedora-tweaks/` | Application State | System check history, Trusted Change Journal, active plans |
| `~/.local/share/loofi-fedora-tweaks/startup.log` | Startup Log | GUI startup and early crash diagnostics |
| `${XDG_STATE_HOME:-~/.local/state}/loofi-fedora-tweaks/app.log` | Runtime Log | Centralized application execution and diagnostic logs |
| `~/.cache/loofi-fedora-tweaks/` | Transient Cache | Temporary inspection caches |

Loofi never creates unmanaged system files in `/etc` or `/var`. A support bundle is an explicit user-requested archive and is written to your home directory by default.

---

## 2. Preference Storage (`settings.json`)

User preferences are stored as a flat JSON object with an explicit state schema version. The following is a representative persisted payload; values vary with the user's choices:

```json
{
  "theme": "dark",
  "follow_system_theme": true,
  "start_minimized": false,
  "show_notifications": true,
  "confirm_dangerous_actions": true,
  "restore_last_tab": false,
  "last_tab_index": 0,
  "log_level": "INFO",
  "check_updates_on_start": true,
  "navigation_mode": "standard",
  "suppressed_confirmations": [],
  "locale": "en",
  "favorite_routes": [],
  "hidden_routes": [],
  "last_route_id": "atlas_dashboard",
  "window_geometry": {},
  "last_seen_version": "0.0.0",
  "state_schema_version": 2
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
| `XDG_CONFIG_HOME` | Absolute path | Custom location for core state configuration; legacy preference helpers retain `~/.config/loofi-fedora-tweaks/` |
| `XDG_DATA_HOME` | Absolute path | Custom location for core persistent application state |
| `XDG_STATE_HOME` | Absolute path | Custom location for the centralized application log |

---

## 5. Resetting Application State

To reset user preferences to fresh defaults without affecting system packages:

```bash
rm -f ~/.config/loofi-fedora-tweaks/settings.json
```

To remove historical snapshots and journal records only, close Loofi first and delete the specific history files:

```bash
rm -f ~/.local/share/loofi-fedora-tweaks/health_timeline_v12.json
rm -f ~/.local/share/loofi-fedora-tweaks/health_timeline.db
rm -f ~/.local/share/loofi-fedora-tweaks/action_center_history.jsonl
rm -f ~/.local/share/loofi-fedora-tweaks/action_log.jsonl
```

Do not delete the entire application data directory: it also contains active plans, action runs, recovery state, and other inventory-managed domains. Substitute the corresponding `XDG_DATA_HOME` path when using a custom data root.

Resetting local state has **zero impact** on your installed Fedora packages or system configurations.
