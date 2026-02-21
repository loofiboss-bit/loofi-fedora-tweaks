# Release Notes — v2.0.0 "Evolution"

**Release Date:** 2026-02-21
**Codename:** Evolution
**Theme:** Service Layer Migration — domain logic extraction from flat `utils/` into organized `services/` and `core/` layers

## Summary

v2.0.0 "Evolution" is a structural refactoring release that reorganizes the codebase from
a flat `utils/` namespace into domain-specific `services/` and `core/` layers. This establishes
clear architectural boundaries for future development while maintaining full backward compatibility
through deprecation shims. No user-facing behavior changes — all 6383 tests pass.

## Highlights

- **22 modules migrated** from `utils/` to `services/` across 6 domains (security, software, desktop, storage, network, virtualization)
- **14 modules migrated** from `utils/` to `core/` across 4 domains (agents, ai, diagnostics, export)
- **Backward-compatible deprecation shims** in `utils/` — existing imports continue to work with `DeprecationWarning`
- **3 legacy deprecated shims removed** (`process.py`, `battery.py`, `action_executor.py`)
- **All UI/CLI/API/plugin imports updated** to new service/core paths
- **6383 tests passing**, 80%+ coverage, 0 new failures

## Architecture Changes

### New `services/` Layer

| Domain | Modules | Key Classes |
| --- | --- | --- |
| `services/security/` | 7 | FirewallManager, SecureBootManager, USBGuardManager, SandboxManager, SafetyManager, AuditLogger, RiskRegistry |
| `services/software/` | 1 | FlatpakManager |
| `services/desktop/` | 4 | DesktopUtils, KwinTiling, Tiling, WaylandDisplay |
| `services/storage/` | 2 | CloudSync, StateTeleport |
| `services/network/` | 4 | NetworkUtils, NetworkMonitor, Ports, MeshDiscovery |
| `services/virtualization/` | 4 | Virtualization, VMManager, VFIO, DisposableVM |

### New `core/` Domains

| Domain | Modules | Key Classes |
| --- | --- | --- |
| `core/agents/` | 5 | AgentRegistry, AgentPlanner, AgentExecutor, AgentScheduler, AgentNotifier |
| `core/ai/` | 3 | AIAssistant, AISettingsManager, AIFeaturesManager |
| `core/diagnostics/` | 3 | DiagnosticManager, TroubleshootManager, LogManager |
| `core/export/` | 3 | AnsibleExporter, KickstartGenerator, ReportExporter |

### Migration Strategy

1. Module files moved to new domain directories with `__init__.py` re-exports
2. Deprecation shims left in `utils/` — emit `DeprecationWarning` on import
3. All internal imports (UI, CLI, API, plugins) updated to new paths
4. Test `@patch` paths updated to match new module locations

## Changes

### Changed

- Migrated 22 modules from `utils/` to `services/` (security, software, desktop, storage, network, virtualization)
- Migrated 14 modules from `utils/` to `core/` (agents, ai, diagnostics, export)
- Updated all UI tab imports to use `services.*` and `core.*` namespaces
- Updated CLI imports (AuditLogger, FirewallManager, agents, ai_models, health_timeline)
- Updated API imports (AgentRegistry, ActionExecutor)
- Updated plugin imports (PluginIsolationManager, OllamaManager, AIConfigManager, ContextRAGManager)
- Updated 120+ `@patch` paths in test files to match new module locations

### Removed

- `utils/process.py` — deprecated shim (removed, was already unused)
- `utils/battery.py` — deprecated shim (removed, consumers migrated to `services/hardware/`)
- `utils/action_executor.py` — deprecated shim (removed, consumers use `core/executor/`)

### Added

- `services/__init__.py` packages for all 6 service domains
- `core/agents/__init__.py`, `core/ai/__init__.py`, `core/diagnostics/__init__.py`, `core/export/__init__.py`
- Backward-compatible deprecation shims in `utils/` for all 36 migrated modules

## Upgrade Guide

### For Plugin Authors

If your plugin imports from `utils/`, those imports still work but will emit `DeprecationWarning`.
Update to the new paths:

```python
# Old (deprecated, still works)
from utils.firewall import FirewallManager

# New (preferred)
from services.security.firewall import FirewallManager
# or
from services.security import FirewallManager
```

### For CLI Users

No changes — CLI interface and output formats are unchanged.

## Testing

- **6383 tests passing** (47 pre-existing Windows-only failures, 95 skipped)
- **80%+ code coverage** maintained
- All `@patch` decorator paths updated to new module locations
- Both success and failure paths tested for migrated modules

