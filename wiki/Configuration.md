# Configuration

Configuration files, themes, and customization options for Loofi Fedora Tweaks.

---

## State integrity and recovery

v13 centralizes application state under the XDG config, data, cache, and runtime roots. v14 binds restore plans to the archive digest and the current target baseline, expires them after 30 minutes, and rolls back already changed domains if a later domain fails. Open **Settings → State & Recovery** to run the read-only State Doctor, create a privacy-safe backup, preview a restore plan, or inspect collector freshness. Backups exclude registered secret domains and restore always requires a generated plan before apply.

The equivalent CLI entry points are `state doctor`, `state backup`, `state restore plan`, and `state restore apply`.

## Configuration Directory

All user configuration is stored in:

```
~/.config/loofi-fedora-tweaks/
```

**Files:**

| File | Purpose |
|------|---------|
| `settings.json` | Application settings (theme, language, auto-update) |
| `favorites.json` | Favorite tabs (sidebar quick access) |
| `quick_actions.json` | Dashboard quick action buttons |
| `audit.jsonl` | Audit log of privileged actions (JSONL format) |
| `history.json` | Action history with undo commands (max 50) |
| `profile.json` | User profile from first-run wizard |
| `profiles/` | Saved user profiles (work, gaming, etc.) |
| `../share/loofi-fedora-tweaks/action_plans.json` | At most 50 Action Center plans |
| `../share/loofi-fedora-tweaks/action_runs.jsonl` | At most 100 Action Center run records |

Action plans persist validated parameters, policy facts, digest, preview, and
expiry. Commands are regenerated from the audited action definition during
both preview and apply. A persisted `running` record is marked `interrupted`
after restart and is never retried automatically. A `verifying` record is
preserved so the user can explicitly run verification after restart; it is
never verified or resumed automatically.

---

## Configuration Files

### `settings.json`

Application-wide settings:

```json
{
  "theme": "dark",
  "language": "en_US",
  "auto_update_check": true,
  "notification_level": "normal",
  "enable_telemetry": false,
  "developer_mode": false,
  "sidebar_collapsed": false,
  "monitor_refresh_rate": 1000,
  "confirm_dangerous_actions": true,
  "create_snapshot_before_risky": true
}
```

**Key settings:**
- `theme`: `"system"`, `"dark"`, `"light"`, or `"highcontrast"`
- `language`: Locale code (currently only `en_US`)
- `auto_update_check`: Check for app updates on startup
- `notification_level`: `"minimal"`, `"normal"`, or `"verbose"`
- `enable_telemetry`: Always `false` (no telemetry implemented)
- `developer_mode`: Enable debug logging and experimental features
- `sidebar_collapsed`: Start with sidebar collapsed
- `monitor_refresh_rate`: System monitor refresh interval (ms)
- `confirm_dangerous_actions`: Show confirmation dialogs for risky operations
- `create_snapshot_before_risky`: Prompt for snapshot before dangerous actions

### `favorites.json`

Favorite tabs for quick access in sidebar:

```json
{
  "favorites": [
    "dashboard",
    "maintenance",
    "software",
    "network",
    "security"
  ]
}
```

**Add favorites:**
- GUI: Right-click any tab → "Add to Favorites"
- Manual: Edit `favorites.json` and add tab ID

### `quick_actions.json`

Dashboard quick action buttons:

```json
{
  "actions": [
    {
      "id": "update",
      "label": "Check Updates",
      "icon": "🔄",
      "target_tab": "maintenance"
    },
    {
      "id": "cleanup",
      "label": "Clean Up",
      "icon": "🧹",
      "target_tab": "maintenance"
    }
  ]
}
```

**Customize:**
- GUI: Dashboard → Right-click quick action → "Edit" or "Remove"
- Manual: Edit `quick_actions.json`

### `audit.jsonl`

Structured audit log (JSON Lines format):

```jsonl
{"timestamp": "2026-02-14T10:30:15.123456", "action": "package.install", "params": {"packages": ["firefox"]}, "exit_code": 0, "stderr_hash": "sha256:abc...", "dry_run": false}
{"timestamp": "2026-02-14T10:35:22.789012", "action": "firewall.add_port", "params": {"port": "8080", "protocol": "tcp"}, "exit_code": 0, "stderr_hash": "sha256:def...", "dry_run": false}
```

**Features:**
- Auto-rotates at 10 MB (keeps 5 backups)
- Sensitive params redacted (passwords, tokens)
- stderr hashed for privacy
- View via CLI: `loofi-fedora-tweaks --cli audit-log --count 20`

### `history.json`

Action history with undo commands:

```json
{
  "history": [
    {
      "timestamp": "2026-02-14T10:30:15",
      "action": "delete_snapshots",
      "description": "Deleted 3 snapshots",
      "undo_commands": [
        ["restore_snapshot", ["--id", "123"], "Restore snapshot 123"]
      ]
    }
  ]
}
```

**Max entries**: 50 (older entries are removed)

**Undo:**
- GUI: Click undo button in status bar
- CLI: Not currently supported

### `profile.json`

User profile from first-run wizard:

```json
{
  "hardware_profile": "hp-elitebook",
  "package_manager": "dnf",
  "desktop_environment": "gnome",
  "backup_tool": "timeshift",
  "first_run_complete": true,
  "created_at": "2026-02-14T09:00:00"
}
```

**Delete to re-run wizard**: `rm ~/.config/loofi-fedora-tweaks/profile.json`

---

## Themes

### Available Themes

| Theme | Description | Palette |
|-------|-------------|---------|
| **System** | Follows the active Qt/KDE palette | Derived from `QPalette` with contrast guards |
| **Abyss Dark** | Default dark theme | Dark surfaces with a restrained blue accent |
| **Abyss Light** | Light theme | Light surfaces with a deep blue accent |
| **High Contrast** | Explicit high-contrast theme | Black, white, yellow, and semantic status colors |

### Theme Structure

All themes use one structural QSS template. The application injects a semantic
palette for the selected theme at runtime:

**System-wide** (installed via RPM):
```
/usr/share/loofi-fedora-tweaks/assets/base.qss
```

**Source tree**:
```
loofi-fedora-tweaks/assets/base.qss
```

### Switch Theme

**GUI**: Settings tab → Appearance → Theme dropdown

**Manual**:
```bash
# Edit settings
nano ~/.config/loofi-fedora-tweaks/settings.json

# Change theme field
{
  "theme": "system"
}
```

Restart app to apply.

---

## QSS Styling Rules

`base.qss` owns component structure. Theme colors come from semantic roles in
`ui/design/theme_manager.py`, so adding a maintained palette requires code and
contrast-test updates rather than copying the structural stylesheet. Arbitrary
custom QSS loading is not a supported configuration contract.

### Common Selectors

**Sidebar:**
```css
QTreeWidget#sidebar {
    background-color: $color_surface;
    color: $color_text_muted;
}

QTreeWidget#sidebar::item:selected {
    background-color: $color_selected;
    color: $color_accent;
}
```

**Buttons:**
```css
QPushButton {
    background-color: $color_surface_raised;
    color: $color_text;
    border-radius: $radius_control;
    padding: $space_2 $space_4;
}

QPushButton:hover {
    background-color: $color_hover;
}
```

**Cards:**
```css
QFrame[routeCard="true"] {
    background-color: $color_surface;
    border-radius: $radius_card;
    padding: $space_4;
}
```

**Tables:**
```css
QTableWidget::item {
    color: $color_text;
    padding: $space_2;
}

QTableWidget::item:alternate {
    background-color: $color_surface_raised;
}

QTableWidget::item:selected {
    background-color: $color_selected;
    color: $color_text;
}
```

### objectName Targeting

Many widgets use `setObjectName()` for precise styling:

```python
# In Python code
button.setObjectName("dangerAction")
```

```css
/* In QSS */
QPushButton[objectName="dangerAction"] {
    background-color: $color_error_surface;
    color: $color_error_text;
}
```

---

## App Catalog

The application catalog (`config/apps.json`) defines GUI applications in the Software tab.

**System-wide**: `/usr/share/loofi-fedora-tweaks/config/apps.json`

**Source tree**: `loofi-fedora-tweaks/config/apps.json`

### Format

```json
{
  "apps": [
    {
      "name": "Firefox",
      "desc": "Mozilla Firefox Web Browser",
      "cmd": "firefox",
      "args": [],
      "check_cmd": "firefox --version",
      "icon": "🦊",
      "category": "Internet"
    }
  ]
}
```

**Fields:**
- `name`: Display name
- `desc`: Brief description
- `cmd`: Command to launch (also package name for install)
- `args`: Command-line arguments (usually empty)
- `check_cmd`: Command to check if installed
- `icon`: Emoji icon
- `category`: Category for grouping

### Remote Catalog

The app catalog can be fetched remotely via `utils/remote_config.py`:

**Fallback order:**
1. Remote CDN URL (if configured)
2. Local system file (`/usr/share/loofi-fedora-tweaks/config/apps.json`)
3. Source tree file (`config/apps.json`)

**Update interval**: Daily (cached)

---

## Polkit Policies

Polkit policy files define privileged actions.

**System-wide**: `/usr/share/polkit-1/actions/`

**Files:**
- `org.loofi.fedora-tweaks.package.policy`
- `org.loofi.fedora-tweaks.firewall.policy`
- `org.loofi.fedora-tweaks.network.policy`
- `org.loofi.fedora-tweaks.storage.policy`
- `org.loofi.fedora-tweaks.service-manage.policy`
- `org.loofi.fedora-tweaks.kernel.policy`
- `org.loofi.fedora-tweaks.security.policy`

**Edit policies** (advanced):

```bash
sudo nano /usr/share/polkit-1/actions/org.loofi.fedora-tweaks.package.policy
```

**Reload polkit** after editing:

```bash
sudo systemctl restart polkit
```

See: [Security Model](Security-Model) for details.

---

## Shell Completions

Bash and Zsh completions for CLI commands.

**System-wide**: `/usr/share/bash-completion/completions/loofi-fedora-tweaks`

**Enable**:

```bash
# Bash (automatic after RPM install)
# No action needed

# Zsh
# Add to ~/.zshrc:
autoload -U compinit && compinit
```

**Test**:

```bash
loofi-fedora-tweaks --cli <TAB>
# Shows: info, health, doctor, cleanup, ...
```

---

## Logs

Application logs are stored in:

```
~/.local/share/loofi-fedora-tweaks/
```

**Files:**

| File | Purpose |
|------|---------|
| `startup.log` | Application startup log |
| `plugins.log` | Plugin loading and execution log |

**View logs:**

```bash
# Startup log
tail -f ~/.local/share/loofi-fedora-tweaks/startup.log

# Plugin log
tail -f ~/.local/share/loofi-fedora-tweaks/plugins.log
```

**Rotate logs**: Logs auto-rotate at 5 MB (3 backups kept).

---

## Environment Variables

### `PYTHONPATH`

Required when running from source:

```bash
PYTHONPATH=loofi-fedora-tweaks python3 loofi-fedora-tweaks/main.py
```

### `QT_QPA_PLATFORM`

Force Qt platform plugin:

```bash
# Force X11
QT_QPA_PLATFORM=xcb loofi-fedora-tweaks

# Force Wayland
QT_QPA_PLATFORM=wayland loofi-fedora-tweaks
```

### `LOOFI_DEBUG`

Enable debug logging:

```bash
LOOFI_DEBUG=1 loofi-fedora-tweaks
```

---

## Backup & Restore

### Backup Configuration

```bash
# Backup all config
tar -czf loofi-backup.tar.gz ~/.config/loofi-fedora-tweaks/

# Backup specific files
cp ~/.config/loofi-fedora-tweaks/settings.json ~/settings-backup.json
```

### Restore Configuration

```bash
# Restore all config
tar -xzf loofi-backup.tar.gz -C ~/

# Restore specific files
cp ~/settings-backup.json ~/.config/loofi-fedora-tweaks/settings.json
```

---

## Next Steps

- [Getting Started](Getting-Started) — Configure after installation
- [Troubleshooting](Troubleshooting) — Config file issues
- [Contributing](Contributing) — Contribute themes or presets
