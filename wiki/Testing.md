# Testing & Quality Assurance — v28.0.2 "Ease"

Loofi Fedora Tweaks enforces strict quality gates to guarantee system safety and prevent regressions before any code is merged or published.

---

## 1. Automated Test Suite Metrics (v28.0.2)

- **Test Suite Results**: 4,804 passed, 73 skipped, 0 failures.
- **Code Coverage**: 86.64% line coverage across the maintained core (blocking CI gate is 85%).
- **Automated Validation**: Static typing (`mypy`), linting (`flake8`), architecture boundaries, packaging validation, and documentation link checks all pass cleanly.
- **Evidence Boundaries**: Headless/offscreen tests prove logic, command construction, and catalog contracts. Physical display server integration, hardware battery controllers, and Polkit agents are verified through manual qualification gates.

---

## 2. Running Tests Locally

Run the test suite using `just`:

```bash
# Run complete test suite with headless offscreen display
LOOFI_IPC_MODE=disabled QT_QPA_PLATFORM=offscreen just test

# Run a specific test file
just test-file test_product_catalog

# Run tests with code coverage check
LOOFI_IPC_MODE=disabled QT_QPA_PLATFORM=offscreen just test-coverage
```

---

## 3. Code Style & Static Analysis

```bash
# Run Flake8 linter
just lint

# Run Mypy static type checker
just typecheck

# Comprehensive multi-step verification gate
LOOFI_IPC_MODE=disabled QT_QPA_PLATFORM=offscreen just verify
```

---

## 4. Release Documentation & Packaging Checks

The release pipeline executes dedicated checks to prevent documentation drift:

```bash
# Verify release documentation, link targets, and version sync
python3 scripts/check_release_docs.py

# Verify canonical documentation-to-wiki mirrors
python3 scripts/sync_wiki_docs.py --check

# Validate RPM packaging metadata and AppStream XML
just check-packaging
```

