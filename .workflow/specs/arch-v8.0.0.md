# Architecture — v8.0.0

## Goals

- Make navigation stable, searchable, and persistable without adding major feature tabs.
- Keep `core/navigation` PyQt-free so release checks, command palette data, quick actions, and favorites can validate routes without importing UI.
- Preserve existing privilege boundaries: UI does not execute subprocesses, CLI does not import UI, services/core do not import PyQt6, and privileged actions continue through pkexec-aware executor conventions.
- Harden release trust by validating command allowlists, snapshot commands, RPM imports, packaging manifests, active roadmap state, and dynamic plugin counts.

## Decisions

- `NavigationRoute.id` is the canonical persisted identifier. Plugin routes use `PluginMetadata.id`; subroutes use `<area>:<subroute>` and carry the owning `plugin_id`.
- Legacy tab labels are aliases only. Compatibility stays in `resolve()` and `MainWindow.switch_to_tab()`.
- `MainWindow.switch_to_route(route_id)` selects the owning plugin, lazy-loads the widget when needed, and delegates to `activate_route(route)` when present. Generic `QTabWidget` label/alias matching is the fallback.
- Favorites v2 stores `{"version": 2, "favorites": [...]}` and migrates legacy lists through route alias resolution.
- Command palette, quick action registry, dashboard quick action config, Atlas task cards, and health-detail navigation all emit route IDs.
- `core.executor.command_policy` is the shared allowlist boundary for preview, execute, API executor requests, and ProfileManager snapshot commands.
- The RPM `%check` import smoke is blocking and imports `core.navigation`.
- Packaging validation inspects wheel and sdist artifacts for source subpackages, assets, QSS/icons, translations, config/agent resources, and entry point metadata.

## Required Routes

- Maintenance: `maintenance:updates`, `maintenance:cleanup`, `maintenance:smart-updates`, `maintenance:overlays`
- System monitor: `system-monitor:performance`, `system-monitor:processes`
- Software: `software:apps`, `software:repos`, `software:flatpak`
- Security: `security:overview`, `security:firewall`, `security:privacy`, `security:ports`
- Network: `network:connections`, `network:dns`, `network:privacy`, `network:monitoring`
- Desktop: `desktop:director`, `desktop:theming`, `desktop:display`
- Development: `development:containers`, `development:developer`
- Automation: `automation:scheduler`, `automation:replicator`
- Community: `community:presets`, `community:marketplace`, `community:plugins`, `community:featured`
- Diagnostics: `diagnostics:watchtower`, `diagnostics:boot`
- Existing detail surfaces for AI Lab, Loofi Link, virtualization, settings, and agents remain routes over existing plugins.
