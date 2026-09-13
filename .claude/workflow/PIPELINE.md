# Workflow Pipeline — v27.0.1 "Core"

Release work follows this sequence:

1. Align version metadata with `scripts/bump_version.py`.
2. Read the active `.workflow/specs/` task, architecture, and race-lock files.
3. Implement service/core logic before GUI, CLI, or packaging exposure.
4. Add deterministic tests with mocked host/system calls.
5. Run stabilization, adapter, release-doc, lint, type, test, coverage, RPM, and CLI smoke validation.
6. Publish only through the canonical master/tag release workflow and read back
   the GitHub release, COPR result, and wiki.

V27.0.1 is the current Fedora Maintenance Core release. The maintained
coverage gate is 85%; the repository-wide 90% target is explicitly deferred.
The supported distribution artifacts are the RPM and source distribution only:
there is no application Flatpak bundle, web API, background daemon, or custom
Polkit package in the current product surface. Navigation routes through
`core/navigation` and keeps the focused five-area sidebar.
