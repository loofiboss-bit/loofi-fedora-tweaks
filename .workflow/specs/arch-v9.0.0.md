# Architecture — v9.0.0

## Goals

- Improve the whole application without adding a new permanent feature tab or making Fedora 45 the main target.
- Keep Fedora KDE 44 as the supported readiness target and preserve `45-preview` as advisory-only metadata.
- Standardize command execution at the boundary shared by GUI, CLI, daemon/API, and services.
- Strengthen state/settings reliability and route/plugin drift detection while preserving existing public IDs and saved user state.
- Make documentation and release gates reflect the actual current project instead of stale historical planning assumptions.

## Decisions

- Add `core.executor.command_facade.CommandFacade` as the v9 entrypoint for command-vector preview/execute calls. It delegates validation and execution to the existing command policy and `ActionExecutor`.
- Keep `ActionExecutor`, `PrivilegedCommand`, daemon fallback code, and service-specific helpers in place for compatibility; migrate call sites opportunistically after the facade contract is covered.
- Raise the release quality gate to 84% across Justfile, CI, auto-release, and release-doc validation.
- Keep `ReleaseReadiness.DEFAULT_TARGET` and `ReadinessActionService.DEFAULT_TARGET` on Fedora 44. Do not rename or promote `45-preview`.
- Preserve all existing `NavigationRoute.id` values and route aliases. Add trust tests instead of route renames.
- Treat Qt-dependent worker/plugin bridge modules as explicit runtime exceptions inside architecture docs and tests; services remain PyQt-free.
- State migration must be idempotent and tolerate missing legacy keys for theme, experience level, favorites, hidden routes, and window geometry.

## Validation Contract

- Release docs fail if metadata, workflow specs, race lock, coverage gates, or active roadmap state drift.
- Command facade tests cover preview, execute, privilege wrapping, policy rejection, and command-vector normalization.
- Readiness tests assert Fedora 44 defaults and Fedora 45 preview-only behavior.
- Navigation tests assert palette/quick-action parity, hidden advanced route searchability, and plugin metadata stability.
- Architecture tests assert that PyQt imports in core/services are limited to documented runtime exceptions.
