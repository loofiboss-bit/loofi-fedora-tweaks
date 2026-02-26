# Release Notes — v2.10.0 "API Migration Slice 6"

## Overview

v2.10.0 starts the next bounded daemon/API migration cycle after v2.9.0 closure. This slice first normalizes workflow and report artifact conventions to canonical `vX.Y.Z` tags, then establishes a concrete method-level migration target inventory for the next implementation steps. The work keeps strict compatibility constraints in place: no privilege model expansion, fail-closed behavior, and preferred-mode fallback continuity.

## Highlights

- Standardized workflow/report artifact tag handling to canonical `vX.Y.Z` in core workflow scripts.
- Updated workflow regression tests to enforce canonical-tag behavior and reject short-tag-only assumptions.
- Activated v2.10.0 workflow contracts (`tasks-v2.10.0.md`, `arch-v2.10.0.md`) and seeded `run-manifest-v2.10.0.json`.
- Generated canonical focused test artifact `test-results-v2.10.0.json` from the v2.10 workflow regression suite.
- Completed bounded method-level residual target inventory for Slice 6:
  - Network write-path strict-success propagation candidates
  - Firewall privileged command consistency/parity candidates
  - System read-path classification candidates
- Advanced workflow progression through `P1 PLAN`, `P2 DESIGN`, `P3 BUILD`, and `P4 TEST` with `P5 DOC` documentation sync.

## Upgrade Notes

- This slice does not introduce user-facing privilege model changes.
- Existing daemon preferred-mode fallback behavior remains intact.
- Packaging/version bump alignment should be finalized in package/release phases when runtime version is advanced from `2.9.0` to `2.10.0`.
