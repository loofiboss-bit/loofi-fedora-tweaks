# Requirements: Loofi Fedora Tweaks Alignment Slice

**Defined:** 2026-04-10
**Core Value:** Provide a safe, trustworthy Fedora administration surface whose documentation, workflow metadata, and runtime behavior agree with each other.

## v1 Requirements

### Release Authority

- [ ] **ALIGN-01**: Maintainer can identify the active workflow target from one authoritative source without conflicting repo entrypoint docs
- [x] **ALIGN-02**: README presents the repo's release story and run modes without stale current-release branding
- [ ] **ALIGN-03**: Docs index and architecture reference point to the real latest documented release line and actual entry-mode surface

### Workflow Evidence

- [ ] **ALIGN-04**: Release notes never reference workflow report files that do not exist
- [ ] **ALIGN-05**: Validation scripts and tests fail when release/doc/workflow drift is introduced
- [ ] **ALIGN-06**: The active `v2.13.0` slice can publish canonical release notes and workflow report artifacts after verification

## v2 Requirements

### Deferred

- **ALIGN-FUTURE-01**: Rename the headless API flag from `--web` to `--api` across runtime, packaging, and docs
- **ALIGN-FUTURE-02**: Bump packaged runtime/version files from `2.11.0` to the next verified shipped release line

## Out of Scope

| Feature | Reason |
|---------|--------|
| New UI tabs or runtime features | `v2.13.0` is documentation/workflow hardening only |
| Privilege or daemon surface expansion | Stabilization rules forbid scope creep |
| Fabricated historical workflow reports | Evidence integrity must be preserved |

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| ALIGN-01 | Phase 1 | Pending |
| ALIGN-02 | Phase 1 | Completed |
| ALIGN-03 | Phase 1 | Pending |
| ALIGN-04 | Phase 1 | Pending |
| ALIGN-05 | Phase 1 | Pending |
| ALIGN-06 | Phase 1 | Pending |

**Coverage:**
- v1 requirements: 6 total
- Mapped to phases: 6
- Unmapped: 0 ✓

---
*Requirements defined: 2026-04-10*
*Last updated: 2026-04-10 after active-slice planning bootstrap*
