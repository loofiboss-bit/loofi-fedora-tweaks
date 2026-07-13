# Tasks — v13.0.0 "Anchor"

## Contract

- [x] A01-A03: repair metadata, source-install contract, and baseline evidence
- [x] A10-A12: canonical XDG inventory, atomic I/O, locking, schemas, and migration runner
- [x] A20: canonical metric/snapshot observability facade with compatibility aliases
- [x] A21: collector lease, typed busy state, freshness, owner, and failure status
- [x] A30: read-only State Doctor across CLI and authenticated API
- [x] A31: hashed privacy-safe archive, restore plan/apply, rollback, and threat validation
- [x] A40: preserve typed Fedora 44 supported and Fedora 45 preview target registry
- [x] A22/A32/A41: persistent Action Center v3 lifecycle, recovery audit linkage, and typed capability matrix
- [x] A50-A52: shared release quality, package/artifact verification, resumable orchestration
- [ ] A60-A61: final docs/screenshots/wiki/release evidence and live publication

## Required release exit

`just verify`, `just test-coverage`, `just validate-release`, `just build-rpm`, source-install smoke, RPM smoke, checksums, SBOM, security scan, GitHub release readback, and COPR readback must all succeed before this file and the roadmap may mark v13 DONE.
