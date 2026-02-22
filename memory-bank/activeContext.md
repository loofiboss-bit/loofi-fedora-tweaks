# Active Context — Loofi Fedora Tweaks

## Current State

**Version**: v2.1.0 "Continuity" — **ACTIVE**
**Date**: 2026-02-22

The repository has opened the v2.1.0 continuation cycle after completing v2.0.0.
This cycle focuses on workflow/tracker consistency and automation hardening before
starting broader feature expansion.

## Recent Changes

- Activated v2.1.0 in `ROADMAP.md` as ACTIVE
- Updated `.workflow/specs/.race-lock.json` to active `v2.1.0`
- Created `.workflow/specs/tasks-v2.1.0.md`
- Created `.workflow/specs/arch-v2.1.0.md`

## Current Work Focus

**Workflow realignment and drift closure**:

1. Reconcile supporting trackers with canonical workflow state
2. Implement adapter sync smart re-render
3. Integrate stats snapshot/render into version bump pipeline
4. Harden CI drift gates

## Open Items

1. Align `memory-bank/progress.md` and `memory-bank/tasks/_index.md` to v2.1.0 workstream
2. Reconcile `.self-maintaining-progress.md` with current repo path and release state
3. Implement v2.1 TASK-004 through TASK-006 in `.workflow/specs/tasks-v2.1.0.md`

## Next Steps

1. Complete tracker reconciliation tasks (documentation state)
2. Begin `scripts/sync_ai_adapters.py` smart re-render implementation
3. Add/extend tests for adapter sync and bump pipeline changes

## Active Decisions

- **Canonical authority**: `ROADMAP.md` + `.workflow/specs/*`
- **Supporting context**: `memory-bank/*` and `.self-maintaining-progress.md` must mirror canonical state
- **Incremental scope**: v2.1.0 prioritizes continuity and deterministic automation over major feature additions
