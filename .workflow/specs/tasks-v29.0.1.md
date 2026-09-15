# Tasks — v29.0.1 "Utility"

Status: implementation and local automated qualification complete; public
release closure is recorded after canonical publication and readback.

- [x] AUTH-001 | Remove legacy Action Center execution and keep the
  orchestrator as the only mutation authority.
- [x] AUTH-002 | Add the shared PyQt-free operation controller and Qt adapter.
- [x] CAT-001 | Add TaskDescriptor metadata and classify every existing action
  and route.
- [x] BUNDLE-001 | Add the versioned application and Tune bundle contract with
  independent application results and ordered stop-on-error Tune results.
- [x] UI-001 | Replace the primary shell with Home, Install, Tune, Fix, and
  Update plus secondary Activity & Recovery and Settings surfaces.
- [x] UI-002 | Convert manual-only operations to explicit instructions or
  native-settings handoffs and retire the generic action catalog from normal
  navigation.
- [x] FLOW-001 | Implement Update as the reference inline operation flow.
- [x] FLOW-002 | Implement curated multi-select Install with source-aware
  availability and per-item outcomes.
- [x] FLOW-003 | Implement editable Minimal, Recommended, and Power User Tune
  profiles with capability-gated Fedora and desktop sections.
- [x] FLOW-004 | Implement symptom-first Fix with inline verified repair or
  explicit manual/native handoff.
- [x] COMPAT-001 | Redirect legacy GUI routes and retain `changes` as the v29
  CLI compatibility alias for Activity.
- [x] DOC-001 | Synchronize active docs, CLI help, screenshots, wiki mirrors,
  architecture, release notes, and package metadata.
- [x] QUAL-001 | Pass isolated verification, release-document, architecture,
  product, packaging, drift, and RPM build gates.
- [x] [post-publish] PUB-001 | Record exact tag lineage, GitHub workflow and
  assets, checksums, attestations, COPR build and package metadata, and public
  wiki readback in the v29.0.1 publication report.

## Qualification boundaries

Physical KDE/GNOME, Traditional/Atomic, Polkit, reboot, keyboard, scaling, and
Orca sessions remain `unverified` unless independently run on the named host.
They are excluded from support claims rather than inferred from CI.
