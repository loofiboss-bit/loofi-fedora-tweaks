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

| Era | Versions | Theme |
|-----|----------|-------|
| Legacy (integer) | v21–v50 | UX, architecture, plugins, stabilization, hardening |
| SemVer | v1.0.0 | Version renormalization |
| SemVer | v2.0.0 "Evolution" | Service layer migration |

52 total versions shipped.

## What's Left to Build

### Immediate (Release Closure)

- [ ] Fix v2.0.0 tag conflict (old pre-SemVer tag vs new release)
- [ ] Update race-lock status from `active` → `done`

### Planning Required

- [ ] Define next version scope in ROADMAP.md (v2.1.0 or v3.0.0)
- [ ] Identify remaining stabilization gaps or new feature candidates

## Current Status

**v2.0.0 "Evolution"**: ✅ COMPLETE — all 12 tasks done, codebase clean, tests passing.

**Project state**: Stable baseline, between releases. All stabilization phases complete — new features are now unblocked.

## Known Issues

1. **Tag conflict**: Old pre-SemVer `v2.0.0` tag points to legacy commit `4933073`, not the current Evolution release
2. **Race-lock stale**: `.workflow/specs/.race-lock.json` still shows `active` for v2.0.0 despite completion
3. **No next version**: ROADMAP.md has no planned work after v2.0.0
