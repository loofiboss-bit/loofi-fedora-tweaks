# Contributing to Loofi Fedora Tweaks

Thanks for contributing.

This guide focuses on how to make safe, reviewable changes that match project conventions.

---

## Development Setup

```bash
git clone https://github.com/loofiboss-bit/loofi-fedora-tweaks.git
cd loofi-fedora-tweaks
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev]'
```

Run from source:

```bash
PYTHONPATH=loofi-fedora-tweaks python3 loofi-fedora-tweaks/main.py
```

CLI mode:

```bash
PYTHONPATH=loofi-fedora-tweaks python3 loofi-fedora-tweaks/main.py --cli info
```

---

## Project Architecture (Current)

High-level layout:

- `loofi-fedora-tweaks/ui/` - PyQt6 tabs and window components
- `loofi-fedora-tweaks/core/` and `services/` - domain logic and system services
- `loofi-fedora-tweaks/core/product_catalog.py` - canonical product metadata
- `loofi-fedora-tweaks/core/plugins/` - built-in page-provider compatibility views
- `loofi-fedora-tweaks/cli/main.py` - CLI entrypoint
- `loofi-fedora-tweaks/services/` - service layer components
- `tests/` - unit tests with mocks

The UI is catalog-driven. External Python plugins are retired and must not be
reintroduced as an executable extension boundary.

---

## Critical Engineering Rules

1. Never use `sudo` in application command execution paths; use `pkexec` via command helpers.
2. Never hardcode `dnf`; use package manager detection (`dnf` vs `rpm-ostree`).
3. Never call subprocesses directly from UI or alternate entrypoints.
4. Classify every operation as `host`, `app_state`, `session`, or `manual_only`.
5. Route every host mutation through `ActionCenterOrchestrator`; background
   services may create plans but may not confirm or execute them.
6. Always unpack privileged operation tuples before execution.
7. Keep version values synchronized with `scripts/bump_version.py`.

---

## Coding Standards

- Prefer existing patterns over new abstractions.
- Keep changes minimal and targeted.
- New UI surfaces should follow `BaseTab` and product-catalog conventions.
- Keep user-visible strings translatable (`self.tr("...")`) in UI code.
- Avoid introducing root-required tests or environment-coupled behavior.

---

## Testing Requirements

Run tests before opening a PR:

```bash
just verify
```

Testing expectations:

- Mock all system calls (`subprocess`, filesystem, command discovery).
- Cover both success and failure paths.
- Prefer `@patch` decorators in unittest-style tests.

---

## Lint and Build

Lint:

```bash
just lint
```

Build RPM:

```bash
just build-rpm
```

---

## Pull Request Workflow

1. Create a topic branch from `master`.
2. Keep commits scoped (for example docs-only or tests-only).
3. Update docs for behavioral changes (`README`, user guide, release notes/changelog as needed).
4. Include test evidence in the PR description.
5. Link related issues.

Recommended commit style:

- `fix: ...`
- `feat: ...`
- `docs: ...`
- `test: ...`

---

## Reporting Bugs and Requesting Features

Use GitHub issues:

- Bugs: include reproduction steps, expected/actual behavior, logs, environment.
- Features: include user problem, proposed UX/CLI behavior, and constraints.

Issue tracker: <https://github.com/loofiboss-bit/loofi-fedora-tweaks/issues>
