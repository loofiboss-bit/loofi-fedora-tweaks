# Tasks — v5.0.0 "Aurora"

## Contract

- [x] ID: T1 | Files: version.py, pyproject.toml, spec, docs | Dep: none | Agent: Planner | Description: Align v5.0.0 Aurora metadata
  Acceptance: Runtime, packaging, changelog, roadmap, release notes, and active docs identify v5.0.0 "Aurora"
  Docs: README.md, CHANGELOG.md, ROADMAP.md, docs/releases/RELEASE-NOTES-v5.0.0.md
  Tests: scripts/check_release_docs.py

- [x] ID: T2 | Files: core/diagnostics, services/desktop, services/package | Dep: T1 | Agent: Builder | Description: Implement Fedora KDE 44 readiness diagnostics
  Acceptance: Read-only checks cover Fedora, KDE/Qt, session, display manager, DNF5, PackageKit, repos, Atomic, NVIDIA, Flatpak, and TLS
  Docs: docs/FEDORA_KDE_44_READINESS.md
  Tests: tests/test_fedora44_readiness.py

- [x] ID: T3 | Files: ui, cli | Dep: T2 | Agent: Sculptor | Description: Expose readiness in dashboard and CLI
  Acceptance: Dashboard card opens a focused detail view; CLI supports `fedora44-readiness [--advanced]` and global `--json`
  Docs: docs/USER_GUIDE.md, docs/BEGINNER_QUICK_GUIDE.md
  Tests: tests/test_fedora44_readiness.py, tests/test_v4_ui.py

- [x] ID: T4 | Files: core/export, utils/journal, ui/support_bundle_wizard.py | Dep: T2 | Agent: Builder | Description: Extend support bundle to v3
  Acceptance: Bundle includes privacy-masked Fedora KDE 44 diagnostics and existing ZIP export embeds the v3 payload
  Docs: docs/FEDORA_KDE_44_READINESS.md
  Tests: tests/test_fedora44_readiness.py

- [x] ID: T5 | Files: loofi-fedora-tweaks.spec, workflows | Dep: T1 | Agent: Packager | Description: Update Fedora 44 packaging and split optional runtime deps
  Acceptance: Active COPR targets use Fedora 44; API and daemon dependencies are in optional RPM subpackages
  Docs: docs/releases/RELEASE-NOTES-v5.0.0.md
  Tests: tests/test_fedora44_readiness.py packaging assertions
