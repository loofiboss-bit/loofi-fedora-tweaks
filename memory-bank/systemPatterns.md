# System Patterns — Loofi Fedora Tweaks

## Architecture Overview

```
GUI (PyQt6) ─┐
CLI (argparse)─┤──→ Services (domain/) ──→ Core (domain/) ──→ Utils (shared/)
API (FastAPI) ─┤
Daemon ────────┘
```

All four entry modes are thin consumers. Business logic lives in `services/` and `core/`. Shared infrastructure (commands, errors, system detection) lives in `utils/`.

## Layer Rules (Strict)

| Layer | Path | Allowed | Forbidden |
|-------|------|---------|-----------|
| UI | `ui/*_tab.py` | PyQt6 widgets, signals, `BaseTab` inheritance | `subprocess`, business logic |
| Services | `services/*/` | Domain services, `@staticmethod` ops | `import PyQt6`, UI references |
| Core | `core/*/` | Domain modules (agents, AI, diagnostics, export, executor, plugins) | `import PyQt6`, UI references |
| Utils | `utils/*.py` | Shared ops, commands, errors, backward-compat shims | `import PyQt6`, UI references |
| CLI | `cli/main.py` | Argument parsing, calls services/core/utils | `import ui`, PyQt6 |
| API | `api/routes/` | FastAPI endpoints, calls services/core/utils | PyQt6 |

## Critical Patterns

### 1. PrivilegedCommand (Always Unpack)

```python
from utils.commands import PrivilegedCommand
binary, args, desc = PrivilegedCommand.dnf("install", "package")
cmd = [binary] + args  # ["pkexec", "dnf", "install", "-y", "package"]
```

- Returns `Tuple[str, List[str], str]` — NEVER pass the tuple directly to subprocess
- `dnf()` adds `-y` internally — don't duplicate

### 2. BaseTab Inheritance

```python
from ui.base_tab import BaseTab
class MyTab(BaseTab):
    def __init__(self):
        super().__init__()  # provides self.output_area, self.runner, self.run_command()
```

### 3. Package Manager Detection

```python
pm = SystemManager.get_package_manager()  # "dnf" or "rpm-ostree"
if SystemManager.is_atomic():
    # rpm-ostree path
else:
    # dnf path
```

### 4. Subprocess Safety

- Always `timeout=N` on every `subprocess.run()` / `check_output()` call
- Never `shell=True`
- Never `sudo` — only `pkexec` via PrivilegedCommand
- Audit log all privileged actions (timestamp, action, params, exit code)

### 5. Error Handling

```python
from utils.errors import LoofiError, DnfLockedError, CommandFailedError
raise DnfLockedError(hint="Package manager is busy.")
# Each error has: code, hint, recoverable attributes
```

### 6. Dangerous Operations

```python
from ui.confirm_dialog import ConfirmActionDialog
if ConfirmActionDialog.confirm(self, "Delete snapshots", "Cannot be undone"):
    # proceed
```

### 7. Lazy Tab Loading

Tabs register via `MainWindow._lazy_tab()` loaders dict and load on first navigation.

## Service Domains (9)

| Domain | Path | Responsibility |
|--------|------|----------------|
| security | `services/security/` | Audit, firewall, risk assessment, safety, sandbox, SecureBoot, USB guard |
| hardware | `services/hardware/` | Battery, Bluetooth, disk, hardware info, profiles, temperature |
| network | `services/network/` | Mesh networking, monitoring, network config, port management |
| desktop | `services/desktop/` | Desktop settings, display config, KWin, tiling |
| software | `services/software/` | Flatpak management |
| storage | `services/storage/` | Cloud sync, teleport |
| virtualization | `services/virtualization/` | Disposable VMs, VFIO passthrough, VM management |
| system | `services/system/` | Process management, services, system info |
| package | `services/package/` | Package management abstraction |

## Core Domains (8)

| Domain | Path | Responsibility |
|--------|------|----------------|
| agents | `core/agents/` | AI agent runtime, planning, scheduling, notifications |
| ai | `core/ai/` | AI integration, model management, RAG context |
| diagnostics | `core/diagnostics/` | Health score, timeline, detailed diagnostics |
| export | `core/export/` | Ansible export, kickstart generation, reports |
| executor | `core/executor/` | `BaseActionExecutor` + `ActionResult` abstraction |
| plugins | `core/plugins/` | Plugin lifecycle: loading, sandboxing, integrity, marketplace |
| profiles | `core/profiles/` | System profiles, hardware profiles storage |
| workers | `core/workers/` | Background worker threads (`BaseWorker`, `CommandWorker`) |

## Component Relationships

```
UI Tabs → CommandRunner (QProcess) → Services/Core → Utils → subprocess
                                                          → PrivilegedCommand (pkexec)
                                                          → SystemManager (detection)
                                                          → ErrorHandler (typed exceptions)
```

## Plugin System

- `LoofiPlugin` ABC — all plugins implement this interface
- `PluginLoader` → `PluginScanner` → `PluginRegistry` for lifecycle
- `PluginSandbox` for execution isolation
- `PluginIntegrity` for manifest validation
- Marketplace with CDN index, ratings, reviews, badges, analytics
