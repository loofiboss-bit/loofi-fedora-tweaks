# Release Notes -- v2.2.1

**Release Date:** 2026-02-23
**Codename:** Velocity (patch)
**Theme:** CI test stability — fix @patch targets broken by the v2.2.0 cached_which migration

## Summary

v2.2.1 is a patch release that fixes CI test failures introduced in v2.2.0. The v2.2.0 migration to `cached_which` moved logic into `core/` modules, but several test files still patched names in the `utils/` shim namespace, causing 36+ test failures in CI. All affected @patch targets have been corrected.

## Highlights

- All CI test failures from v2.2.0 are resolved
- No functional changes — pure test infrastructure fix

## Changes

### Fixed

- `tests/test_ai_models.py`: corrected `@patch` targets from `utils.ai_models.*` to `core.ai.ai_models.*` for both `cached_which` and `subprocess`
- `tests/test_ai_polish.py`: corrected `@patch` targets from `utils.ai_models.*` to `core.ai.ai_models.*` for both `cached_which` and `subprocess`
- `tests/test_ai.py`: corrected `@patch` targets from `utils.ai.*` to `core.ai.ai.*` for `cached_which`
- `tests/test_agent_planner_dedicated.py`: corrected `@patch` targets from `utils.agent_planner.*` to `services.system.system.*` for `cached_which`
- `tests/test_ansible_export.py`: corrected `@patch` targets from `utils.ansible_export.*` to `core.export.ansible_export.*` for both `cached_which` and `subprocess.run`
- `tests/conftest.py`: added `FirewallManager._available_cached = None` reset in `_clear_lru_caches` fixture to prevent test isolation failures

## Stats

- **Tests:** TODO passed, TODO skipped, 0 failed
- **Lint:** 0 errors
- **Coverage:** TODO%

## Upgrade Notes

TODO — or "No user-facing changes."
