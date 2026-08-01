# Tasks — v23.1.0 "Compass"

## Contract

- [x] ID: T1 | Files: `loofi-fedora-tweaks/core/public_operations.py`,
  `loofi-fedora-tweaks/cli/`, `loofi-fedora-tweaks/api/`,
  `tests/test_v20_mutation_boundary.py` | Dep: none | Agent: Engineer |
  Description: Inventory every public operation and close direct host mutation
  paths behind Action Center plans or safe manual guidance.
  Acceptance: The machine-readable registry covers every public CLI and API
  leaf, and the boundary gate reports zero direct public host mutations.
  Docs: `ARCHITECTURE.md`, `docs/VERIFIED_MAINTENANCE.md`
  Tests: `tests/test_v20_mutation_boundary.py`
- [x] ID: T2 | Files: active documentation, wiki mirrors, desktop metadata,
  release-document checks | Dep: T1 | Agent: Engineer | Description: Make
  active product copy, examples, navigation, and documentation match v23.1.0.
  Acceptance: Current docs contain no stale flow, placeholder, device-specific
  copy, unsafe mutation example, broken internal link, or wiki drift.
  Docs: `README.md`, `docs/README.md`, `wiki/Getting-Started.md`
  Tests: `tests/test_release_doc_check.py`
- [x] ID: T3 | Files: Home, Updates, Install App, Troubleshoot, Cleanup,
  Action Center, Settings, and shell UI modules | Dep: T1,T2 | Agent: Engineer |
  Description: Deliver one plain-language, state-led core workflow journey.
  Acceptance: Core tasks are reachable within two navigation actions, plans
  remain review-first, and responsive, keyboard, RTL, high-contrast, and scale
  contracts remain enforced.
  Docs: `docs/USER_GUIDE.md`, `docs/images/user-guide/README.md`
  Tests: `tests/test_v23_1_phase3_ui.py`
- [x] ID: T4 | Files: `loofi-fedora-tweaks/cli/parser_domains/`,
  `loofi-fedora-tweaks/cli/main.py`, `loofi-fedora-tweaks/ui/main_window.py` |
  Dep: T3 | Agent: Engineer | Description: Split parser registration and window
  setup into named responsibilities without changing public commands, routes,
  startup order, or lazy loading.
  Acceptance: Parser compatibility and MainWindow structure tests pass with no
  new eager system probes.
  Docs: `ARCHITECTURE.md`
  Tests: `tests/test_cli_parser_contract.py`, `tests/test_main_window.py`
- [x] ID: T5 | Files: version metadata, release notes, changelog, AppStream,
  workflow specs, privacy-safe screenshots | Dep: T1,T2,T3,T4 | Agent: Release
  Engineer | Description: Bind the qualified implementation to v23.1.0 and
  prepare the canonical exact-tag release pipeline.
  Acceptance: Version sync, release docs, full verification, packaging, and
  Fedora 44 KDE Wayland screenshot gates pass from the release commit.
  Docs: `CHANGELOG.md`, `docs/releases/RELEASE-NOTES-v23.1.0.md`
  Tests: `just release-prep`, `just build-rpm`
- [ ] [post-publish] Publish and independently verify the exact v23.1.0 tag,
  GitHub assets and attestations, CI and CodeQL, COPR packages and signatures,
  clean Fedora 44 installation, public docs and wiki, and final repository
  state.
