# Loofi Fedora Tweaks

## What This Is

Loofi Fedora Tweaks is a Fedora-focused desktop control center built with Python 3.12+ and PyQt6. It exposes the same system-management surface through GUI, CLI, daemon, and headless Web API entrypoints, with strict privilege controls and Atomic Fedora awareness.

## Core Value

Provide a safe, trustworthy Fedora administration surface whose documentation, workflow metadata, and runtime behavior agree with each other.

## Requirements

### Validated

- ✓ Desktop control center for Fedora system management across GUI, CLI, daemon, and Web API entrypoints — existing repository surface
- ✓ Privileged actions use `pkexec`, typed errors, and timeout-enforced subprocess calls — existing repository conventions
- ✓ Workflow metadata under `.workflow/` drives current-release and release-readiness decisions — existing release process

### Active

- [ ] Restore one authoritative release story across roadmap, workflow metadata, README/docs, and architecture references
- [ ] Remove or replace stale references to nonexistent workflow report artifacts
- [ ] Add validation coverage so release/documentation drift fails fast in tests and scripts

### Out of Scope

- Runtime feature expansion — this slice is documentation/workflow hardening only
- Privilege-model changes or new daemon/API capabilities — stabilization rule
- Renaming runtime flags such as `--web` to `--api` — command-surface changes are deferred
- Broad documentation rewrite outside authoritative entrypoints and directly referenced release artifacts — keep scope bounded

## Context

The repository already tracks an active workflow target of `v2.13.0 "Alignment"` in top-level `ROADMAP.md` and `.workflow/specs/.race-lock.json`, while runtime version files remain `2.11.0` and the latest documented release note in repo is `v2.12.0`. Current drift includes stale README release branding, a broken latest-release index in `docs/releases/RELEASE_NOTES.md`, an outdated architecture banner, and release notes that cite missing `.workflow/reports/*.json` files.

## Constraints

- **Tech stack**: Python 3.12+, PyQt6, Fedora Linux — stay aligned with repository conventions
- **Workflow truth**: `.workflow/specs/.race-lock.json` and top-level `ROADMAP.md` are authoritative for active slice tracking — docs must consume, not override, that truth
- **Runtime safety**: No new privilege scope, no `sudo`, no `shell=True`, all subprocess calls remain timeout-enforced — stabilization rules are mandatory
- **Evidence integrity**: Missing workflow artifacts must be corrected or the docs narrowed; never fabricate evidence

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Plan the next update around the active `v2.13.0 Alignment` slice | Top-level roadmap and race-lock already identify it as the current stabilization target | ✓ Good |
| Treat workflow metadata, latest documented release, and packaged runtime version as separate facts | The repo currently has `v2.13.0` active, `v2.12.0` documented, and `2.11.0` in version files | ✓ Good |
| Keep the actual runtime API flag as `--web` in this slice | `loofi-fedora-tweaks/main.py` and service/unit files expose `--web` today | ✓ Good |
| Prefer narrowing stale release-note claims over inventing missing `v2.12.0` report files | `scripts/generate_workflow_reports.py` only emits the current runtime version by default | ✓ Good |

---
*Last updated: 2026-04-10 after GSD planning bootstrap for the active alignment slice*
