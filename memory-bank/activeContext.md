# Active Context — Loofi Fedora Tweaks

## Current State

**Version**: v2.0.0 "Evolution" — **COMPLETE**
**Date**: 2026-02-22

The project has completed the v2.0.0 "Evolution" release, which migrated business logic from monolithic `utils/*.py` modules into a structured `services/` layer with 9 domains. All 12 migration tasks are done.

## Recent Changes (v2.0.0)

- Migrated services: software, desktop, storage, network, virtualization, security
- Populated core stubs (executor, diagnostics, export, plugins, profiles, workers)
- Updated all UI, CLI, API, and plugin imports to use new service paths
- Removed deprecated backward-compatibility shims
- Updated ARCHITECTURE.md, ROADMAP.md, README.md
- Fixed CI release job tag handling
- Synced workspace configs

## Current Work Focus

**Between releases** — no ACTIVE or NEXT version defined in ROADMAP.md.

## Open Items

1. **Race-lock status**: Still set to `active` in `.workflow/specs/.race-lock.json` — should be updated to `done`
2. **Git tag conflict**: Old pre-SemVer `v2.0.0` tag (commit `4933073`) conflicts with the new SemVer v2.0.0 "Evolution" release (HEAD at `aaac690`, 14 commits ahead). Needs resolution: delete old tag + retag, or bump to v2.0.1
3. **No next version planned**: ROADMAP.md has no ACTIVE, NEXT, or PLANNED entries after v2.0.0

## Next Steps

1. Close v2.0.0 release (fix tag conflict, update race-lock to `done`)
2. Plan next version scope (v2.1.0 or v3.0.0)
3. Consider remaining stabilization or new feature work

## Active Decisions

- **SemVer adopted**: Project moved from integer versioning (v21–v50) to SemVer (v1.0.0 → v2.0.0)
- **Service layer pattern**: All domain logic lives in `services/` with `@staticmethod` methods
- **Stabilization complete**: All 6 hardening phases are done — new features are now unblocked
- **Memory bank initialized**: 2026-02-22
