# Architecture Spec — v2.1.0 "Continuity"

## Summary

v2.1.0 is a workflow and automation continuity release. It establishes a clean
post-v2.0 baseline by synchronizing authoritative workflow state, memory trackers,
and self-maintaining adapter automation.

## Design Principles

1. **Workflow-first authority**: `ROADMAP.md` + `.workflow/specs/*` are canonical state
2. **No layer violations**: Documentation/automation work only; no UI business logic changes
3. **Incremental hardening**: Complete drift/automation fixes before any major feature expansion
4. **Deterministic release plumbing**: Stats and adapter sync behavior must be reproducible

## Target Architecture Changes

| Area                     | Current Issue                                         | v2.1.0 Design Direction                                    |
| ------------------------ | ----------------------------------------------------- | ---------------------------------------------------------- |
| Workflow state           | v2.0.0 completed with no active continuation cycle    | Explicitly activate v2.1.0 with task/arch contracts        |
| Memory bank              | Stale release-closure items in progress trackers      | Align active/progress/task index with v2.1.0               |
| Self-maintaining tracker | Historical path and phase drift vs canonical workflow | Reconcile to current repo path and active version          |
| Adapter sync pipeline    | Manual/stat drift maintenance burden                  | Smart re-render driven by previous/current stats snapshots |
| Version bump cascade     | Stats and adapter rendering not fully coupled         | Integrate prev-stats snapshot + render into bump flow      |
| CI policy                | Drift checks may be non-blocking or unclear           | Enforce blocking checks with actionable failures           |

## Execution Flow (v2.1.0)

1. Open v2.1.0 cycle (`ROADMAP`, race-lock, task spec, arch spec)
2. Align supporting trackers (`memory-bank/*`, `.self-maintaining-progress.md`)
3. Implement `sync_ai_adapters.py` smart re-render logic
4. Integrate previous-stats capture in `bump_version.py` pipeline
5. Tighten CI gates for stats/adapter drift

## Constraints

- Keep stabilization/security invariants unchanged (`pkexec`, no `sudo`, no `shell=True`, subprocess timeouts)
- Preserve current architecture boundaries (`ui/` no subprocess/business logic)
- Follow existing test conventions (`@patch` decorators, module-under-test patch paths)
- Avoid speculative feature work in v2.1.0 until continuity tasks are complete

## Verification Criteria

- v2.1.0 marked ACTIVE and parseable by workflow tooling
- Memory and progress trackers no longer contradict canonical workflow state
- Adapter sync automation updates drifted values deterministically from stats files
- Version bump path produces updated stats and rendered adapter files in one flow
- CI fails on stats/adapter drift regressions
