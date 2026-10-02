# Tasks — v31.0.0 "Mastery"

Baseline: v30.2.1 commit `f4a71a9`. Local implementation, verification,
and RPM/source artifacts are authorized. A subsequent user request authorizes
commit, push, and pull request creation. Public release remains v30.2.1 until
formal publication.

## Implementation

- [x] ID: T1 | Files: `core/tweak_commands.py`, `core/tasks/tweaks.py`, `core/actions/tweaks.py`, `core/actions/catalog.py`, `core/execution_policy.py` | Dep: none | Agent: Codex | Description: Expand tweak catalog to 22 controls across GNOME, KDE, and DNF5.
  Acceptance: GNOME schemas mapped dynamically, KDE specs registered, DNF parallel downloads privileged execution and read-only config dump supported, all action IDs registered in ACTIVE_ACTION_IDS.
  Docs: `docs/releases/RELEASE-NOTES-v31.0.0.md`
  Tests: `tests/test_v31_tweak_catalog.py`, `tests/test_tweaks_v30_1.py`, `tests/test_tweaks_v30_2.py`

- [x] ID: T2 | Files: `cli/parser_domains/tweaks.py`, `cli/parser_domains/apps.py`, `cli/commands/tweaks_commands.py`, `cli/commands/apps_commands.py`, `cli/parser.py`, `cli/main.py` | Dep: T1 | Agent: Codex | Description: Implement CLI parity for tweaks and apps domains.
  Acceptance: Full CLI subcommands (`tweaks list/get/set/restore`, `apps list/install`), table formatting, machine JSON mode, dry-run support, and updated CLI parser regression digest.
  Docs: `docs/USER_GUIDE.md`
  Tests: `tests/test_v31_cli_parity.py`, `tests/test_cli_parser_contract.py`, `tests/test_v27_cli.py`

- [x] ID: T3 | Files: `core/actions/catalog.py` | Dep: none | Agent: Codex | Description: Dynamic package manager resolution for clean-all actions.
  Acceptance: Replaced hardcoded `dnf5` calls in `_render_dnf_clean` and `_verify_dnf_clean` with `runtime.package_manager()`.
  Docs: `.workflow/specs/arch-v31.0.0.md`
  Tests: `tests/test_action_catalog.py`, `tests/test_v31_tweak_catalog.py`

- [x] ID: T4 | Files: `core/tasks/applications.py` | Dep: none | Agent: Codex | Description: Expand curated application catalog.
  Acceptance: Added Flatseal, Mission Center, Spotify, and Neovim with complete metadata and source labels.
  Docs: `docs/releases/RELEASE-NOTES-v31.0.0.md`
  Tests: `tests/test_v31_cli_parity.py`

- [x] ID: T5 | Files: `ui/tweaks_page.py` | Dep: T1 | Agent: Codex | Description: Hide empty group cards during UI search filtering.
  Acceptance: Category cards dynamically hide when all child rows are filtered out by search needle.
  Docs: `docs/USER_GUIDE.md`
  Tests: `tests/test_tweaks_v30_1.py`

- [x] ID: T6 | Files: `version.py`, `pyproject.toml`, `loofi-fedora-tweaks.spec`, documentation and specs | Dep: T1-T5 | Agent: Codex | Description: Version bump to 31.0.0 and documentation synchronization.
  Acceptance: Version files synchronized, release notes and changelogs authored, all release documentation checks passing.
  Docs: `README.md`, `ROADMAP.md`, `CHANGELOG.md`, `docs/releases/RELEASE-NOTES-v31.0.0.md`
  Tests: `scripts/check_release_docs.py`, `scripts/check_stabilization_rules.py`

## Local Qualification

- [x] ID: Q1 | Files: test suite and release documentation | Dep: T1-T6 | Agent: Codex | Description: Run full automated verification and check gates.
  Acceptance: `just verify` passes with >=85% test coverage, release docs check passes, project stats verified.
  Docs: `docs/releases/RELEASE-NOTES-v31.0.0.md`
  Tests: `just verify`, `python3 scripts/check_release_docs.py`
