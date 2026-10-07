# Loofi Fedora Tweaks — Justfile
# Unified command interface for humans and AI agents.
# Run `just --list` to see all available commands.
#
# Install just: pkexec dnf install just

# Default: show available commands
default:
    @just --list --unsorted

# === Configuration ===

# Project paths
src_root := "loofi-fedora-tweaks"
test_dir := "tests"

# Thresholds (single source of truth — CI workflows read these)
# V27 gates the maintained Fedora Maintenance Core at 85%. The planned
# 90% repository-wide target is deferred to the next release; the complete
# test suite still runs every compatibility module.
coverage_min := "85"
max_line_length := "150"
flake8_ignore := "E501,W503,E402,E722,E203"

# ============================================================
#  Development
# ============================================================

# Run the application (GUI mode)
run:
    @echo "Starting Loofi Fedora Tweaks..."
    PYTHONPATH={{src_root}} python3 {{src_root}}/main.py

# Run the application in CLI mode
cli *ARGS:
    PYTHONPATH={{src_root}} python3 {{src_root}}/main.py --cli {{ARGS}}

# ============================================================
#  Testing
# ============================================================

# Run full test suite
test *ARGS:
    PYTHONPATH={{src_root}} python -m pytest {{test_dir}}/ -v --tb=short {{ARGS}}

# Run a single test file (e.g., just test-file test_commands)
test-file FILE:
    PYTHONPATH={{src_root}} python -m pytest {{test_dir}}/{{FILE}}.py -v

# Run a single test method (e.g., just test-method test_commands::TestClass::test_method)
test-method PATH:
    PYTHONPATH={{src_root}} python -m pytest {{test_dir}}/{{PATH}} -v

# Run tests with coverage report
test-coverage:
    PYTHONPATH={{src_root}} python -m pytest {{test_dir}}/ -v \
        --cov={{src_root}} \
        --cov-report=term-missing \
        --cov-fail-under={{coverage_min}}

# Run tests in Linux via WSL (optional alternative backend)
test-linux-wsl *ARGS:
    pwsh -File scripts/run_linux_tests.ps1 -Backend wsl -TestArgs "{{ARGS}}"

# Run tests in Linux via Docker (primary backend)
test-linux-docker *ARGS:
    pwsh -File scripts/run_linux_tests.ps1 -Backend docker -TestArgs "{{ARGS}}"

# Auto-select Docker first, WSL fallback
test-linux *ARGS:
    pwsh -File scripts/run_linux_tests.ps1 -Backend auto -TestArgs "{{ARGS}}"

# Run tests and output JUnit XML (for CI)
test-ci:
    PYTHONPATH={{src_root}} python -m pytest {{test_dir}}/ -v --tb=short \
        --cov={{src_root}} \
        --cov-report=term-missing \
        --cov-fail-under={{coverage_min}} \
        --junitxml=test-results.xml

# ============================================================
#  Code Quality
# ============================================================

# Lint with flake8
lint:
    if [ -x .venv/bin/flake8 ]; then .venv/bin/flake8 {{src_root}}/ --max-line-length={{max_line_length}} --ignore={{flake8_ignore}}; else flake8 {{src_root}}/ --max-line-length={{max_line_length}} --ignore={{flake8_ignore}}; fi

# Type check with mypy
typecheck:
    if [ -x .venv/bin/mypy ]; then MYPYPATH={{src_root}} .venv/bin/mypy {{src_root}}/ --ignore-missing-imports --no-error-summary; else MYPYPATH={{src_root}} mypy {{src_root}}/ --ignore-missing-imports --no-error-summary; fi

# Run pre-commit hooks on all files
pre-commit:
    pre-commit run --all-files

# Full verification (lint + typecheck + tests + coverage)
verify:
    @echo "=== Lint ==="
    just lint
    @echo ""
    @echo "=== Type Check ==="
    just typecheck
    @echo ""
    @echo "=== Architecture ==="
    just validate-architecture
    @echo ""
    @echo "=== Product catalog and version ==="
    just check-product-catalog
    @echo ""
    @echo "=== Tests + Coverage ==="
    just test-coverage
    @echo ""
    @echo "=== All checks passed ==="

# ============================================================
#  Build & Package
# ============================================================

# Build RPM package
build-rpm:
    bash scripts/build_rpm.sh

# Build source distribution
build-sdist:
    bash scripts/build_sdist.sh

# Build AppImage
build-appimage:
    bash scripts/build_appimage.sh

# Build all packages
build-all: build-rpm build-sdist

# ============================================================
#  Quality Gates
# ============================================================

# Code-rule checks (stabilization rules + architecture boundaries)
validate-architecture:
	PYTHONPATH=loofi-fedora-tweaks python3 scripts/check_stabilization_rules.py
	PYTHONPATH=loofi-fedora-tweaks python3 scripts/validate_architecture.py

# Keep generated catalog documentation and active version sources in sync
check-product-catalog:
    python3 scripts/gen_tweaks_doc.py --check
    python3 scripts/bump_version.py --check

# Validate pyproject package metadata and wheel/sdist contents
check-packaging:
    python3 scripts/sync_requirements.py --check
    PYTHONPATH={{src_root}} python3 scripts/check_packaging_manifest.py --build

# ============================================================
#  Version Management
# ============================================================

# Show current version
version:
    @python3 -c "import sys; sys.path.insert(0, '{{src_root}}'); from version import __version__, __version_codename__; print(f'{__version__} \\"{__version_codename__}\\"')"

# ============================================================
#  Release
# ============================================================

# Full release preparation (verify + architecture + packaging)
release-prep: verify validate-architecture check-packaging
    @echo "Release preparation complete."

# ============================================================
#  Utilities
# ============================================================

# Clean build artifacts and caches
clean:
    rm -rf build/ dist/ *.egg-info __pycache__
    rm -rf .pytest_cache .mypy_cache .coverage htmlcov
    rm -f test-results.xml
    find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
    @echo "Cleaned."
