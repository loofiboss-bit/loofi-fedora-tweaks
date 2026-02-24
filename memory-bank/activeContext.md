# Active Context — Loofi Fedora Tweaks

## Current State

**Version**: v2.3.0 "Insight" — **DONE**
**Date**: 2026-02-24

v2.3.0 is complete. All six planned deliverables shipped: five diagnostic gather methods,
`gather_all_diagnostics()`, updated `export_markdown()`/`export_html()`/`save_report()`,
HTML CSS improvements, and 33 unit tests (all passing). Race-lock closed.

## Recent Changes

- Released v2.3.0 "Insight" — enhanced diagnostics: 5 new report sections
- Added `gather_services_info()`, `gather_journal_errors()`, `gather_updates_info()`,
  `gather_selinux_info()`, `gather_network_info()` to `ReportExporter`
- `save_report()` now defaults to `comprehensive=True`; all export methods accept `diagnostics=`
- Replaced `tests/test_report_exporter.py` with 33-test suite (9 classes) — all passing
- Closed v2.3.0 race-lock as completed
- Updated CHANGELOG.md, ROADMAP.md (version index + detailed section), tasks-v2.3.0.md

## Current Work Focus

**No active version** — v2.3.0 is done. Awaiting v2.4.0 planning.

Candidates for v2.4.0:

- New Fedora-specific feature tabs
- Coverage push toward 85%+
- Improved AI agent / scheduling capabilities
- UI/UX polish pass

## Open Items

1. Plan and activate v2.4.0 scope in ROADMAP.md
2. Update `.workflow/specs/.race-lock.json` to new active version
3. Create `.workflow/specs/tasks-v2.4.0.md` and `arch-v2.4.0.md`

## Active Decisions

- **Canonical authority**: `ROADMAP.md` + `.workflow/specs/*`
- **Stabilization gate**: All 6 phases complete — feature expansion is unblocked
- **Coverage**: Baseline at 77–81% (CI gate at 77%)
