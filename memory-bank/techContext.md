# Tech Context — Loofi Fedora Tweaks

## Tech Stack

| Component | Technology | Version |
|-----------|-----------|---------|
| Language | Python | 3.12+ |
| GUI Framework | PyQt6 | 6.7+ |
| API Framework | FastAPI | 0.128+ (optional) |
| API Server | Uvicorn | 0.30+ (optional) |
| Auth | PyJWT + bcrypt | (optional, for API) |
| HTTP Client | httpx | 0.27+ (optional) |
| OS | Fedora Linux | 43 |

## Dependencies

### Runtime (Required)

- `PyQt6 >= 6.7`
- `requests >= 2.31`

### Optional Groups

- `[api]`: FastAPI, Uvicorn, PyJWT, bcrypt, httpx, python-multipart
- `[dev]`: pytest, flake8, mypy, pytest-cov

## Development Setup

### Run the App

```bash
./run.sh                    # GUI mode (default)
./run.sh --cli              # CLI mode
./run.sh --daemon           # Daemon mode
./run.sh --api              # API mode
```

### Testing

```bash
PYTHONPATH=loofi-fedora-tweaks python -m pytest tests/ -v --tb=short          # Full suite
PYTHONPATH=loofi-fedora-tweaks python -m pytest tests/test_commands.py -v      # Single file
PYTHONPATH=loofi-fedora-tweaks python -m pytest tests/test_commands.py::TestPrivilegedCommandBuilders::test_dnf_install -v  # Single test
PYTHONPATH=loofi-fedora-tweaks python -m pytest tests/ --cov=loofi-fedora-tweaks --cov-report=term-missing --cov-fail-under=80  # Coverage
```

### Linting & Formatting

```bash
flake8 loofi-fedora-tweaks/ --max-line-length=150 --ignore=E501,W503,E402,E722,E203
mypy loofi-fedora-tweaks/ --ignore-missing-imports --no-error-summary
```

- **Formatter**: `black` (line-length 150)
- **Linter**: `ruff` (target py312, line-length 150)
- **Style**: Google-style docstrings, `%s` log formatting (never f-strings in log calls)

### Building

```bash
bash scripts/build_rpm.sh           # Build RPM
python scripts/bump_version.py      # Version bump (cascades to version.py + .spec + pyproject.toml + release notes)
```

## Technical Constraints

- **Fedora-only**: App uses `dnf`, `systemctl`, `firewall-cmd`, `rpm-ostree`, and other Fedora-specific tools
- **No root tests**: All tests mock system calls — CI runs without privileges
- **80% coverage gate**: CI enforces minimum 80% test coverage
- **pkexec only**: Never use `sudo` — always `pkexec` via `PrivilegedCommand`
- **Subprocess timeouts**: Every `subprocess.run()` / `check_output()` must have `timeout=N`
- **Never `shell=True`**: Always list-based subprocess args
- **Never hardcode `dnf`**: Use `SystemManager.get_package_manager()`
- **Never hardcode versions in tests**: Use dynamic assertions (non-empty, semver format)

## CI/CD

- **Test gate**: 80% coverage minimum
- **Stabilization rules**: Block hardcoded version/codename assertions
- **Docs gate**: Block hardcoded version assertions in docs
- **Security scanner**: `bandit` (skips B103, B104, B108, B310, B404, B603, B602)

## Version Sync

Three files must always match — use `scripts/bump_version.py`:

1. `loofi-fedora-tweaks/version.py` — `__version__`, `__version_codename__`
2. `loofi-fedora-tweaks.spec` — `Version:`
3. `pyproject.toml` — `version`

## Distribution Channels

| Channel | Config | Status |
|---------|--------|--------|
| RPM/COPR | `loofi-fedora-tweaks.spec` | Active |
| Flatpak | `org.loofi.FedoraTweaks.yml` | Available |
| AppImage | `build_flatpak.sh` (also covers AppImage) | Available |
| Direct install | `install.sh` | Available |
| Systemd service | `loofi-fedora-tweaks.service` | Available |
