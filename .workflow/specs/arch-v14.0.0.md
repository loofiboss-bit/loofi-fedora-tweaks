# Architecture — v14.0.0 "Helm"

## Goals

Complete the guided maintenance chain with a bounded, explicit, crash-safe
plan/apply/verify lifecycle. Preserve Fedora 44 as the supported target and
keep Fedora 45 advisory.

## Decisions

- `core.actions` owns action definitions, plans, policy decisions, durable runs, and lifecycle transitions.
- Persisted plans contain action IDs and validated parameters, never authoritative command vectors.
- Commands are regenerated and preflighted at apply time; `pkexec` remains a separate typed privilege boundary.
- Plans expire after 30 minutes. One cross-process mutation lease is allowed; interrupted runs never auto-resume.
- `succeeded` requires the definition's verifier. No fix-all, automatic rollback, scheduled mutation, or plugin-provided executable action exists.
- The v14 executable catalog is limited to `dnf-clean-all`, `restart-failed-service`, and `fstrim-all`; everything else remains manual-only.
- New API surfaces are authenticated and read-only. Existing API and D-Bus mutation contracts remain compatibility-only and are not expanded.
- Existing route, plugin, task, settings, favorites, Action Center item, readiness CLI, and support-bundle compatibility fields remain stable.
- Numeric SQLite metrics and structured JSON snapshots remain separate behind `ObservabilityService`.
- Release artifacts must be built from and tagged at the exact release commit; a mismatched pre-existing tag is a hard failure.

## Safety invariants

- All system commands are list-based, allowlisted, timeout-bounded, audit-linked, and never use `shell=True`.
- Medium/high-risk actions without supported rollback require an explicit no-rollback acknowledgement.
- Atomic Fedora capability policy is fail-closed; cache mutation stays read-only/manual there.
- GUI execution is asynchronous through `BaseTab`/`CommandRunner`; core and services remain PyQt-free.
