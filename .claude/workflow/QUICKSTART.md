# Workflow Quickstart

This repository uses `.workflow/specs/` as the active release planning area.

For v5.0.0 Aurora work:

- Read `.workflow/specs/.race-lock.json` before release-scoped edits.
- Use `docs/README.md`, `CHANGELOG.md`, and `ROADMAP.md` as active documentation indexes.
- Run `just verify` or the explicit validation commands from `docs/RELEASE_CHECKLIST.md` before release.
- Keep Fedora KDE 44 as the supported target and Fedora 43 as best-effort compatible.
