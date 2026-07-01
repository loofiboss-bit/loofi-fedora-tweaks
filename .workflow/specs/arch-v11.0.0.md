# Architecture — v11.0.0 "Harbor"

## Goals

- Add a narrow `core.actions` Action Center layer above existing readiness and executor modules instead of creating a second command system.
- Keep Fedora KDE 44 as the stable supported target and Fedora 45 as preview/advisory.
- Make daily maintenance, rollback guidance, and support export data testable without root or host mutation.

## Decisions

- Action Center items are pure dataclasses in `core/actions/model.py`.
- Command preview and execution continue through `core.executor.CommandFacade` and the shared command policy.
- Readiness actions remain the first Action Center source via `ReadinessActionService`.
- Medium/high-risk actions receive rollback guidance from `RollbackGuidanceService` before execution.
- Daily Maintenance probes are read-only, bounded, and mockable in `core/diagnostics/daily_maintenance.py`.
- Support Bundle v7 extends `SupportBundleV5` for import compatibility and adds a `SupportBundleV7` alias.
