# Architecture — v18.0.0 "Haven"

## Goal

Complete one local, verified mutation boundary while reducing duplicated
product metadata and retiring unenforceable third-party code execution.

## Decisions

- `ProductCatalogEntry` is the canonical data contract; existing plugin and
  navigation models are compatibility projections.
- `ActionDefinition` schema v3 records operation class, supported Fedora
  variants, reboot policy, and affected resources.
- Action Center is the only host writer. GUI, CLI, daemon, automation, and
  agents may plan; only an explicit user confirmation can execute.
- App-local writes use atomic state services. Session actions use validated
  domain services. Unsupported operations are manual-only.
- External plugin execution and public Marketplace distribution are retired.
  Built-in data-only plugin specs and lazy loading remain.
- Credentials use Secret Service with session-only fallback. Web API binding is
  loopback-only and every non-token route remains read-only.
- Fedora support values come from one release-policy contract rather than
  scattered literals.

## Protected behavior

- Stable route IDs, aliases, state, startup, Traditional/Atomic policy, and
  built-in plugin loading remain compatible.
- Commands are regenerated from typed definitions after fresh preflight.
- No automatic confirmation, reboot, rollback, retry, or interrupted-run resume.
- Existing external plugin files remain untouched and are never imported.
- Unknown future persisted schemas remain read-only.
