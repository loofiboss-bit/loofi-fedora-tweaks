# Tasks — v27.0.1 "Core"

**Status:** public release complete; automated qualification complete.

- [x] Phase 1 — Publication truth and unique version identity; preserve the
  historical `v27.0.0` Marketplace Enhancement tag and use `v27.0.1` for Core.
- [x] Phase 2 — Product-scope reduction; remove specialist public surfaces,
  local API/daemon, duplicate marketplace operations, and Flatpak distribution
  packaging while retaining safe host inspection compatibility.
- [x] Phase 3 — Platform neutrality; implement immutable `PlatformProfile`,
  backend-aware Traditional/Atomic behavior, and fail-closed readiness states.
- [x] Phase 4 — Core journeys; converge the five destinations, Home state,
  Updates flow, Changes review, neutral native software handoff, and responsive
  navigation.
- [x] Phase 5 — Safety and interfaces; keep Action Center as the only mutation
  authority and reduce the public CLI to documented, bounded commands.
- [x] Phase 6 — Automated qualification; run the full test suite plus lint,
  type, architecture, packaging, dependency, product-contract, and
  stabilization gates. Maintained-surface coverage is 86.94% against the 85%
  blocking gate.
- [x] Phase 7 — Release documentation; update README banner, guides, AppStream
  metadata, changelog, roadmap, wiki mirrors, and release evidence scaffolding.
- [ ] [post-publish] [authorized-skip] Raise coverage to repository-wide 90%
  and complete physical/manual Fedora qualification in a subsequent release.
