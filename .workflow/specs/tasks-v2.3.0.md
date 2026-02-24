# Tasks — v2.3.0 "Insight"

**Date**: 2026-02-24
**Status**: DONE
**Arch Spec**: `arch-v2.3.0.md`

## Task List

---

### TASK001 — Add `gather_services_info()` to `ReportExporter`

**ID**: TASK001
**Status**: Complete
**Files**: `core/export/report_exporter.py`
**Dep**: none
**Agent**: backend-builder
**Description**: Add `gather_services_info()` static method that calls `systemctl --failed --no-legend` and returns a list of failed unit names and their sub-state.
**Acceptance**: Method returns `[]` on clean system, list of dicts on failures; handles `SubprocessError` gracefully; has `timeout=15`.
**Docs**: docstring with Args/Returns
**Tests**: TASK005

---

### TASK002 — Add `gather_journal_errors()` to `ReportExporter`

**ID**: TASK002
**Status**: Complete
**Files**: `core/export/report_exporter.py`
**Dep**: none
**Agent**: backend-builder
**Description**: Add `gather_journal_errors()` that calls `journalctl -p 3 -n 20 --no-pager --output=short` and returns last 20 lines of errors/critical messages as a single string.
**Acceptance**: Returns `""` when no errors; handles permission/missing journalctl gracefully; `timeout=15`.
**Docs**: docstring
**Tests**: TASK005

---

### TASK003 — Add `gather_updates_info()` to `ReportExporter`

**ID**: TASK003
**Status**: Complete
**Files**: `core/export/report_exporter.py`
**Dep**: none
**Agent**: backend-builder
**Description**: Add `gather_updates_info()` that checks pending update count using `dnf check-update -q` (traditional) or `rpm-ostree status` (atomic). Branches on `SystemManager.is_atomic()`.
**Acceptance**: Returns string like `"12 packages pending"` or `"Up to date"` or `"Unknown"`. Handles both Fedora variants. `timeout=30`.
**Docs**: docstring
**Tests**: TASK005

---

### TASK004 — Add `gather_selinux_info()` and `gather_network_info()`, update export methods

**ID**: TASK004
**Status**: Complete
**Files**: `core/export/report_exporter.py`
**Dep**: TASK001, TASK002, TASK003
**Agent**: backend-builder
**Description**: Add `gather_selinux_info()` (getenforce + recent AVC denials), `gather_network_info()` (IP, DNS, gateway), and `gather_all_diagnostics()` master method. Update `export_html()` and `export_markdown()` to accept and render all sections.
**Acceptance**: HTML report includes all 6 sections; Markdown report includes all sections; `save_report()` calls `gather_all_diagnostics()` when `info=None`.
**Docs**: All methods documented
**Tests**: TASK005

---

### TASK005 — Write `tests/test_report_exporter.py`

**ID**: TASK005
**Status**: Complete
**Files**: `tests/test_report_exporter.py`
**Dep**: TASK004
**Agent**: test-writer
**Description**: Comprehensive unit tests for all new and existing methods. Mock all subprocess calls. Test both success and failure paths. Test atomic and traditional Fedora paths for `gather_updates_info`.
**Acceptance**: All new methods have success + failure tests; at least 90% branch coverage on `report_exporter.py`; `@patch` decorators only.
**Docs**: module docstring
**Tests**: self

---

### TASK006 — Update CHANGELOG and ROADMAP, activate v2.3.0

**ID**: TASK006
**Status**: Complete
**Files**: `CHANGELOG.md`, `ROADMAP.md`, `memory-bank/activeContext.md`, `memory-bank/progress.md`
**Dep**: TASK005
**Agent**: release-planner
**Description**: Add v2.3.0 entry to CHANGELOG, add v2.3.0 entry to ROADMAP version index, update memory-bank files.
**Acceptance**: CHANGELOG has v2.3.0 section; ROADMAP version index includes v2.3.0; memory-bank reflects ACTIVE state.
**Docs**: n/a
**Tests**: n/a
