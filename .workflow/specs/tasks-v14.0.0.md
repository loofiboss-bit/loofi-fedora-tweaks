# Tasks — v14.0.0 "Helm"

## Contract

- [x] H00-H03: archive the legacy v14 tag, enforce exact tag/source lineage, and repair blocking release gates
- [x] H10-H13: complete state schema, inventory, observability locking, and atomic restore contracts
- [x] H20-H23: add canonical action definitions, expiring plans, durable runs, policy decisions, and lifecycle transitions
- [x] H30-H32: ship the deny-by-default `dnf-clean-all`, `restart-failed-service`, and `fstrim-all` catalog
- [x] H40-H42: converge Action Center GUI, CLI, read-only API, Atlas entry points, and Support Bundle v10
- [x] H50-H52: preserve Fedora 44 support, Fedora 45 preview status, compatibility IDs, and release documentation
- [x] H60-H63: pass full type, test, 85% coverage, security, RPM, Flatpak, sdist, and Fedora review gates
- [x] [post-publish] H70-H72: publish and read back GitHub, COPR, wiki, checksums, SBOM, provenance, and installed version evidence

## Required release exit

`just verify`, `just test-coverage`, `just validate-release`, `just build-rpm`,
`just build-flatpak`, `just build-sdist`, `just check-drift`, exact tag/source
lineage, Fedora 44 RPM install smoke, terminal COPR success, GitHub release
readback, and wiki readback must all succeed before v14 is marked DONE.
