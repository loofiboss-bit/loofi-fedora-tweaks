# Contributing Guide — v28.0.2 "Ease"

Thank you for contributing to Loofi Fedora Tweaks! This project prioritizes stability, verifiable operations, and defensive security.

---

## 1. Development Setup

Clone the repository and set up a virtual environment:

```bash
git clone https://github.com/loofiboss-bit/loofi-fedora-tweaks.git
cd loofi-fedora-tweaks
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev]'
```

Run the application locally from the source tree:

```bash
# Launch GUI
PYTHONPATH=loofi-fedora-tweaks python3 loofi-fedora-tweaks/main.py

# Launch CLI in JSON mode
PYTHONPATH=loofi-fedora-tweaks python3 loofi-fedora-tweaks/main.py --cli --json info
```

---

## 2. Pre-Commit Quality Checks

Before submitting a pull request, ensure all local validation commands succeed:

```bash
# Run full unit and integration test suite offscreen
LOOFI_IPC_MODE=disabled QT_QPA_PLATFORM=offscreen just test

# Run linter and type checker
just lint
just typecheck

# Execute comprehensive verification suite
LOOFI_IPC_MODE=disabled QT_QPA_PLATFORM=offscreen just verify

# Validate RPM packaging and release docs
just check-packaging
python3 scripts/check_release_docs.py
python3 scripts/sync_wiki_docs.py --check
```

---

## 3. Core Architectural Rules

All contributions must respect the established repository boundaries:

1. **No Direct Subprocesses in `ui/`**: UI classes handle presentation and signals only. System commands belong in `services/` or `core/actions/`.
2. **No Shell Invocations**: Use argument lists (`list[str]`) for subprocesses. Never pass `shell=True` or unescaped strings to execution runners.
3. **No Root GUI**: The GUI runs strictly unprivileged. Never prompt the user to run the application with `sudo`.
4. **Action Center Gate**: Any operation that modifies the host system must be structured as an Action Center definition with preflight checks, explicit authorization, and independent post-execution verification.
5. **Fail Closed**: If a platform, desktop environment, or hardware capability cannot be verified, mark it as unavailable rather than falling back to guessing.

---

## 4. Documentation & Release Standards

- Whenever adding or modifying CLI options or actions, update the corresponding documentation files in `docs/` and `wiki/`.
- Ensure all CLI examples in Markdown documentation parse against `cli/parser.py`.
- Run `python3 scripts/sync_wiki_docs.py` to keep mirrored guides in sync.

