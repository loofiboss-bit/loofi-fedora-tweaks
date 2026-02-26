# Architecture Spec — v2.3.0 "Insight"

**Date**: 2026-02-24
**Status**: ACTIVE
**Focus**: Enhanced Diagnostic Report

## Summary

Extend the existing `ReportExporter` (in `core/export/report_exporter.py`) to produce a
comprehensive multi-section diagnostic HTML/Markdown report. The existing system only
exports basic system info (9 fields). v2.3.0 adds 5 new diagnostic sections:

1. **Failed Services** — systemd units in a failed state
2. **Journal Errors** — last 10 critical/error log entries
3. **Pending Updates** — DNF/rpm-ostree pending update count
4. **SELinux Status** — enforcing mode + recent AVC denials (if any)
5. **Network Overview** — IP address, DNS servers, default gateway

## Affected Files

| File                             | Change                                                                                  |
| -------------------------------- | --------------------------------------------------------------------------------------- |
| `core/export/report_exporter.py` | Add 5 new `gather_*` methods + `gather_all_diagnostics()` + update HTML/Markdown export |
| `tests/test_report_exporter.py`  | New: comprehensive unit tests for all new methods                                       |
| `ROADMAP.md`                     | Add v2.3.0 entry                                                                        |
| `CHANGELOG.md`                   | Add v2.3.0 entry                                                                        |
| `memory-bank/activeContext.md`   | Update on completion                                                                    |
| `memory-bank/progress.md`        | Update on completion                                                                    |

## Design Decisions

- **No new UI tab**: Enhancement is in-place; `SystemInfoTab` export button already calls `save_report()`
- **Graceful degradation**: All new sections return empty/unknown if tools not available
- **Atomic Fedora support**: `gather_updates_info()` branches on `is_atomic()` from `SystemManager`
- **Timeouts**: All subprocess calls use `timeout=15` or shorter
- **Output size cap**: Journal errors capped at 20 lines, SELinux denials at 10 events

## HTML Report Structure (Enhanced)

```
<h1>System Report — Loofi Fedora Tweaks</h1>
<h2>System Information</h2>     ← existing
<h2>Failed Services</h2>        ← new (v2.3.0)
<h2>Recent Journal Errors</h2>  ← new (v2.3.0)
<h2>Pending Updates</h2>        ← new (v2.3.0)
<h2>SELinux Status</h2>         ← new (v2.3.0)
<h2>Network Overview</h2>       ← new (v2.3.0)
```

## Data Sources

| Section          | Command                                                                        |
| ---------------- | ------------------------------------------------------------------------------ |
| Failed Services  | `systemctl --failed --no-legend`                                               |
| Journal Errors   | `journalctl -p 3 -n 20 --no-pager --output=short`                              |
| Pending Updates  | `dnf check-update -q --assumeno` (traditional) or `rpm-ostree status` (atomic) |
| SELinux Status   | `getenforce` + `ausearch -m AVC -ts today -i 2>/dev/null \| tail -10`          |
| Network Overview | `ip -4 addr show` + `cat /etc/resolv.conf` + `ip route show default`           |
