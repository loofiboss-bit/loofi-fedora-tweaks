# Loofi Fedora Tweaks — Workspace Instructions

Treat this file as the canonical, hand-maintained workspace instructions for the repository.
`.github/copilot-instructions.md` is generated and should stay a thin summary.

## Project at a glance

- Fedora-focused desktop control center built with Python 3.12+ and PyQt6.
- Main source root is `loofi-fedora-tweaks/`; set `PYTHONPATH=loofi-fedora-tweaks` for direct Python commands.
- Entry modes live in `loofi-fedora-tweaks/main.py`: GUI, `--cli`, `--daemon`, and `--web`.
- Canonical references:
  - `ARCHITECTURE.md` — structure, boundaries, critical patterns
  - `ROADMAP.md` — release scope and status
  - `docs/README.md` — documentation index
  - `.github/instructions/system_hardening_and_stabilization_guide.md` — safety and privilege rules

## Build and verify

Prefer the `Justfile` as the primary command surface.

- Run app: `just run`
- CLI example: `just cli info`
- Full tests: `just test`
- Single test file: `just test-file test_commands`
- Single test: `just test-method test_commands.py::TestPrivilegedCommandBuilders::test_dnf_install`
- Coverage: `just test-coverage`
- Lint: `just lint`
- Typecheck: `just typecheck`
- Full verification: `just verify`
- Build RPM: `just build-rpm`
- Release-doc validation: `just validate-release`
- Agent adapter drift: `just check-drift`

Useful raw equivalents:

- `PYTHONPATH=loofi-fedora-tweaks python3 loofi-fedora-tweaks/main.py`
- `PYTHONPATH=loofi-fedora-tweaks python -m pytest tests/ -v --tb=short`
- `flake8 loofi-fedora-tweaks/ --max-line-length=150 --ignore=E501,W503,E402,E722,E203`
- `mypy loofi-fedora-tweaks/ --ignore-missing-imports --no-error-summary`

## Architecture boundaries

See `ARCHITECTURE.md` for the full map. The rules that matter on almost every task are:

- `ui/*_tab.py`: PyQt6 widgets only. No `subprocess`, no business logic.
- `services/` and `core/`: domain logic. No PyQt imports.
- `utils/`: shared infrastructure, command helpers, errors, compatibility shims.
- `cli/main.py`: argument parsing and service calls only. Never import UI.
- Use `loofi-fedora-tweaks/ui/base_tab.py` and `utils/command_runner.py` for async GUI command flows.

Before release-scoped or workflow-scoped work, check:

- `.workflow/specs/.race-lock.json`
- `.workflow/specs/tasks-vX.Y.Z.md`
- `.workflow/specs/arch-vX.Y.Z.md`

## Critical conventions

- Never use `sudo`; use `pkexec` through `utils/commands.py`.
- Never use `shell=True`.
- Every subprocess call must include `timeout=...`.
- Always unpack `PrivilegedCommand` tuples before execution.
- Never hardcode `dnf`; use `SystemManager.get_package_manager()` and branch on `SystemManager.is_atomic()`.
- The real `SystemManager` implementation lives in `loofi-fedora-tweaks/services/system/system.py`.
- UI work must use `BaseTab`, `CommandRunner`, and `self.tr("...")` for user-facing strings.
- Use `%s` logging placeholders, not f-strings in log calls.
- Keep version changes synchronized across `loofi-fedora-tweaks/version.py`, `loofi-fedora-tweaks.spec`, and `pyproject.toml` via `scripts/bump_version.py`.
- Do not hardcode versions or codenames in tests.

## Testing conventions

- Tests are executed with `pytest`, but new tests should follow the repository’s `unittest` + `unittest.mock` style.
- Use `@patch` decorators, not patch context managers.
- Mock all system calls (`subprocess`, `shutil.which`, file I/O, OS probes, network access).
- For package operations, test both traditional Fedora and Atomic Fedora paths.
- Keep tests rootless and deterministic.
- See `.github/instructions/test.instructions.md` for the full testing contract.

## Exemplar files

- `loofi-fedora-tweaks/ui/base_tab.py` — base UI command-tab pattern
- `loofi-fedora-tweaks/ui/main_window.py` — plugin/sidebar/lazy-loading wiring
- `loofi-fedora-tweaks/utils/commands.py` — `PrivilegedCommand`, validation, audit logging
- `loofi-fedora-tweaks/services/system/system.py` — `SystemManager`, package-manager detection, caching
- `loofi-fedora-tweaks/cli/main.py` — CLI boundary patterns
- `tests/test_commands.py` — command-builder and patching style

## Link-first docs

Prefer linking to these instead of duplicating them in new instructions or prompts:

- `README.md` — product overview and quick start
- `docs/README.md` — documentation map
- `CONTRIBUTING.md` — contributor workflow
- `docs/PLUGIN_SDK.md` — plugin-specific work
- `docs/TROUBLESHOOTING.md` — operational issues
- `CHANGELOG.md` and `docs/releases/` — release history
- `.github/instructions/` — specialized repo rules by concern and file area

## Agent and customization notes

- Use the repo agents in `.github/agents/` and `.github/claude-agents/` for multi-step work.
- Keep new workspace instructions minimal and broadly applicable.
- Prefer file-specific instructions under `.github/instructions/` for narrow domains instead of growing this file.
