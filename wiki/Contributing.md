# Contributing — v27.0.1 "Core"

## Development setup

```bash
git clone https://github.com/loofiboss-bit/loofi-fedora-tweaks.git
cd loofi-fedora-tweaks
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev]'
```

Run the GUI or reduced CLI from the source tree:

```bash
PYTHONPATH=loofi-fedora-tweaks python3 loofi-fedora-tweaks/main.py
PYTHONPATH=loofi-fedora-tweaks python3 loofi-fedora-tweaks/main.py --cli --json info
```

## Before opening a pull request

```bash
LOOFI_IPC_MODE=disabled QT_QPA_PLATFORM=offscreen just verify
just check-packaging
just validate-release
just check-drift
```

The full test suite must pass with no failures. Keep coverage claims tied to
the maintained V27 surface (85% blocking gate); do not claim repository-wide
90% until it is measured and gated in a later release.

## Architecture rules

- Keep contracts, policy, persistence, and Action Center orchestration in
  `core/`.
- Keep host probes and adapters PyQt-free in `services/` or `utils/`.
- Keep subprocesses and mutation authority out of `ui/`.
- Keep `cli/` bounded, typed, and independent of UI imports.
- Add every persistent host change as a closed Action Center definition with
  fresh preflight, explicit confirmation, bounded execution, and independent
  verification.
- Treat unknown Fedora desktop/session/backend capability as unavailable.

Do not add a daemon, local Web API, external plugin execution, custom policy
file, Flatpak distribution bundle, automatic reboot, retry, rollback, or
unattended scheduler to the Core surface.

## Documentation

Update the README banner, active guides, release notes, AppStream metadata,
roadmap, and wiki mirrors when behavior or version changes. Historical pages
must be labeled as historical rather than reused as current instructions.
