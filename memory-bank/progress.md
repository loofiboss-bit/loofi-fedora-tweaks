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

| Era              | Versions           | Theme                                               |
| ---------------- | ------------------ | --------------------------------------------------- |
| Legacy (integer) | v21–v50            | UX, architecture, plugins, stabilization, hardening |
| SemVer           | v1.0.0             | Version renormalization                             |
| SemVer           | v2.0.0 "Evolution" | Service layer migration                             |

52 total versions shipped.

## What's Left to Build

### Active (v2.1.0 Continuity)

- [x] Activate v2.1.0 cycle in roadmap and workflow specs
- [ ] Reconcile memory-bank and self-maintaining trackers with canonical workflow state
- [ ] Implement smart adapter re-render in `scripts/sync_ai_adapters.py`
- [ ] Integrate prev-stats snapshot and render cascade in `scripts/bump_version.py`
- [ ] Enforce blocking adapter/stats drift checks in CI

### Upcoming (Post-Continuity)

- [ ] Define next feature-focused scope after continuity tasks are complete
- [ ] Prioritize candidate enhancements using v2.1 outcome as baseline

## Current Status

**v2.0.0 "Evolution"**: ✅ COMPLETE — all 12 tasks done, codebase clean, tests passing.

**v2.1.0 "Continuity"**: 🚧 ACTIVE — workflow and automation continuity tasks in progress.

**Project state**: Stable baseline with active continuity cycle. All stabilization phases remain complete.

## Known Issues

1. **Tracker drift**: `.self-maintaining-progress.md` contains legacy path/phase context that must match v2.1 canonical workflow
2. **Automation gap**: Adapter sync smart re-render is defined but not yet implemented
3. **Pipeline coupling gap**: Stats snapshot and adapter render are not yet fully integrated in version bump flow
