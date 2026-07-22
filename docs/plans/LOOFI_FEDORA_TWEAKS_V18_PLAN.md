# Loofi Fedora Tweaks v18.0.0 "Haven"

## Canonical implementation plan

v18 completes the local trust boundary established by Assurance. Every supported
host mutation is planned, explicitly confirmed, audited, and independently
verified through Action Center. Unsupported mutations fail closed as manual-only.
The release removes public Marketplace distribution and executable third-party
plugins, while preserving built-in lazy-loaded plugins and stable navigation.

### Required outcomes

- Generate plugin, route, destination, section, visibility, compatibility, and
  risk views from one data-only product catalog.
- Classify every operation as host, app-state, session, or manual-only, and
  reject unclassified mutation entry points in release gates.
- Route GUI, CLI, daemon, automation, and agent host mutations through the
  Action Center lifecycle. Background actors may create plans but never confirm
  or execute them unattended.
- Add Action Center schema v3 metadata for operation class, Fedora variants,
  reboot policy, and affected resources, with atomic v2 migration.
- Retire public preset/plugin distribution, reviews, analytics, hot reload, and
  executable external plugins. Existing external files are never deleted or
  imported.
- Store credentials through Secret Service with session-only fallback, keep the
  Web API read-only and loopback-only, and add token rotation/revocation and
  issuance throttling.
- Simplify Home, Action Center, Updates, Security, Upgrade, and Advanced around
  one review-run-verify vocabulary without weakening lazy startup.
- Reduce the largest architectural hotspots, make committed project statistics
  authoritative, and synchronize security/contributor documentation with code.

### Protected contracts

- All existing route IDs and aliases remain resolvable. Retired Marketplace
  routes resolve to an explanatory local-profiles compatibility view.
- Favorites, saved navigation, lazy loading, startup budgets, themes, and
  Traditional/Atomic capability policy remain compatible.
- Built-in plugin specs and read surfaces for GUI, CLI, daemon, API, and IPC
  remain available; only external executable distribution is intentionally
  retired.
- Persisted v1/v2 state remains readable and migrates atomically. Unknown future
  schemas remain read-only.
- No persisted command is authoritative, and no exit code alone marks a host
  mutation successful.

### Phases

1. Authority, baseline, legacy v18 namespace, and complete mutation inventory.
2. Product catalog, Fedora release policy, operation classification, and gates.
3. Action Center schema v3 and full host-mutation convergence.
4. Marketplace retirement, external-code quarantine, Secret Service, and API hardening.
5. Haven workflow and information-hierarchy redesign.
6. Architectural decomposition, state/support-bundle consolidation, typing,
   statistics, and documentation quality.
7. Full regression, security, performance, packaging, and release readiness.

### Explicit non-goals

- No new AI or agent feature family, public Marketplace, remote mutation API,
  automatic distribution upgrade, automatic reboot/rollback/retry, physical
  extras split, or UI toolkit rewrite.
- No deletion of existing user plugin files or historical release evidence.
- No commit, push, tag mutation, publication, or remote-service change without
  separate explicit authorization.

### Release gates

- Full tests, lint, typecheck, architecture, state, stats, docs, security,
  dependency, SBOM, RPM, Flatpak, and sdist checks pass with at least 86 percent
  coverage and no changed-module regression.
- Zero unclassified host mutations and zero presentation/alternate-entrypoint
  direct host execution paths.
- Every existing route and alias resolves; retired Marketplace commands return
  stable machine-readable `feature_retired` results.
- Meaningful Home is no slower than `min(Phase 0 * 1.20, 225 ms)`, RSS is no
  more than Phase 0 * 1.15, and startup creates one plugin with zero probes,
  active hidden timers, or running worker threads.
- The latest supported Fedora release at RC is physically verified on
  Traditional and Atomic systems. A prerelease remains preview-only.
