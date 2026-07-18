# Tasks — v15.0.0 "Essentials"

## Contract

- [x] E00-E09: capture the v14 baseline, implementation lineage, startup/resource measurements, screenshots, workflow counts, task classification, and protected regression gates
- [x] E10-E19: add six destinations, centralized navigation policy, Standard/Advanced modes, route placement, and idempotent settings/favorites migration
- [x] E20-E29: introduce data-only `PluginSpec`, deferred plugin imports and instances, conditional startup services, lifecycle ownership, and reproducible startup benchmarks
- [x] E30-E39: replace the default route tree with a flat six-destination shell, shared secondary navigation, optional Advanced destination, and compatible direct routes
- [x] E40-E49: consolidate route, setting, and safe-action discovery into one policy-backed global search surface with navigation-only Action Center results
- [x] E50-E59: ship one canonical Home composed from existing read-only health, update, state, history, backup, and Action Center sources
- [x] E60-E69: consolidate the five core workflows and preserve Action Center as the only Review/Plan/Run/Verify/History UI
- [x] E70-E79: replace exposed experience tiers with Standard/Advanced, simplify onboarding, add Repair Loofi and About, and remove no-op/permanent shell controls
- [x] E80-E89: follow the system theme by default, use semantic icons and accessible shared states, validate responsive layouts, and remeasure startup/resources/workflow decisions
- [x] E90-E99: implement logical component discovery, audit base dependencies, preserve API/daemon subpackages, verify v14 state compatibility, and record NO-GO for a physical extras RPM
- [x] E100-E107: synchronize `15.0.0 "Essentials"` metadata, roadmap, architecture, user guides, release notes, migration guidance, AppStream, and canonical screenshots
- [x] E108: run local full-suite, coverage, lint, release-doc, packaging, Fedora-readiness, RPM, Flatpak, sdist, SBOM/checksum, security, and workflow-report gates
- [x] E109: preserve the old Nebula tag object as `legacy-v15.0.0-nebula` and deliberately free the conflicting remote `v15.0.0` tag before publication
- [ ] [post-publish] E110: commit the exact release tree, publish/read back GitHub assets and provenance, complete COPR/Fedora 44 install-upgrade evidence, and publish/read back the wiki

## Required release exit

Local publish readiness requires `just verify`, `just test-coverage`,
`just validate-release`, `just check-packaging`, `just check-drift`,
`just build-rpm`, `just build-flatpak`, `just build-sdist`, the security scan,
Fedora review contracts, screenshot verification, workflow reports, checksums,
and SBOM validation.

Public completion additionally requires one exact release commit, a remote
`v15.0.0` tag that peels to it, terminal GitHub Actions and COPR success,
Fedora 44 install/upgrade evidence, GitHub release asset readback, and wiki
readback. The historical 2026-02-08 Nebula tag collision must be remediated
without losing its commit before the exact-lineage gate can pass. That
remediation is complete; publication and readback remain open.
