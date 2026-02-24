# Progress — Loofi Fedora Tweaks

## What Works

### Application

- 28 feature tabs across 7 categories (System, Hardware, Network, Desktop, Security, Software, Advanced)
- 4 entry modes: GUI, CLI (`--cli`), Daemon (`--daemon`), API (`--api`)
- Lazy tab loading for fast startup
- Plugin marketplace with sandboxing, ratings, reviews, hot-reload
- Experience levels (Beginner/Intermediate/Expert)
- Guided tour and onboarding wizard
- Health score dashboard with timeline and diagnostics
- Abyss (dark) and Light themes
- Command palette for quick actions
- Dangerous operation confirmation dialogs with safety snapshots
- Ansible export, kickstart generation, report export
- AI agent runtime with planning and scheduling

### Infrastructure

- 228+ test files, 6383+ tests, 81%+ coverage (80% CI-enforced)
- RPM packaging via COPR (`loofitheboss/loofi-fedora-tweaks`)
- Flatpak and AppImage distribution
- Systemd service for daemon mode
- Polkit policy for privilege escalation
- CI pipeline with coverage gate, stabilization rules, docs gate, bandit security scanner
- Structured service layer (9 domains) + core layer (8 domains)
- All 6 stabilization/hardening phases complete

### Version History Summary

| Era              | Versions            | Theme                                                 |
| ---------------- | ------------------- | ----------------------------------------------------- |
| Legacy (integer) | v21–v50             | UX, architecture, plugins, stabilization, hardening   |
| SemVer           | v1.0.0              | Version renormalization                               |
| SemVer           | v2.0.0 "Evolution"  | Service layer migration                               |
| SemVer           | v2.1.0 "Continuity" | Workflow realignment, adapter sync, CI drift gates    |
| SemVer           | v2.2.0 "Velocity"   | Performance caching, subprocess safety, service tests |
| SemVer           | v2.2.1 (patch)      | CI stability: @patch target fixes                     |
| SemVer           | v2.2.2 (patch)      | CI: coverage threshold 77%, tasks spec gate           |
| SemVer           | v2.3.0 "Insight"    | Enhanced diagnostics: 5 new report sections           |

56 total versions shipped.

## What's Left to Build

### Upcoming (v2.4.0 — unplanned)

- [ ] Define next version scope and activate in ROADMAP.md
- [ ] Candidate areas: new Fedora-specific feature tabs, coverage push to 85%+
- [ ] Create workflow specs (tasks-v2.4.0.md, arch-v2.4.0.md)
- [ ] Update race-lock to new active version

## Current Status

**v2.3.0 "Insight"**: ✅ COMPLETE — enhanced diagnostics: 5 gather methods + 33 tests.
**v2.2.2 (patch)**: ✅ COMPLETE — CI stability fix (coverage threshold 77%, tasks spec gate).
**v2.2.1 (patch)**: ✅ COMPLETE — @patch target corrections for CI stability.
**v2.2.0 "Velocity"**: ✅ COMPLETE — performance caching, subprocess safety, service-layer tests.
**v2.1.0 "Continuity"**: ✅ COMPLETE — workflow realignment, adapter sync, CI drift gates in place.

**Project state**: Clean, stable, all stabilization phases complete. Awaiting v2.3.0 planning.

## Known Issues

(none)
