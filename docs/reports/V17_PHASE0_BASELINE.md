# v17 Phase 0 Baseline and Scope Lock

Date: 2026-07-20
Baseline: `b42facecff6e5b9c8f16e96bdbb14c45ee98b6da`

## Release baseline

- v16.0.0 is released and publicly verified.
- Meaningful Home: 181.011 ms; RSS: 77,970 KiB.
- Startup: one Home plugin, zero subprocess probes, timers, and QThreads.
- Release suite: 7,722 passed, 40 skipped, 86.48 percent coverage.

## Component decision

Current deterministic analysis reports 374 modules, 113 shared core/specialist
modules, 50 specialist-exclusive modules, and specialist-exclusive reach from
CLI/API/daemon. A physical extras package is therefore not a v17 deliverable.

## Mutation classification

| Surface | Phase 0 state | v17 target |
| --- | --- | --- |
| Action Center three-action catalog | Verified | Preserve |
| Fedora/Flatpak/firmware updates | Confirmed, exit-code based | Independent verified plans |
| Application install/remove | Direct command runner | Verified plans |
| Slow-system diagnosis | Read-only with verified service handoff | Preserve |
| Cleanup | Mixed verified/direct/manual | Verified or manual-only |
| Recovery-point creation | Direct command runner | Verified plan |
| Restore/delete | Direct high-risk paths | Explicitly outside Assurance |
| Web API executor/profile writes | Mutating despite read-only product claim | Remove |

Phase 0 changes documentation and workflow authority only. Product code and
16.0.0 metadata remain unchanged.
