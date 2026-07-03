# ARCHITECTURE.md — Loofi Fedora Tweaks

> **Canonical architecture reference.** All agent and instruction files MUST reference this document
> instead of duplicating architecture details. This file is updated when structure changes.
>
> **Version**: 11.0.0 "Lighthouse" | **Python**: 3.12+ | **Framework**: PyQt6 | **Platform**: Fedora KDE 44

## Project Structure

```text
loofi-fedora-tweaks/          # Application root (on PYTHONPATH)
├── main.py                   # Entry point — GUI (default), CLI (--cli), Daemon (--daemon)
├── version.py                # __version__, __version_codename__, __app_name__
├── core/                     # Business logic and system services [v4.0 Hub]
│   ├── diagnostics/          # Health & Repair Autopilot (HRA)
│   │   ├── health_registry.py# Central registry for system checks
│   │   ├── health_model.py   # Structured HealthCheck/HealthResult schemas
│   │   ├── release_readiness.py# Fedora KDE 44 release readiness aggregation
│   │   ├── readiness_actions.py# v7 safe action planning bridge
│   │   ├── fedora44_readiness.py# Compatibility facade
│   │   ├── upgrade_checker.py# Fedora version transition assistant
│   │   ├── task_dashboard.py # Goal-oriented task logic
│   │   └── gaming_audit.py   # Specialized hardware/gaming diagnostics
│   ├── executor/             # Action execution and safety
│   │   ├── action_model.py   # SystemAction with risk/rollback metadata
│   │   ├── action_executor.py# Centralized safe command runner
│   │   ├── command_facade.py # v9 command-vector preview/execute facade
│   │   └── command_policy.py # Shared executor/API command allowlist
│   ├── navigation/           # Route manifest, focused navigation areas, and route validation
│   ├── export/               # Diagnostic export services
│   │   ├── support_bundle_v5.py# Aegis support diagnostics and redaction
│   │   ├── support_bundle_v4.py# Compatibility wrapper
│   │   └── ansible_exporter.py # ANSIBLE export logic
│   ├── plugins/              # Plugin discovery and loading logic
│   ├── agents/               # AgentRegistry, AgentPlanner, AgentExecutor
│   └── ai/                   # AI logic and prompt templates
├── ui/                       # PyQt6 widgets — Feature tabs + base class
│   ├── base_tab.py           # BaseTab ABC — shared CommandRunner wiring
│   ├── atlas_dashboard_tab.py# v4.0 Home - Task-based entry point
│   ├── task_wizard.py        # v4.0 Guided 4-step repair lifecycle
│   ├── support_bundle_wizard.py# v4.0 Export UI
│   ├── main_window.py        # MainWindow with sidebar + lazy-loaded tab stack
│   ├── icon_pack.py          # Semantic icon resolver + theme-aware tinting
│   ├── lazy_widget.py        # Lazy tab loader
│   ├── wizard.py             # First-run wizard
│   └── ...                   # Feature tabs (maintenance, software, etc.)
├── utils/                    # Shared utilities
│   ├── commands.py           # PrivilegedCommand builder (pkexec)
│   ├── command_runner.py     # CommandRunner (QProcess async wrapper)
│   ├── system.py             # SystemManager (Atomic detection, etc.)
│   ├── experience_level.py   # Beginner/Intermediate/Advanced modes
│   └── ...
├── services/                 # Legacy/Niche domain services
├── cli/                      # CLI subcommands
├── config/                   # Apps and polkit policies
└── web/                      # Web dashboard logic
```

## Three Entry Modes


| Mode       | Flag       | Module                   | Purpose                                    |
| ---------- | ---------- | ------------------------ | ------------------------------------------ |
| **GUI**    | (default)  | `main.py` → `MainWindow` | PyQt6 desktop app with registry-loaded tabs |
| **CLI**    | `--cli`    | `cli/main.py`            | Subcommands with `--json` output           |
| **Daemon** | `--daemon` | `daemon/runtime.py`      | D-Bus daemon host + legacy fallback        |

## Layer Rules (STRICT)

| Layer        | Path          | Allowed                                             | Forbidden                     |
| ------------ | ------------- | --------------------------------------------------- | ----------------------------- |
| **UI**       | `ui/*_tab.py` | PyQt6 widgets, signals, BaseTab                     | `subprocess`, business logic  |
| **Services** | `services/*/` | Domain services (security, network, storage, etc.)  | `import PyQt6`, UI references |
| **Core**     | `core/*/`     | Domain modules (agents, ai, diagnostics, export)    | `import PyQt6`, UI references |
| **Utils**    | `utils/*.py`  | Shared ops, commands, errors; backward-compat shims | `import PyQt6`, UI references |
| **CLI**      | `cli/main.py` | Argument parsing, calls services/core/utils         | `import ui`, PyQt6            |

**Key rule**: `services/` and `core/` hold domain logic. `utils/` retains shared infrastructure (`commands.py`, `errors.py`, `operations.py`) and backward-compatible shims. GUI and CLI are consumers only.

### Explicit Qt Runtime Exceptions

Most `core/` and `services/` code must remain PyQt-free. The allowed PyQt imports are bridge modules that exist to host or type UI workers/plugins, plus one legacy service confirmation bridge kept for backward compatibility:

- `core/workers/base_worker.py`
- `core/workers/command_worker.py`
- `core/plugins/interface.py`
- `core/plugins/adapter.py`
- `services/security/safety.py` (`SafetyManager.confirm_action()` legacy UI confirmation bridge)

`tests/test_architecture_imports.py` enforces this allowlist. New domain logic must not add PyQt imports to `core/` or `services/`.

## Tab Layout And Routes

Built-in feature tabs are sourced from `core/plugins/loader.py` and `PluginRegistry`; release gates validate the live loader count instead of relying on prose counts. Route-level navigation is defined in `core/navigation/manifest.py`, where plugin routes and subroutes such as `maintenance:updates`, `software:apps`, and `system-monitor:processes` are stable IDs.

### Focused Navigation Areas

The route manifest keeps the stable plugin and subroute contract. `core/navigation/areas.py` groups those routes into the focused sidebar without importing PyQt.

| Order | Area               | Icon                   | Default role                              |
| ----- | ------------------ | ---------------------- | ----------------------------------------- |
| 1     | Home               | `home`                 | Launch page, task cards, readiness        |
| 2     | Software & Updates | `packages-software`    | Apps, repositories, updates, maintenance  |
| 3     | System & Hardware  | `hardware-performance` | System info, monitoring, hardware, disks  |
| 4     | Network & Security | `security-shield`      | Connectivity, privacy, firewall, backup   |
| 5     | Desktop & Settings | `appearance-theme`     | Desktop, app settings, profiles, tooling  |
| 6     | More               | `developer-tools`      | Advanced, automation, community, and logs |

| Route/plugin ID    | Tab                | File                     | Consolidates                             |
| ------------------ | ------------------ | ------------------------ | ---------------------------------------- |
| `atlas_dashboard`  | Home               | `atlas_dashboard_tab.py` | Task cards and guided entry              |
| `dashboard`        | Live Overview      | `dashboard_tab.py`       | Dashboard                                |
| `system_info`      | System Info        | `system_info_tab.py`     | System details                           |
| `monitor`          | System Monitor     | `monitor_tab.py`         | Performance + Processes                  |
| `maintenance`      | Maintenance        | `maintenance_tab.py`     | Updates + Cleanup + Overlays             |
| `hardware`         | Hardware           | `hardware_tab.py`        | Hardware + HP Tweaks + Bluetooth         |
| `software`         | Software           | `software_tab.py`        | Apps + Repos                             |
| `security`         | Security & Privacy | `security_tab.py`        | Security + Privacy                       |
| `network`          | Network            | `network_tab.py`         | Connections + DNS + Privacy + Monitoring |
| `gaming`           | Gaming             | `gaming_tab.py`          | Gaming setup                             |
| `desktop`          | Desktop            | `desktop_tab.py`         | Director + Theming                       |
| `development`      | Development        | `development_tab.py`     | Containers + Developer tools             |
| `ai_lab`           | AI Lab             | `ai_enhanced_tab.py`     | AI features                              |
| `automation`       | Automation         | `automation_tab.py`      | Scheduler + Replicator + Pulse           |
| `community`        | Community          | `community_tab.py`       | Presets + Marketplace                    |
| `diagnostics`      | Diagnostics        | `diagnostics_tab.py`     | Watchtower + Boot                        |
| `virtualization`   | Virtualization     | `virtualization_tab.py`  | VMs + VFIO + Disposable                  |
| `mesh`             | Loofi Link         | `mesh_tab.py`            | Mesh + Clipboard + File Drop             |
| `teleport`         | State Teleport     | `teleport_tab.py`        | Workspace Capture/Restore                |
| `performance`      | Performance        | `performance_tab.py`     | Auto-Tuner                               |
| `snapshots`        | Snapshots          | `snapshot_tab.py`        | Snapshot Timeline                        |
| `logs`             | Logs               | `logs_tab.py`            | Smart Log Viewer                         |
| `storage`          | Storage            | `storage_tab.py`         | Disks + Mounts + SMART                   |
| `health`           | Health Timeline    | `health_timeline_tab.py` | System health over time                  |
| `profiles`         | Profiles           | `profiles_tab.py`        | User profiles management                 |
| `extensions`       | Extensions         | `extensions_tab.py`      | GNOME/KDE extensions browser             |
| `backup`           | Backup             | `backup_tab.py`          | Backup wizard + Timeshift/Snapper        |
| `agents`           | Agents             | `agents_tab.py`          | AI agent management                      |
| `settings`         | Settings           | `settings_tab.py`        | App settings                             |

Consolidated tabs use `QTabWidget` for sub-navigation within the tab.

### Sidebar Index And Routes (v12.0.0)

The sidebar uses a `SidebarIndex` (`dict[str, SidebarEntry]`) keyed by `PluginMetadata.id` for O(1) tab lookups. `SidebarEntry` holds the tree item, page widget, metadata, and status. Route IDs are resolved through `core.navigation`; Favorites v2 persists route/plugin IDs rather than display-name-derived slugs.

Key methods:

- `_find_or_create_category(category)` — cached category item lookup
- `_create_tab_item(...)` — creates tree item with badge and icon
- `_register_in_index(plugin_id, entry)` — populates index and content area
- `add_page(...)` — public API orchestrator (backward-compatible)
- `switch_to_route(route_id)` — canonical route/plugin navigation with subroute activation
- `switch_to_tab(name)` — backward-compatible alias wrapper
- `_set_tab_status(tab_id, status)` — O(1) status update via data role

Status rendering uses `SidebarItemDelegate` with colored dots instead of text markers.

## Critical Patterns

### 1. PrivilegedCommand (ALWAYS unpack)

```python
from utils.commands import PrivilegedCommand

binary, args, desc = PrivilegedCommand.dnf("install", "package")
cmd = [binary] + args  # ["pkexec", "dnf", "install", "-y", "package"]
# ⚠️ Never pass the raw tuple to subprocess.run()
```

- Returns `Tuple[str, List[str], str]` — binary, args, description
- Auto-detects Atomic (rpm-ostree) vs Traditional (dnf)
- `dnf()` adds `-y` internally — don't duplicate

### 2. BaseTab for UI Tabs

```python
from ui.base_tab import BaseTab

class MyTab(BaseTab):
    def __init__(self):
        super().__init__()
        # Provides: self.output_area, self.runner (CommandRunner),
        # self.run_command(), self.append_output(), self.add_section()
```

### 3. CommandRunner (Async GUI)

```python
from utils.command_runner import CommandRunner
self.runner = CommandRunner()
self.runner.finished.connect(self.on_done)
self.runner.run_command("pkexec", ["dnf", "update", "-y"])
```

Never block the GUI thread with synchronous subprocess calls.

### 3b. CommandFacade (Shared Preview/Execute Boundary)

```python
from core.executor import CommandFacade

result = CommandFacade().preview(["dnf", "check-update"], action_id="updates-preview")
result = CommandFacade().execute(["dnf", "clean", "all"], privileged=True, timeout=120)
```

Use list-based command vectors. The facade delegates to `ActionExecutor` and `command_policy`, preserving allowlist validation, `pkexec`, timeout handling, action IDs, and audit metadata. Do not pass shell strings.

### 4. Operations Tuple Pattern

```python
@staticmethod
def clean_cache() -> Tuple[str, List[str], str]:
    pm = SystemManager.get_package_manager()
    if pm == "rpm-ostree":
        return ("pkexec", ["rpm-ostree", "cleanup", "--base"], "Cleaning...")
    return ("pkexec", ["dnf", "clean", "all"], "Cleaning...")
```

### 5. Error Framework

```python
from utils.errors import LoofiError, DnfLockedError, CommandFailedError
raise DnfLockedError(hint="Package manager is busy.")
# Each error has: code, hint, recoverable attributes
```

### 6. Confirm Dialog (Dangerous Ops)

```python
from ui.confirm_dialog import ConfirmActionDialog
if ConfirmActionDialog.confirm(self, "Delete snapshots", "Cannot be undone"):
    # proceed
```

### 7. Atomic Fedora

```python
pm = SystemManager.get_package_manager()  # "dnf" or "rpm-ostree"
if SystemManager.is_atomic():
    # rpm-ostree path
```

Always use `SystemManager.get_package_manager()` — **never hardcode `dnf`**.

### 8. Privilege Escalation

**Only `pkexec`** — never `sudo`. Policy: `config/org.loofi.fedora-tweaks.policy`.

### 9. Lazy Tab Loading

```python
from core.plugins.loader import PluginLoader
from core.plugins.registry import PluginRegistry
from ui.lazy_widget import LazyWidget

loader = PluginLoader(detector=detector)
loader.load_builtins(context=context)
for plugin in PluginRegistry.instance():
    meta = plugin.metadata()
    lazy_widget = LazyWidget(plugin.create_widget)
    self.add_page(name=meta.name, icon=meta.icon, widget=lazy_widget, category=meta.category)
```

### 10. Safety & History

- `SafetyManager.confirm_action()` — snapshot prompt before risky ops
- `HistoryManager.log_change()` — action log with undo commands (max 50)

### 10b. Settings And State Migration

Saved UI state must be keyed by stable IDs, never translated labels. Migrations must be idempotent and tolerate missing legacy values for:

- theme and system-theme preference
- experience level
- favorite route/plugin IDs
- hidden/default route visibility
- main-window geometry and sidebar state

### 11. Icon System (Semantic IDs + Theme Tint)

- Sidebar, dashboard, and quick actions use semantic icon IDs (for example `home`, `update`, `security-shield`) instead of emoji glyphs.
- Runtime loading and tinting are centralized in `ui/icon_pack.py`.
- Icon roots are checked in this order:
  - `assets/icons/`
  - `loofi-fedora-tweaks/assets/icons/`
- `icon-map.json` maps semantic IDs to assets; SVG is preferred with PNG fallback (`16`, `20`, `24`, `32`).
- Main sidebar applies selection-aware tint variants so active rows are brighter and inactive rows stay integrated with the theme.

## Testing Rules

- **Framework**: `unittest` + `unittest.mock`
- **Decorators only**: `@patch`, never context managers
- **Mock everything**: `subprocess.run`, `check_output`, `shutil.which`, `os.path.exists`, `builtins.open`
- **Both paths**: Test success AND failure
- **No root**: Tests run in CI without privileges
- **Path setup**: `sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'loofi-fedora-tweaks'))`
- **Coverage**: 84%+ current gate, 85% stretch goal

## Adding a Feature

1. **Logic**: `utils/new_feature.py` — `@staticmethod`, return ops tuples
2. **UI**: `ui/new_feature_tab.py` — inherit `BaseTab`
3. **CLI**: Subcommand in `cli/main.py` with `--json`
4. **Test**: `tests/test_new_feature.py` — mock all system calls
5. **Register**: plugin metadata + registry category with semantic `icon="..."` token (no emoji)
6. **Docs**: `CHANGELOG.md`, `README.md`

## Version Management

Three files MUST stay in sync (use `scripts/bump_version.py` for cascade):

- `loofi-fedora-tweaks/version.py` — `__version__`, `__version_codename__`
- `loofi-fedora-tweaks.spec` — `Version:`
- `pyproject.toml` — `version`

## Build & Run

```bash
./run.sh                                                    # Dev run
PYTHONPATH=loofi-fedora-tweaks python -m pytest tests/ -v   # Tests
bash scripts/build_rpm.sh                                   # Build RPM
flake8 loofi-fedora-tweaks/ --max-line-length=150 --ignore=E501,W503,E402,E722,E203
```

## Config & Conventions

- **Config dir**: `~/.config/loofi-fedora-tweaks/`
- **App catalog**: `config/apps.json`
- **QSS**: `assets/modern.qss` — use `setObjectName()` for targeting
- **Icon pack**: `assets/icons/` + `loofi-fedora-tweaks/assets/icons/` (`svg/`, `png/`, `icon-map.json`)
- **i18n**: `self.tr("...")` for all user-visible strings
- **Naming**: `ui/*_tab.py` → `*Tab`; `utils/*.py` → `*Manager`/`*Ops` with `@staticmethod`
- **Plugins**: Extend `LoofiPlugin` ABC, place in `plugins/<name>/plugin.py`
├── daemon/                   # D-Bus daemon host + validators + handlers (v2.4.0)
│   ├── runtime.py            # Daemon bootstrap and GLib main loop
│   ├── server.py             # D-Bus object methods (org.loofi.FedoraTweaks.Daemon1)
│   ├── contracts.py          # Standard JSON response envelope
│   ├── validators.py         # Input validation for privileged operations
│   └── handlers/             # Network/firewall/port-audit execution handlers
