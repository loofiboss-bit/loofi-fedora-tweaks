# Loofi Fedora Tweaks v22.0.0 "Alignment"

## Canonical implementation plan

**Baseline commit:** `3c9ce62a14839f40dd1ac027cc43a83476f27571`  
**Current product version:** v21.0.0 "Resolve"  
**Active target:** v22.0.0 "Alignment"  
**Primary theme:** Fedora-native consolidation and truthful depth  
**Plan date:** 2026-07-28

## Outcome

Alignment consolidates the current Fedora control center around truthful
capability presentation, native desktop handoffs, enforceable runtime and
release gates, and a quieter task hierarchy. It adds no new execution
authority or feature family.

User-visible success means:

- Home emphasizes one next step and a compact set of current exceptions.
- Action Center presents one primary action for its current lifecycle state.
- Specialist Tools starts with a searchable group overview instead of a
  twenty-six-row route rail.
- Plasma-owned settings open the relevant installed KDE control module through
  a fixed, non-privileged, user-triggered handoff.
- Capability state is explicit when an operation is read-only, unavailable,
  manual, delegated to a native tool, or pending reboot.
- Core journeys remain keyboard-, focus-, screen-reader-, scale-, contrast-,
  RTL-, and reduced-motion-verifiable.

## Protected contracts

- Preserve all 81 stable route IDs, aliases, favorites, direct links, saved
  navigation, settings readers, and built-in lazy loading.
- Preserve Action Center schema v4, one action per expiring plan, fresh
  preflight, explicit confirmation, separate verification, and no automatic
  reboot, retry, rollback, resume, or parameter broadening.
- Preserve System Check and Trusted Change Journal stores, CLI/JSON, daemon and
  D-Bus contracts, the authenticated loopback-only read-only API, support
  bundles, and future-schema read-only behavior.
- Preserve Traditional and Atomic policy branches. Fedora 44 remains stable;
  Fedora 45 remains preview until official final availability and fresh
  Traditional plus Kinoite qualification.
- Preserve the cold-start contract: one realized Home provider and zero
  subprocess probes, active timers, or running QThreads.
- Preserve v20's historical publication-blocked status. Alignment does not
  reopen or falsely close that release.

## Phases

### Phase 0 — Authority and baseline

- Lock this plan, the architecture contract, tasks, roadmap, documentation
  index, baseline evidence, and active race lock.
- Record the current route, schema, startup, package, test, visual, and release
  state without changing runtime behavior or product version.

### Phase 1 — Trust foundation

- Make COPR terminal success, repository availability, clean installation, and
  version readback distinct mandatory gates.
- Close API/daemon RPM dependency gaps and validate their real entrypoints.
- Replace shell-like Flatpak status probes with structured application-ID
  queries.
- Enforce bounded two-phase runtime shutdown.
- Redact header, colon, whitespace, token, and password credential forms from
  support evidence.

### Phase 2 — Catalog and native alignment

- Split destination-owned catalog records behind one canonical composer while
  proving exact ordered route equality.
- Add inert capability-state and native-handoff presentation contracts.
- Resolve handoffs through one fixed allowlisted service; never persist or
  elevate command vectors.
- Delegate app discovery, network connections, appearance, display, and window
  management to installed Plasma tools while retaining Loofi-specific safe
  tasks.

### Phase 3 — Visual hierarchy and workflows

- Repair label/background hierarchy and make the shell toggle unambiguous.
- Compress Home around status, one next action, and bounded exceptions.
- Make Action Center lifecycle-driven with one primary action.
- Add a Specialist Tools group overview and improve System Check and Activity
  local-state presentation.

### Phase 4 — Accessibility and Fedora 45 readiness

- Expand the real journey focus, AT-SPI, geometry, theme, RTL, and reduced
  motion matrices.
- Verify the provider-neutral SecretStore contract, including locked and
  unavailable Secret Service behavior.
- Keep Fedora 45 preview-only unless official-final and fresh physical
  Traditional plus Kinoite evidence both pass.

### Phase 5 — Qualification and release readiness

- Run complete repository, security, package, startup, compatibility, and
  artifact gates.
- Produce exact-candidate RPM, optional subpackages, Flatpak, sdist, checksums,
  SBOM, provenance, and artifact-attestation verification.
- Treat commit, push, tag, publication, machine installation, and independent
  public readback as separately authorized release actions.

## Release gates

- `just verify`, release-document validation, packaging validation, adapter
  drift, security scans, and at least 86 percent global coverage pass.
- All 81 routes preserve identity, order, search, favorites, aliases, and direct
  links across catalog decomposition.
- Trust-foundation regressions cover success, failure, timeout, unavailable,
  and malicious-input cases through the real owning boundaries.
- Meaningful Home median and RSS stay within the Phase 0 × 1.10 ceilings, with
  one realized provider and no cold probes, timers, or QThreads.
- Offscreen evidence is supplemented by real Wayland, keyboard, Orca/AT-SPI,
  Traditional, and Atomic readback before public completion.
- COPR is never called complete from artifacts or a non-terminal API state.
