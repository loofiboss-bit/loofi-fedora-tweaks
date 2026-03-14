# Code Implementer Memory

## Project Structure
- App code lives in `loofi-fedora-tweaks/loofi-fedora-tweaks/` (inner dir), NOT the outer root
- Working directory for code: `loofi-fedora-tweaks/loofi-fedora-tweaks/`
- UI tabs: `loofi-fedora-tweaks/loofi-fedora-tweaks/ui/*_tab.py` (26 tab files + base_tab.py)
- Plugin core: `loofi-fedora-tweaks/loofi-fedora-tweaks/core/plugins/`

## Plugin Architecture (v25.0)
- `core/plugins/interface.py` — PluginInterface ABC with `metadata()`, `create_widget()`, `set_context()`, `on_activate()`, `on_deactivate()`, `check_compat()`
- `core/plugins/metadata.py` — PluginMetadata frozen dataclass
- `ui/base_tab.py` — already implements `QWidget, PluginInterface` with stub _METADATA and default methods
- 26 built-in tabs all migrated in v25.0 Tasks 12/13

## Tab Migration Pattern

### BaseTab subclasses (13 tabs): add PluginMetadata import + _METADATA + metadata() + create_widget()
```python
from core.plugins.metadata import PluginMetadata
class FooTab(BaseTab):
    _METADATA = PluginMetadata(id="foo", name="Foo", description="...", category="Bar", icon="X", badge="", order=N)
    def metadata(self): return self._METADATA
    def create_widget(self): return self
```

### QWidget-only tabs (13 tabs): also add PluginInterface as second parent
```python
from core.plugins.interface import PluginInterface
from core.plugins.metadata import PluginMetadata
class FooTab(QWidget, PluginInterface):  # QWidget MUST come first
    _METADATA = PluginMetadata(...)
    def metadata(self): return self._METADATA
    def create_widget(self): return self
```

### set_context() special case (SettingsTab, DashboardTab): tabs with MainWindow constructor arg
- Change `__init__(self, main_window)` to `__init__(self, main_window=None)`
- Defer UI build (if it needs main_window) to `set_context()` or just store as optional
- settings_tab: defers `_init_ui()` to `set_context()`; dashboard_tab: `main_window=None` default is enough (only used in button handlers with hasattr guards)

## Arch Spec Location
- `.workflow/specs/arch-v25.0.md` — full plugin interface spec, metadata reference table, per-task notes

## Critical Edit Warning
- When editing class docstrings, be careful not to accidentally insert class body code INSIDE the docstring
- Always use a separate old_string that ends the docstring with `"""` before placing new class attributes

## CLI Modularization (2026-02-25) ✅ COMPLETE

### Fixed Handler API Mismatches

**agent_commands.py** - Aligned with AgentRegistry:
- Methods: `instance().list_agents()`, `get_state(id)`, `enable_agent(id)`, `disable_agent(id)`, `register_agent(config)`, `remove_agent(id)`, `get_recent_activity(limit)`
- Actions fixed: status (uses get_state), create (uses register_agent), remove, logs, templates, notify

**service_package_commands.py** - Aligned with ServiceExplorer:
- Methods: `list_services(scope, filter_state, search)`, `get_service_details(name, scope)`, `start/stop/restart/enable/disable/mask/unmask_service(name, scope)`, `get_service_logs(name, scope, lines)`  
- Args fixed: `service_name` → `name`, added `user` scope flag, ServiceScope imported in handler

**diagnostic_commands.py** - Fixed import path:
- Changed `from services.system import cached_which` → `from services.system.system import cached_which`

**main.py** - Cleaned dead imports:
- Removed: `cached_which`, `ServiceScope`, `handle_display`, `handle_health_history`, `handle_logs`, `handle_tuner`, `handle_backup`
- These commands (`cmd_health_history`, `cmd_tuner`, `cmd_logs`, `cmd_display`, `cmd_backup`) remain inline in main.py ~lines 400-1200

**cli/__init__.py** - Added main import for test compatibility:
- Added `from cli import main  # noqa: F401` to make `cli.main` resolvable by test patches

### Test Results
✅ All 62 targeted tests pass (test_v17_cli.py, test_new_features.py, test_main_entry.py)
✅ Flake8 passes on all changed files
✅ Backward compatibility maintained - tests can still patch `cli.main.BluetoothManager`, etc.

### Test Compatibility Rule
CLI tests patch symbols on `cli.main`. When extracting handlers, keep wrapper functions (`cmd_*`) in cli.main as monkeypatch points.
