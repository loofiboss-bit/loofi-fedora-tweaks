# Workflow Quickstart

This repository uses `.workflow/specs/` as the active release planning area.

For v8.0.0 Beacon work:

- Read `.workflow/specs/.race-lock.json` before release-scoped edits.
- Keep route IDs in `core/navigation` as the canonical persisted navigation surface.
- Use `docs/README.md`, `CHANGELOG.md`, and `ROADMAP.md` as active documentation indexes.
- Run `just verify` or the explicit validation commands from `docs/RELEASE_CHECKLIST.md` before release.
- Keep Fedora KDE 44 as the supported target and Fedora 45 as preview-only advisory context.
