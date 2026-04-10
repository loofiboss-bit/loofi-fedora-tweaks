# Roadmap: Loofi Fedora Tweaks Alignment Planning

## Overview

This GSD roadmap mirrors the repository's active stabilization target and turns it into executable plan files. The immediate goal is to close the active `v2.13.0 "Alignment"` slice by reconciling release authority, documentation entrypoints, workflow evidence, and validation rules without expanding product or privilege scope.

## Phases

**Phase Numbering:**
- Integer phases (1, 2, 3): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

- [ ] **Phase 1: v2.13.0 Alignment** - Documentation/workflow convergence for authoritative release truth

## Phase Details

### Phase 1: v2.13.0 Alignment
**Goal**: Restore a single authoritative release story across roadmap metadata, workflow artifacts, README/docs entrypoints, and architecture references while preserving the actual runtime surface.
**Depends on**: Nothing (first phase)
**Requirements**: [ALIGN-01, ALIGN-02, ALIGN-03, ALIGN-04, ALIGN-05, ALIGN-06]
**Success Criteria** (what must be TRUE):
  1. Maintainers can open `README.md`, `docs/README.md`, `docs/releases/RELEASE_NOTES.md`, and `ARCHITECTURE.md` without seeing contradictory release/version or entry-mode claims.
  2. No release note in the repository references nonexistent `.workflow/reports/*.json` artifacts.
  3. Validation scripts and regression tests fail when stale release pointers or missing workflow report references are reintroduced.
  4. Canonical `v2.13.0` workflow reports and release-note artifacts exist for slice closure.
**Plans**: 4 plans

Plans:
- [x] 01-01: Reconcile `README.md` release framing and run-mode documentation
- [ ] 01-02: Refresh docs entrypoints and `ARCHITECTURE.md` to the verified repo state
- [ ] 01-03: Remove false `v2.12.0` workflow-report claims and harden report/document validation
- [ ] 01-04: Generate canonical `v2.13.0` closure artifacts and publish verified release metadata

## Progress

**Execution Order:**
Phases execute in numeric order: 1

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. v2.13.0 Alignment | 1/4 | In progress | 01-01 |
