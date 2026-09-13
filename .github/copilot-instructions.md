# loofi-fedora-tweaks — Copilot Instructions

This is a thin repository adapter. `AGENTS.md` and `ARCHITECTURE.md` are the
canonical engineering instructions.

## Project

**loofi-fedora-tweaks** — Fedora Maintenance Core for Fedora KDE 44

Tech stack: Python + PyQt6

## Commands

- Test: `LOOFI_IPC_MODE=disabled QT_QPA_PLATFORM=offscreen just verify`
- Lint: `flake8 loofi-fedora-tweaks/ --max-line-length=150`
- Typecheck: `mypy loofi-fedora-tweaks/ --ignore-missing-imports --no-error-summary`
- Package: `just build-rpm` and `just build-sdist`

## Code Style

- Python 3.12+ with type hints
- Formatter: repository formatting conventions, line length 150
- Linter: flake8 (the canonical CI command)
- Use `logging` module, never `print()` in production code
- Docstrings: Google style
- Imports: stdlib → third-party → local, one blank line between groups

## Testing

- Framework: pytest
- Test files: `tests/` directory, `test_*.py` naming
- Use fixtures and parametrize for data-driven tests

## Commits

Format: `type(scope): description`
Types: feat, fix, refactor, docs, test, chore, ci, perf, revert, style
Scope: kebab-case, max 100 chars subject.

## Boundaries

- Keep `ui/` free of subprocesses and domain logic.
- Keep `core/` and `services/` free of PyQt imports.
- Route host mutations through Action Center review; never use `sudo` or
  `shell=True`.
- Do not reintroduce the retired web API, daemon, application Flatpak bundle,
  custom Polkit package, or unattended mutation surfaces.

## AI agents

See `AGENTS.md` and `.github/claude-agents/` for repository-specific guidance.
