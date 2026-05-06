# Workflow Quickstart

This repository uses `.workflow/specs/` as the active release planning area.

For v7.0.0 Aegis work:

- Read `.workflow/specs/.race-lock.json` before release-scoped edits.
- Use `docs/README.md`, `CHANGELOG.md`, and `ROADMAP.md` as active documentation indexes.
- Run `just verify` or the explicit validation commands from `docs/RELEASE_CHECKLIST.md` before release.
- Keep Fedora KDE 44 as the supported target and Fedora 45 as preview-only advisory context.
