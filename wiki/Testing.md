# Testing & Quality Assurance — v33.0.1 "Concord"

Loofi Fedora Tweaks uses automated quality gates to protect system safety and
prevent regressions before code is merged or published. Physical and manual
checks are supplementary evidence and never block publication; their status is
recorded as verified, pending, or unverified.

---

## 1. Automated Test Suite Metrics (v33.0.1)

- **Test Suite Results**: 5,382 passed, 33 skipped, and 2,154 subtests passed, 0 failures in local release qualification.
- **Code Coverage**: 85.49% line coverage (blocking CI gate is 85%).
- **Automated Validation**: Static typing (`mypy`), linting (`flake8`), architecture boundaries, packaging validation, and documentation link checks all pass cleanly.
- **Evidence Boundaries**: Headless/offscreen tests prove logic, command construction, and catalog contracts. Physical display server integration, hardware controllers, Polkit agents, reboot behavior, and Atomic-host behavior are recorded separately and are not inferred from automated checks; see the release publication report for their status.

---

## 2. Running Tests Locally

Run the test suite using `just`:

```bash
# Run complete test suite with headless offscreen display
LOOFI_IPC_MODE=disabled QT_QPA_PLATFORM=offscreen just test

# Run a specific test file
just test-file test_product_catalog_records

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
python3 scripts/bump_version.py --check
python3 scripts/gen_tweaks_doc.py --check

# Verify canonical documentation-to-wiki mirrors
python3 scripts/sync_wiki_docs.py --check

# Validate RPM packaging metadata and AppStream XML
just check-packaging
```

## v33.0.1 VM qualification exception

The exact-version GUI candidate failed runs 38178492268 (AT-SPI timeout) and
38178492259 (guest Python/Qt6Gui crash). The maintainer authorized completing
publication without further VM investigation. Manual release run 38183736156
passed every other gate with VM E2E explicitly skipped. The crash remains
unresolved; earlier candidate VM passes do not qualify the exact release GUI.
